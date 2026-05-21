"""
imu_collect_single.py - collect data from a single BNO085/Pico IMU

Usage:
    python3 imu_collect_single.py
    python3 imu_collect_single.py --no-plot
    python3 imu_collect_single.py --port /dev/ttyACM0
"""

import argparse
import csv
import glob
import os
import threading
import time
from collections import deque

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


class ImuReader(threading.Thread):
    def __init__(self, port, baud):
        super().__init__(daemon=True, name="imu")
        self.port = port
        self.baud = baud
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
        path = os.path.join(LOG_DIR, f"imu_data{i:03d}.csv")
        if not os.path.exists(path):
            return path
        i += 1


class LoggingThread(threading.Thread):
    def __init__(self, reader, log_path, hz):
        super().__init__(daemon=True, name="logger")
        self.reader = reader
        self.log_path = log_path
        self.hz = hz
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
            writer.writerow([
                "unix_time", "t_rel_s",
                "roll_deg", "pitch_deg", "yaw_deg",
                "ax", "ay", "az",
            ])
            f.flush()

            while not self._stop_event.is_set():
                now = time.time()
                if (now - last_log) < period:
                    time.sleep(0.0005)
                    continue
                last_log = now

                s = self.reader.latest
                if s is None:
                    continue

                t = now - self.t0
                roll, pitch, yaw, ax, ay, az = s
                writer.writerow([
                    f"{now:.6f}", f"{t:.6f}",
                    f"{roll:.4f}", f"{pitch:.4f}", f"{yaw:.4f}",
                    f"{ax:.6f}", f"{ay:.6f}", f"{az:.6f}",
                ])
                self.rows_written += 1

                if self.rows_written % FLUSH_EVERY == 0:
                    f.flush()

                if (now - last_print) >= 0.5:
                    last_print = now
                    print(
                        f"  t={t:7.2f}s  "
                        f"roll={roll:6.2f}  pitch={pitch:6.2f}  yaw={yaw:6.2f}  "
                        f"[{self.rows_written} rows]",
                        end="\r", flush=True,
                    )

            f.flush()


def run_plot(reader, port, window_sec, plot_hz):
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
    bufs = {k: deque(maxlen=maxlen) for k in ("roll", "pitch", "yaw", "ax", "ay", "az")}

    plt.ion()
    fig, (ax_ang, ax_acc) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    fig.suptitle(f"IMU  ({port})", fontsize=11, fontweight="bold")

    (roll_line,)  = ax_ang.plot([], [], color="tab:blue",   label="roll",  lw=1.5)
    (pitch_line,) = ax_ang.plot([], [], color="tab:orange", label="pitch", lw=1.5)
    (yaw_line,)   = ax_ang.plot([], [], color="tab:green",  label="yaw",   lw=1.5)
    ax_ang.set_ylabel("Degrees")
    ax_ang.legend(loc="upper right", fontsize=8)
    ax_ang.grid(True)

    (ax_line,) = ax_acc.plot([], [], color="tab:red",    label="ax", lw=1.5)
    (ay_line,) = ax_acc.plot([], [], color="tab:purple", label="ay", lw=1.5)
    (az_line,) = ax_acc.plot([], [], color="tab:brown",  label="az", lw=1.5)
    ax_acc.set_ylabel("m/s²")
    ax_acc.set_xlabel("Time (s)")
    ax_acc.legend(loc="upper right", fontsize=8)
    ax_acc.grid(True)

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

            s = reader.latest
            if s is None:
                plt.pause(0.01)
                continue

            roll, pitch, yaw, ax, ay, az = s
            t = now - t0
            ts.append(t)
            bufs["roll"].append(roll);   bufs["pitch"].append(pitch); bufs["yaw"].append(yaw)
            bufs["ax"].append(ax);       bufs["ay"].append(ay);       bufs["az"].append(az)

            roll_line.set_data(ts, bufs["roll"])
            pitch_line.set_data(ts, bufs["pitch"])
            yaw_line.set_data(ts, bufs["yaw"])
            ax_line.set_data(ts, bufs["ax"])
            ay_line.set_data(ts, bufs["ay"])
            az_line.set_data(ts, bufs["az"])

            if len(ts) >= 2:
                ax_ang.set_xlim(max(0.0, ts[-1] - window_sec), ts[-1])

            all_ang = list(bufs["roll"]) + list(bufs["pitch"]) + list(bufs["yaw"])
            if all_ang:
                ymin, ymax = min(all_ang), max(all_ang)
                pad = max(1.0, 0.1 * (ymax - ymin))
                ax_ang.set_ylim(ymin - pad, ymax + pad)

            all_acc = list(bufs["ax"]) + list(bufs["ay"]) + list(bufs["az"])
            if all_acc:
                ymin, ymax = min(all_acc), max(all_acc)
                pad = max(0.1, 0.1 * (ymax - ymin))
                ax_acc.set_ylim(ymin - pad, ymax + pad)

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
    ap.add_argument("--port", default=None)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--hz", type=float, default=LOG_HZ)
    ap.add_argument("--no-plot", action="store_true")
    ap.add_argument("--window", type=float, default=WINDOW_SEC)
    ap.add_argument("--plot-hz", type=float, default=PLOT_HZ)
    args = ap.parse_args()

    if args.port:
        candidates = [args.port]
    else:
        candidates = find_ports()
    if not candidates:
        print("no serial ports found")
        return

    print(f"probing {len(candidates)} port(s) for {PROBE_SECS:.0f}s ...")
    probes = [ImuReader(p, args.baud) for p in candidates]
    for r in probes:
        r.start()
    time.sleep(PROBE_SECS)

    port = None
    for r, p in zip(probes, candidates):
        r.stop()
        r.join(timeout=2.0)
        if r.error:
            print(f"  skip {p}: {r.error}")
        elif r.latest is None:
            print(f"  skip {p}: no data")
        else:
            print(f"  ok   {p}")
            port = p
            break  # use the first one that responds

    if port is None:
        print("no IMU found")
        return

    time.sleep(0.2)

    reader = ImuReader(port, args.baud)
    reader.start()

    t_wait = time.time()
    while reader.latest is None:
        if time.time() - t_wait > 10.0:
            print("warning: IMU never sent data, starting anyway")
            reader.latest = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            break
        time.sleep(0.01)

    log_path = next_log_path()
    print(f"logging to {log_path}  (Ctrl-C to stop)\n")

    logger = LoggingThread(reader, log_path, args.hz)
    logger.start()

    try:
        if not args.no_plot:
            run_plot(reader, port, args.window, args.plot_hz)
            print("plot closed. still logging... (Ctrl-C to stop)")
        while logger.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        logger.stop()
        logger.join(timeout=2.0)
        reader.stop()

    print(f"\ndone. {logger.rows_written} rows -> {log_path}")


if __name__ == "__main__":
    main()
