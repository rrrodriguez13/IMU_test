"""
imu_collect.py  –  Auto-detecting N-IMU CSV-text collector + live plot
=======================================================================
Plug in any number of BNO085-via-Pico devices.  The script finds all
/dev/ttyACM* ports, probes each one for 5 seconds to skip silent REPL
ports, then logs all active IMUs to a single CSV.

The live plot runs on the main thread (required by matplotlib/Tk).
The logging loop runs in a background thread so closing the plot window
or any plot error never interrupts data collection.

Usage
-----
    python3 imu_collect.py                # auto-detect, with live plot
    python3 imu_collect.py --no-plot      # data only, no plot window
    python3 imu_collect.py --ports /dev/ttyACM0 /dev/ttyACM1
    python3 imu_collect.py --hz 50 --window 10

Plotting saved data
-------------------
    python3 plotter.py logs/imu_data000.csv
"""

import argparse
import csv
import glob
import os
import threading
import time
from collections import deque

import serial

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_BAUD    = 115200
LOG_HZ          = 50
PLOT_HZ         = 24
WINDOW_SEC      = 10
LOG_DIR         = "logs"
LOG_PREFIX      = "imu_data"
LOG_DIGITS      = 3
LOG_EXT         = ".csv"
FLUSH_EVERY_N   = 20
PROBE_SECS      = 5.0
PRINT_HZ        = 2
FIRST_SAMPLE_TO = 10.0   # seconds to wait for first sample before giving up


# ── port auto-detection ───────────────────────────────────────────────────────

def find_ports() -> list[str]:
    return sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))


# ── CSV text parser ───────────────────────────────────────────────────────────

def read_packet(ser: serial.Serial):
    raw = ser.readline()
    if not raw:
        return None
    try:
        parts = raw.decode("utf-8", errors="replace").strip().split(",")
        if len(parts) != 6:
            return None
        yaw, pitch, roll, ax_, ay_, az_ = (float(p) for p in parts)
        return roll, pitch, yaw, ax_, ay_, az_
    except ValueError:
        return None


# ── per-IMU reader thread ─────────────────────────────────────────────────────

class ImuReader(threading.Thread):
    def __init__(self, port: str, baud: int, idx: int):
        super().__init__(daemon=True, name=f"imu{idx}")
        self.port   = port
        self.baud   = baud
        self.idx    = idx
        self.latest = None
        self.error  = None
        self._stop  = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
                ser.reset_input_buffer()
                while not self._stop.is_set():
                    pkt = read_packet(ser)
                    if pkt is not None:
                        self.latest = pkt
        except serial.SerialException as e:
            self.error = str(e)


# ── logging thread ────────────────────────────────────────────────────────────

class LoggingThread(threading.Thread):
    def __init__(self, readers, log_path, hz):
        super().__init__(daemon=True, name="logger")
        self.readers      = readers
        self.log_path     = log_path
        self.hz           = hz
        self.rows_written = 0
        self.t0           = None
        self._stop        = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
        n            = len(self.readers)
        header       = build_header(n)
        log_period   = 1.0 / self.hz
        print_period = 1.0 / PRINT_HZ
        last_log     = 0.0
        last_print   = 0.0
        self.t0      = time.time()

        with open(self.log_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            f.flush()

            while not self._stop.is_set():
                now = time.time()
                if (now - last_log) < log_period:
                    time.sleep(0.0005)
                    continue
                last_log = now

                samples = [r.latest for r in self.readers]
                t = now - self.t0

                row = [f"{now:.6f}", f"{t:.6f}"]
                for roll, pitch, yaw, ax_, ay_, az_ in samples:
                    row += [f"{roll:.4f}", f"{pitch:.4f}", f"{yaw:.4f}",
                            f"{ax_:.6f}",  f"{ay_:.6f}",  f"{az_:.6f}"]
                writer.writerow(row)
                self.rows_written += 1

                if self.rows_written % FLUSH_EVERY_N == 0:
                    f.flush()

                if (now - last_print) >= print_period:
                    last_print = now
                    vals = " | ".join(
                        f"imu{i} r={s[0]:6.2f} p={s[1]:6.2f} y={s[2]:6.2f}"
                        for i, s in enumerate(samples)
                    )
                    print(f"  t={t:7.2f}s  {vals}  [{self.rows_written} rows]",
                          end="\r", flush=True)

            f.flush()


# ── logging helpers ───────────────────────────────────────────────────────────

def next_log_path() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    i = 0
    while True:
        path = os.path.join(LOG_DIR, f"{LOG_PREFIX}{i:0{LOG_DIGITS}d}{LOG_EXT}")
        if not os.path.exists(path):
            return path
        i += 1


def build_header(n: int) -> list[str]:
    cols = ["unix_time", "t_rel_s"]
    for i in range(n):
        cols += [f"imu{i}_roll_deg", f"imu{i}_pitch_deg", f"imu{i}_yaw_deg",
                 f"imu{i}_ax",       f"imu{i}_ay",        f"imu{i}_az"]
    return cols


# ── live plot (main thread) ───────────────────────────────────────────────────

def run_plot(readers, active_ports, window_sec, plot_hz):
    try:
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print(f"[plot] matplotlib unavailable: {e}")
        return

    n      = len(readers)
    maxlen = max(10, int(window_sec * plot_hz))
    period = 1.0 / plot_hz
    ts     = deque(maxlen=maxlen)
    bufs   = [{"roll":  deque(maxlen=maxlen),
                "pitch": deque(maxlen=maxlen),
                "yaw":   deque(maxlen=maxlen)} for _ in range(n)]

    plt.ion()
    fig, axes = plt.subplots(n, 1, sharex=True,
                             figsize=(10, 3 * n),
                             squeeze=False)
    lines = []
    for i in range(n):
        ax = axes[i][0]
        (lr,) = ax.plot([], [], color="tab:blue",   label="roll",  lw=1.5)
        (lp,) = ax.plot([], [], color="tab:orange", label="pitch", lw=1.5)
        (ly,) = ax.plot([], [], color="tab:green",  label="yaw",   lw=1.5)
        lines.append((lr, lp, ly))
        ax.set_title(f"IMU {i}  ({active_ports[i]})  — Roll / Pitch / Yaw")
        ax.set_ylabel("Degrees")
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True)
    axes[-1][0].set_xlabel("Time (s)")
    fig.tight_layout()

    t0          = time.time()
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
            for i, (roll, pitch, yaw, *_) in enumerate(samples):
                bufs[i]["roll"].append(roll)
                bufs[i]["pitch"].append(pitch)
                bufs[i]["yaw"].append(yaw)

            for i, (lr, lp, ly) in enumerate(lines):
                lr.set_data(ts, bufs[i]["roll"])
                lp.set_data(ts, bufs[i]["pitch"])
                ly.set_data(ts, bufs[i]["yaw"])

            if len(ts) >= 2:
                xmin = max(0.0, ts[-1] - window_sec)
                axes[0][0].set_xlim(xmin, ts[-1])

            for i in range(n):
                all_y = (list(bufs[i]["roll"]) +
                         list(bufs[i]["pitch"]) +
                         list(bufs[i]["yaw"]))
                if all_y:
                    ymin, ymax = min(all_y), max(all_y)
                    pad = max(1.0, 0.1 * (ymax - ymin) if ymax > ymin else 1.0)
                    axes[i][0].set_ylim(ymin - pad, ymax + pad)

            fig.canvas.draw_idle()
            plt.pause(0.01)

    except Exception:
        pass
    finally:
        try:
            plt.close("all")
        except Exception:
            pass


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Auto-detecting N-IMU collector")
    ap.add_argument("--ports",   nargs="+", default=None)
    ap.add_argument("--baud",    default=DEFAULT_BAUD,  type=int)
    ap.add_argument("--hz",      default=LOG_HZ,        type=float)
    ap.add_argument("--no-plot", action="store_true",   help="Disable live plot")
    ap.add_argument("--window",  default=WINDOW_SEC,    type=float)
    ap.add_argument("--plot-hz", default=PLOT_HZ,       type=float)
    args = ap.parse_args()

    candidate_ports = args.ports if args.ports else find_ports()
    if not candidate_ports:
        print("No serial ports found. Plug in your Pico(s) and try again.")
        return

    # ── probe ─────────────────────────────────────────────────────────────────
    print(f"Found {len(candidate_ports)} port(s), probing for IMU data ({PROBE_SECS:.0f}s)...")
    probes = [ImuReader(p, args.baud, i) for i, p in enumerate(candidate_ports)]
    for r in probes:
        r.start()
    time.sleep(PROBE_SECS)

    active_ports = []
    for r in probes:
        r.stop()
        if r.error:
            print(f"  SKIP {r.port} — error: {r.error}")
        elif r.latest is None:
            print(f"  SKIP {r.port} — no data (REPL or unresponsive)")
        else:
            print(f"  OK   {r.port} — receiving data")
            active_ports.append(r.port)

    if not active_ports:
        print("\nNo active IMU ports found. Check your connections.")
        return

    n = len(active_ports)
    print(f"\n{n} active IMU(s):")
    for i, p in enumerate(active_ports):
        print(f"  imu{i}  →  {p}")

    # ── start reader threads ───────────────────────────────────────────────────
    readers = [ImuReader(p, args.baud, i) for i, p in enumerate(active_ports)]
    for r in readers:
        r.start()

    # Wait for first sample with timeout
    print("\nWaiting for all IMUs to send first sample...", end="", flush=True)
    deadline = time.time() + FIRST_SAMPLE_TO
    while any(r.latest is None for r in readers):
        if time.time() > deadline:
            missing = [active_ports[i] for i, r in enumerate(readers) if r.latest is None]
            print(f"\nTimeout waiting for: {missing}")
            print("Starting anyway with available data.")
            # Replace any still-None latest with zeros so logger never sees None
            for r in readers:
                if r.latest is None:
                    r.latest = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            break
        time.sleep(0.01)
    else:
        print(" ready.")

    # ── start logging thread ───────────────────────────────────────────────────
    log_path = next_log_path()
    print(f"\nLogging to: {log_path}  (Ctrl-C to stop)\n")

    logger = LoggingThread(readers, log_path, args.hz)
    logger.start()

    # ── live plot on main thread (or just wait for Ctrl-C) ────────────────────
    try:
        if not args.no_plot:
            run_plot(readers, active_ports, args.window, args.plot_hz)
        else:
            while logger.is_alive():
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        logger.stop()
        logger.join(timeout=2.0)
        for r in readers:
            r.stop()

    print(f"\n\nStopped. {logger.rows_written} rows saved to: {log_path}")


if __name__ == "__main__":
    main()
