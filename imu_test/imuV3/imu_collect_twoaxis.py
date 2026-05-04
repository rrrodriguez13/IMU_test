"""
imu_collect_twoaxis.py - collect two-axis telescope pointing angles (elevation θ, azimuth φ)
                         live from two BNO085/Pico IMUs, bypassing gimbal lock

    python3 imu_collect_twoaxis.py
    python3 imu_collect_twoaxis.py --no-plot
    python3 imu_collect_twoaxis.py --ports /dev/ttyACM0 /dev/ttyACM1
    python3 imu_collect_twoaxis.py --m0 0 0 0 --m1 0 90 0
"""

import argparse
import csv
import glob
import os
import threading
import time
from collections import deque

import numpy as np
import serial

BAUD = 115200
LOG_HZ = 50
PLOT_HZ = 24
WINDOW_SEC = 10
LOG_DIR = "logs"
FLUSH_EVERY = 20
PROBE_SECS = 5.0


def find_ports():
    return sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))


def read_packet(ser):
    raw = ser.readline()
    if not raw:
        return None
    try:
        parts = raw.decode("utf-8", errors="replace").strip().split(",")
        if len(parts) != 6:
            return None
        yaw, pitch, roll, ax, ay, az = (float(p) for p in parts)
        return roll, pitch, yaw, ax, ay, az
    except ValueError:
        return None


def euler_to_matrix(yaw_deg, pitch_deg, roll_deg):
    y = np.radians(yaw_deg)
    p = np.radians(pitch_deg)
    r = np.radians(roll_deg)
    cy, sy = np.cos(y), np.sin(y)
    cp, sp = np.cos(p), np.sin(p)
    cr, sr = np.cos(r), np.sin(r)
    R = np.zeros((*np.shape(y), 3, 3))
    R[..., 0, 0] =  cy*cp
    R[..., 0, 1] =  cy*sp*sr - sy*cr
    R[..., 0, 2] =  cy*sp*cr + sy*sr
    R[..., 1, 0] =  sy*cp
    R[..., 1, 1] =  sy*sp*sr + cy*cr
    R[..., 1, 2] =  sy*sp*cr - cy*sr
    R[..., 2, 0] = -sp
    R[..., 2, 1] =  cp*sr
    R[..., 2, 2] =  cp*cr
    return R


def recover_angles(sample0, sample1, M0, M1):
    roll0, pitch0, yaw0 = sample0[0], sample0[1], sample0[2]
    roll1, pitch1, yaw1 = sample1[0], sample1[1], sample1[2]

    R0 = euler_to_matrix(yaw0, pitch0, roll0)
    R1 = euler_to_matrix(yaw1, pitch1, roll1)

    R_elev = R0 @ M0.T
    theta = np.degrees(np.arctan2(R_elev[2, 1], R_elev[2, 2]))

    t = np.radians(theta)
    c, s = np.cos(t), np.sin(t)
    Rx_T = np.array([[1, 0,  0],
                     [0, c,  s],
                     [0, -s, c]])

    R_az = Rx_T @ R1 @ M1.T
    phi = np.degrees(np.arctan2(R_az[1, 0], R_az[0, 0]))

    return theta, phi


class ImuReader(threading.Thread):
    def __init__(self, port, baud, idx):
        super().__init__(daemon=True, name=f"imu{idx}")
        self.port = port
        self.baud = baud
        self.idx = idx
        self.latest = None
        self.error = None
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
                ser.reset_input_buffer()
                while not self._stop_event.is_set():
                    pkt = read_packet(ser)
                    if pkt is not None:
                        self.latest = pkt
        except serial.SerialException as e:
            self.error = str(e)


def next_log_path():
    os.makedirs(LOG_DIR, exist_ok=True)
    i = 0
    while True:
        path = os.path.join(LOG_DIR, f"twoaxis{i:03d}.csv")
        if not os.path.exists(path):
            return path
        i += 1


class LoggingThread(threading.Thread):
    def __init__(self, readers, log_path, hz, M0, M1):
        super().__init__(daemon=True, name="logger")
        self.readers = readers
        self.log_path = log_path
        self.hz = hz
        self.M0 = M0
        self.M1 = M1
        self.rows_written = 0
        self.t0 = None
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        period = 1.0 / self.hz
        last_log = 0.0
        last_print = 0.0
        self.t0 = time.time()

        with open(self.log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["unix_time", "t_rel_s", "theta_deg", "phi_deg",
                             "imu0_ax", "imu0_ay", "imu0_az",
                             "imu1_ax", "imu1_ay", "imu1_az"])
            f.flush()

            while not self._stop_event.is_set():
                now = time.time()
                if (now - last_log) < period:
                    time.sleep(0.0005)
                    continue
                last_log = now

                s0, s1 = self.readers[0].latest, self.readers[1].latest
                if s0 is None or s1 is None:
                    continue

                t = now - self.t0
                theta, phi = recover_angles(s0, s1, self.M0, self.M1)

                writer.writerow([f"{now:.6f}", f"{t:.6f}",
                                 f"{theta:.4f}", f"{phi:.4f}",
                                 f"{s0[3]:.6f}", f"{s0[4]:.6f}", f"{s0[5]:.6f}",
                                 f"{s1[3]:.6f}", f"{s1[4]:.6f}", f"{s1[5]:.6f}"])
                self.rows_written += 1

                if self.rows_written % FLUSH_EVERY == 0:
                    f.flush()

                if (now - last_print) >= 0.5:
                    last_print = now
                    print(f"  t={t:7.2f}s  theta={theta:7.2f}  phi={phi:7.2f}"
                          f"  [{self.rows_written} rows]", end="\r", flush=True)

            f.flush()


def run_plot(readers, active_ports, M0, M1, window_sec, plot_hz):
    try:
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plot] matplotlib unavailable: {e}")
        return

    maxlen = max(10, int(window_sec * plot_hz))
    period = 1.0 / plot_hz
    ts = deque(maxlen=maxlen)
    thetas = deque(maxlen=maxlen)
    phis = deque(maxlen=maxlen)
    accel_bufs = [{"ax": deque(maxlen=maxlen),
                   "ay": deque(maxlen=maxlen),
                   "az": deque(maxlen=maxlen)} for _ in range(2)]

    plt.ion()
    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(10, 10))
    ax_t, ax_p, ax_a0, ax_a1 = axes

    (lt,) = ax_t.plot([], [], color="#e07b00", lw=1.5)
    (lp,) = ax_p.plot([], [], color="#2ca02c", lw=1.5)
    accel_lines = []
    for ax_a, label in ((ax_a0, "IMU0"), (ax_a1, "IMU1")):
        (lax,) = ax_a.plot([], [], color="tab:red",    label="ax", lw=1.5)
        (lay,) = ax_a.plot([], [], color="tab:purple", label="ay", lw=1.5)
        (laz,) = ax_a.plot([], [], color="tab:brown",  label="az", lw=1.5)
        accel_lines.append((lax, lay, laz))
        ax_a.set_ylabel(f"{label} Accel (m/s²)")
        ax_a.legend(loc="upper right", fontsize=8)
        ax_a.grid(True)

    ax_t.set_ylabel("Elevation θ (°)")
    ax_p.set_ylabel("Azimuth φ (°)")
    axes[-1].set_xlabel("Time (s)")
    for ax in (ax_t, ax_p):
        ax.grid(True)
        ax.axhline(0, color="#cccccc", lw=0.8)
    fig.suptitle("Live Two-Axis Pointing", fontsize=12, fontweight="bold")
    fig.tight_layout()

    t0 = time.time()
    last_update = 0.0

    try:
        while plt.fignum_exists(fig.number):
            now = time.time()
            if (now - last_update) < period:
                plt.pause(0.01)
                continue
            last_update = now

            s0, s1 = readers[0].latest, readers[1].latest
            if s0 is None or s1 is None:
                plt.pause(0.01)
                continue

            theta, phi = recover_angles(s0, s1, M0, M1)
            t = now - t0
            ts.append(t)
            thetas.append(theta)
            phis.append(phi)
            for i, s in enumerate((s0, s1)):
                accel_bufs[i]["ax"].append(s[3])
                accel_bufs[i]["ay"].append(s[4])
                accel_bufs[i]["az"].append(s[5])

            lt.set_data(ts, thetas)
            lp.set_data(ts, phis)
            for i, (lax, lay, laz) in enumerate(accel_lines):
                lax.set_data(ts, accel_bufs[i]["ax"])
                lay.set_data(ts, accel_bufs[i]["ay"])
                laz.set_data(ts, accel_bufs[i]["az"])

            if len(ts) >= 2:
                xmin = max(0.0, ts[-1] - window_sec)
                ax_t.set_xlim(xmin, ts[-1])

            for ax, buf in ((ax_t, thetas), (ax_p, phis)):
                if buf:
                    ymin, ymax = min(buf), max(buf)
                    pad = max(1.0, 0.1 * (ymax - ymin) if ymax > ymin else 1.0)
                    ax.set_ylim(ymin - pad, ymax + pad)

            for i, ax_a in enumerate((ax_a0, ax_a1)):
                all_a = (list(accel_bufs[i]["ax"]) + list(accel_bufs[i]["ay"])
                         + list(accel_bufs[i]["az"]))
                if all_a:
                    ymin, ymax = min(all_a), max(all_a)
                    pad = max(0.1, 0.1 * (ymax - ymin) if ymax > ymin else 0.1)
                    ax_a.set_ylim(ymin - pad, ymax + pad)

            fig.canvas.draw_idle()
            plt.pause(0.01)

    except Exception:
        pass
    finally:
        try:
            plt.close("all")
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", nargs="+", default=None)
    ap.add_argument("--baud", default=BAUD, type=int)
    ap.add_argument("--hz", default=LOG_HZ, type=float)
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--window", default=WINDOW_SEC, type=float)
    ap.add_argument("--plot-hz", default=PLOT_HZ, type=float)
    ap.add_argument("--m0", nargs=3, type=float, metavar=("YAW", "PITCH", "ROLL"),
                    default=[0.0, 0.0, 0.0])
    ap.add_argument("--m1", nargs=3, type=float, metavar=("YAW", "PITCH", "ROLL"),
                    default=[0.0, 0.0, 0.0])
    args = ap.parse_args()

    M0 = euler_to_matrix(*args.m0)
    M1 = euler_to_matrix(*args.m1)

    candidate_ports = args.ports if args.ports else find_ports()
    if not candidate_ports:
        print("No serial ports found.")
        return

    print(f"Probing {len(candidate_ports)} port(s) for {PROBE_SECS:.0f}s...")
    probes = [ImuReader(p, args.baud, i) for i, p in enumerate(candidate_ports)]
    for r in probes:
        r.start()
    time.sleep(PROBE_SECS)

    active_ports = []
    for r in probes:
        r.stop()
        r.join(timeout=2.0)
        if r.error:
            print(f"  skip {r.port}: {r.error}")
        elif r.latest is None:
            print(f"  skip {r.port}: no data")
        else:
            print(f"  ok   {r.port}")
            active_ports.append(r.port)

    if len(active_ports) < 2:
        print(f"Need 2 IMUs, only found {len(active_ports)}.")
        return

    if len(active_ports) > 2:
        print(f"Found {len(active_ports)} IMUs, using first two: {active_ports[:2]}")
        active_ports = active_ports[:2]

    time.sleep(0.2)

    readers = [ImuReader(p, args.baud, i) for i, p in enumerate(active_ports)]
    for r in readers:
        r.start()

    t_wait = time.time()
    while any(r.latest is None for r in readers):
        if time.time() - t_wait > 10.0:
            print("warning: some IMUs never sent data, starting anyway")
            for r in readers:
                if r.latest is None:
                    r.latest = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            break
        time.sleep(0.01)

    log_path = next_log_path()
    print(f"Logging to {log_path}  (Ctrl-C to stop)\n")

    logger = LoggingThread(readers, log_path, args.hz, M0, M1)
    logger.start()

    try:
        if not args.no_plot:
            run_plot(readers, active_ports, M0, M1, args.window, args.plot_hz)
            print("Plot closed. Still logging... (Ctrl-C to stop)")
        while logger.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        logger.stop()
        logger.join(timeout=2.0)
        for r in readers:
            r.stop()

    print(f"\nDone. {logger.rows_written} rows -> {log_path}")


if __name__ == "__main__":
    main()
