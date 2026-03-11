import os
import serial
import time
import csv
from collections import deque

import matplotlib.pyplot as plt

PORT = "/dev/ttyACM0"
BAUD = 115200

PRINT_HZ = 24          # plot update rate
WINDOW_SEC = 10        # seconds visible on screen

LOG_DIR = "logs"
LOG_PREFIX = "imu_data"
LOG_DIGITS = 3         # 000..999
LOG_EXT = ".csv"

FLUSH_EVERY_N_ROWS = 20


def parse_csv_line(line: str):
    # Expect: roll,pitch,yaw,ax,ay,az
    parts = line.strip().split(",")
    if len(parts) != 6:
        return None
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        return None


def next_log_path() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    i = 0
    while True:
        path = os.path.join(LOG_DIR, f"{LOG_PREFIX}{i:0{LOG_DIGITS}d}{LOG_EXT}")
        if not os.path.exists(path):
            return path
        i += 1


def main():
    log_path = next_log_path()
    print(f"Connecting to {PORT} @ {BAUD}...\n")
    print(f"Logging to: {log_path}")

    # Buffers for plotting
    maxlen = max(10, int(WINDOW_SEC * PRINT_HZ))
    ts = deque(maxlen=maxlen)
    roll_buf = deque(maxlen=maxlen)
    pitch_buf = deque(maxlen=maxlen)
    yaw_buf = deque(maxlen=maxlen)

    # Matplotlib setup
    plt.ion()
    fig, ax = plt.subplots()
    (ln_roll,) = ax.plot([], [], label="roll (deg)")
    (ln_pitch,) = ax.plot([], [], label="pitch (deg)")
    (ln_yaw,) = ax.plot([], [], label="yaw (deg)")
    ax.set_title("BNO085 Roll / Pitch / Yaw (live)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Degrees")
    ax.legend(loc="upper right")
    ax.grid(True)

    period = 1.0 / PRINT_HZ
    last_update = 0.0
    t0 = time.time()
    latest = None

    rows_written = 0

    with serial.Serial(PORT, BAUD, timeout=1) as s, open(log_path, "w", newline="") as f:
        s.reset_input_buffer()

        writer = csv.writer(f)
        # You can remove ax/ay/az columns if you truly only want r/p/y
        writer.writerow(["unix_time", "t_rel_s", "roll_deg", "pitch_deg", "yaw_deg", "ax", "ay", "az"])
        f.flush()

        try:
            while True:
                raw = s.readline()
                if raw:
                    line = raw.decode("utf-8", errors="replace")
                    parsed = parse_csv_line(line)
                    if parsed:
                        latest = parsed

                now = time.time()
                if latest and (now - last_update) >= period:
                    last_update = now

                    roll, pitch, yaw, ax_, ay_, az_ = latest
                    t = now - t0

                    # Log row
                    writer.writerow([f"{now:.6f}", f"{t:.6f}", f"{roll:.4f}", f"{pitch:.4f}", f"{yaw:.4f}",
                                     f"{ax_:.6f}", f"{ay_:.6f}", f"{az_:.6f}"])
                    rows_written += 1
                    if rows_written % FLUSH_EVERY_N_ROWS == 0:
                        f.flush()

                    # Update plot buffers
                    ts.append(t)
                    roll_buf.append(roll)
                    pitch_buf.append(pitch)
                    yaw_buf.append(yaw)

                    # Update plot lines
                    ln_roll.set_data(ts, roll_buf)
                    ln_pitch.set_data(ts, pitch_buf)
                    ln_yaw.set_data(ts, yaw_buf)

                    # Scrolling X window
                    if len(ts) >= 2:
                        xmin = max(0.0, ts[-1] - WINDOW_SEC)
                        xmax = ts[-1]
                        ax.set_xlim(xmin, xmax)

                    # Auto Y scale (based on visible data)
                    all_y = list(roll_buf) + list(pitch_buf) + list(yaw_buf)
                    if all_y:
                        ymin = min(all_y)
                        ymax = max(all_y)
                        pad = max(1.0, 0.1 * (ymax - ymin) if ymax > ymin else 1.0)
                        ax.set_ylim(ymin - pad, ymax + pad)

                    fig.canvas.draw_idle()
                    plt.pause(0.001)

        except KeyboardInterrupt:
            pass
        finally:
            f.flush()

    print("\nStopped. Log saved to:", log_path)


if __name__ == "__main__":
    main()
