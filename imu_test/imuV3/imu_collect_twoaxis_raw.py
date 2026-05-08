"""
imu_collect_twoaxis_raw.py - collect two-axis telescope pointing angles plus raw per-IMU
                              Euler angles from two BNO085/Pico IMUs.

                              Live plot shows each IMU's roll/pitch/yaw and accelerometer
                              independently (same style as imu_collect_accel.py), so you
                              can see what each sensor is doing on its own.

                              The log file saves everything: elevation, azimuth, raw Euler
                              angles, and accel for both IMUs. This means it works with
                              both two_axis_angles.py (for the computed pointing angles)
                              and plotter_twoaxis.py (for the raw per-IMU angles).

Usage:
    python3 imu_collect_twoaxis_raw.py
    python3 imu_collect_twoaxis_raw.py --no-plot
    python3 imu_collect_twoaxis_raw.py --ports /dev/ttyACM0 /dev/ttyACM1
    python3 imu_collect_twoaxis_raw.py --m0 0 0 0 --m1 0 90 0
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
    # Convert yaw/pitch/roll angles (in degrees) into a 3x3 rotation matrix.
    # This lets us do math on orientations instead of raw angles.
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


def recover_angles(sample0, sample1, mount0_rotation, mount1_rotation):
    # Figure out where the telescope is pointing (elevation and azimuth)
    # using the raw orientation readings from both IMUs.
    # IMU0 tells us the elevation (up/down angle).
    # IMU1 tells us the azimuth (left/right angle), corrected for the current elevation.
    roll0, pitch0, yaw0 = sample0[0], sample0[1], sample0[2]
    roll1, pitch1, yaw1 = sample1[0], sample1[1], sample1[2]

    # Build rotation matrices from each IMU's current orientation
    rotation0 = euler_to_matrix(yaw0, pitch0, roll0)
    rotation1 = euler_to_matrix(yaw1, pitch1, roll1)

    # Use IMU0 to extract the elevation angle, accounting for how it's mounted
    elev_rotation = rotation0 @ mount0_rotation.T
    elevation = np.degrees(np.arctan2(elev_rotation[2, 1], elev_rotation[2, 2]))

    # Undo the effect of elevation before reading azimuth from IMU1,
    # so that azimuth stays accurate regardless of how high the telescope is tilted
    elev_rad = np.radians(elevation)
    cos_elev, sin_elev = np.cos(elev_rad), np.sin(elev_rad)
    undo_elev_rotation = np.array([[1,         0,          0],
                                   [0,  cos_elev,  sin_elev],
                                   [0, -sin_elev,  cos_elev]])

    az_rotation = undo_elev_rotation @ rotation1 @ mount1_rotation.T
    azimuth = np.degrees(np.arctan2(az_rotation[1, 0], az_rotation[0, 0]))

    return elevation, azimuth


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
        path = os.path.join(LOG_DIR, f"twoaxis_raw{i:03d}.csv")
        if not os.path.exists(path):
            return path
        i += 1


class LoggingThread(threading.Thread):
    def __init__(self, readers, log_path, hz, mount0_rotation, mount1_rotation):
        super().__init__(daemon=True, name="logger")
        self.readers = readers
        self.log_path = log_path
        self.hz = hz
        self.mount0_rotation = mount0_rotation
        self.mount1_rotation = mount1_rotation
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
            # Log everything: computed pointing angles, raw Euler angles, and accel for both IMUs
            writer.writerow([
                "unix_time", "t_rel_s", "elevation_deg", "azimuth_deg",
                "imu0_roll_deg", "imu0_pitch_deg", "imu0_yaw_deg", "imu0_ax", "imu0_ay", "imu0_az",
                "imu1_roll_deg", "imu1_pitch_deg", "imu1_yaw_deg", "imu1_ax", "imu1_ay", "imu1_az",
            ])
            f.flush()

            while not self._stop_event.is_set():
                now = time.time()

                # Rate-limit writes to the requested log frequency
                if (now - last_log) < period:
                    time.sleep(0.0005)
                    continue
                last_log = now

                # Skip this tick if either IMU hasn't sent its first reading yet
                s0, s1 = self.readers[0].latest, self.readers[1].latest
                if s0 is None or s1 is None:
                    continue

                t = now - self.t0
                elevation, azimuth = recover_angles(s0, s1, self.mount0_rotation, self.mount1_rotation)

                writer.writerow([
                    f"{now:.6f}", f"{t:.6f}",
                    f"{elevation:.4f}", f"{azimuth:.4f}",
                    f"{s0[0]:.4f}", f"{s0[1]:.4f}", f"{s0[2]:.4f}", f"{s0[3]:.6f}", f"{s0[4]:.6f}", f"{s0[5]:.6f}",
                    f"{s1[0]:.4f}", f"{s1[1]:.4f}", f"{s1[2]:.4f}", f"{s1[3]:.6f}", f"{s1[4]:.6f}", f"{s1[5]:.6f}",
                ])
                self.rows_written += 1

                # Flush to disk periodically so data isn't lost if the program crashes
                if self.rows_written % FLUSH_EVERY == 0:
                    f.flush()

                if (now - last_print) >= 0.5:
                    last_print = now
                    print(
                        f"  t={t:7.2f}s  "
                        f"imu0 r={s0[0]:6.2f} p={s0[1]:6.2f} y={s0[2]:6.2f}  "
                        f"imu1 r={s1[0]:6.2f} p={s1[1]:6.2f} y={s1[2]:6.2f}  "
                        f"[{self.rows_written} rows]",
                        end="\r", flush=True,
                    )

            f.flush()


def run_plot(readers, active_ports, window_sec, plot_hz):
    # Live plot showing each IMU's roll/pitch/yaw and accelerometer independently,
    # same style as imu_collect_accel.py so each sensor is easy to read on its own.
    try:
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plot] matplotlib unavailable: {e}")
        return

    n = len(readers)
    maxlen = max(10, int(window_sec * plot_hz))
    period = 1.0 / plot_hz
    ts = deque(maxlen=maxlen)
    bufs = [{"roll": deque(maxlen=maxlen),
             "pitch": deque(maxlen=maxlen),
             "yaw": deque(maxlen=maxlen),
             "ax": deque(maxlen=maxlen),
             "ay": deque(maxlen=maxlen),
             "az": deque(maxlen=maxlen)} for _ in range(n)]

    plt.ion()
    fig, axes = plt.subplots(n * 2, 1, sharex=True, figsize=(10, 3 * n * 2), squeeze=False)
    angle_lines = []
    accel_lines = []
    for i in range(n):
        ax_ang = axes[i * 2][0]
        (roll_line,)  = ax_ang.plot([], [], color="tab:blue",   label="roll",  lw=1.5)
        (pitch_line,) = ax_ang.plot([], [], color="tab:orange", label="pitch", lw=1.5)
        (yaw_line,)   = ax_ang.plot([], [], color="tab:green",  label="yaw",   lw=1.5)
        angle_lines.append((roll_line, pitch_line, yaw_line))
        ax_ang.set_title(f"IMU {i}  ({active_ports[i]}) - Angles")
        ax_ang.set_ylabel("Degrees")
        ax_ang.legend(loc="upper right", fontsize=8)
        ax_ang.grid(True)

        ax_acc = axes[i * 2 + 1][0]
        (ax_line,) = ax_acc.plot([], [], color="tab:red",    label="ax", lw=1.5)
        (ay_line,) = ax_acc.plot([], [], color="tab:purple", label="ay", lw=1.5)
        (az_line,) = ax_acc.plot([], [], color="tab:brown",  label="az", lw=1.5)
        accel_lines.append((ax_line, ay_line, az_line))
        ax_acc.set_title(f"IMU {i}  ({active_ports[i]}) - Accel")
        ax_acc.set_ylabel("m/s^2")
        ax_acc.legend(loc="upper right", fontsize=8)
        ax_acc.grid(True)

    axes[-1][0].set_xlabel("Time (s)")
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

            samples = [r.latest for r in readers]
            if any(s is None for s in samples):
                plt.pause(0.01)
                continue

            t = now - t0
            ts.append(t)
            for i, (roll, pitch, yaw, ax, ay, az) in enumerate(samples):
                bufs[i]["roll"].append(roll)
                bufs[i]["pitch"].append(pitch)
                bufs[i]["yaw"].append(yaw)
                bufs[i]["ax"].append(ax)
                bufs[i]["ay"].append(ay)
                bufs[i]["az"].append(az)

            for i, (roll_line, pitch_line, yaw_line) in enumerate(angle_lines):
                roll_line.set_data(ts, bufs[i]["roll"])
                pitch_line.set_data(ts, bufs[i]["pitch"])
                yaw_line.set_data(ts, bufs[i]["yaw"])

            for i, (ax_line, ay_line, az_line) in enumerate(accel_lines):
                ax_line.set_data(ts, bufs[i]["ax"])
                ay_line.set_data(ts, bufs[i]["ay"])
                az_line.set_data(ts, bufs[i]["az"])

            if len(ts) >= 2:
                xmin = max(0.0, ts[-1] - window_sec)
                axes[0][0].set_xlim(xmin, ts[-1])

            for i in range(n):
                all_ang = list(bufs[i]["roll"]) + list(bufs[i]["pitch"]) + list(bufs[i]["yaw"])
                if all_ang:
                    ymin, ymax = min(all_ang), max(all_ang)
                    pad = max(1.0, 0.1 * (ymax - ymin) if ymax > ymin else 1.0)
                    axes[i * 2][0].set_ylim(ymin - pad, ymax + pad)

                all_acc = list(bufs[i]["ax"]) + list(bufs[i]["ay"]) + list(bufs[i]["az"])
                if all_acc:
                    ymin, ymax = min(all_acc), max(all_acc)
                    pad = max(0.1, 0.1 * (ymax - ymin) if ymax > ymin else 0.1)
                    axes[i * 2 + 1][0].set_ylim(ymin - pad, ymax + pad)

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

    # Build rotation matrices from the user-supplied mounting offsets.
    # These correct for the physical angle each IMU is glued onto the telescope.
    mount0_rotation = euler_to_matrix(*args.m0)
    mount1_rotation = euler_to_matrix(*args.m1)

    # --- Step 1: Find candidate serial ports ---
    candidate_ports = args.ports if args.ports else find_ports()
    if not candidate_ports:
        print("No serial ports found.")
        return

    # --- Step 2: Probe each port to see which ones actually have an IMU talking ---
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

    # --- Step 3: Make sure we have exactly 2 IMUs ---
    if len(active_ports) < 2:
        print(f"Need 2 IMUs, only found {len(active_ports)}.")
        return

    if len(active_ports) > 2:
        print(f"Found {len(active_ports)} IMUs, using first two: {active_ports[:2]}")
        active_ports = active_ports[:2]

    time.sleep(0.2)

    # --- Step 4: Start the real reader threads ---
    readers = [ImuReader(p, args.baud, i) for i, p in enumerate(active_ports)]
    for r in readers:
        r.start()

    # Wait until both IMUs have sent at least one packet before logging starts
    t_wait = time.time()
    while any(r.latest is None for r in readers):
        if time.time() - t_wait > 10.0:
            print("warning: some IMUs never sent data, starting anyway")
            for r in readers:
                if r.latest is None:
                    r.latest = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            break
        time.sleep(0.01)

    # --- Step 5: Start logging and (optionally) plotting ---
    log_path = next_log_path()
    print(f"Logging to {log_path}  (Ctrl-C to stop)\n")

    logger = LoggingThread(readers, log_path, args.hz, mount0_rotation, mount1_rotation)
    logger.start()

    try:
        if not args.no_plot:
            run_plot(readers, active_ports, args.window, args.plot_hz)
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
