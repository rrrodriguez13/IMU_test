import serial
import time
from collections import deque

import matplotlib.pyplot as plt

PORT = "/dev/ttyACM0"
BAUD = 115200

PRINT_HZ = 24          # plot update rate
WINDOW_SEC = 10        # seconds visible on screen


def parse_csv_line(line: str):
    # Expect: roll,pitch,yaw,ax,ay,az
    parts = line.strip().split(",")
    if len(parts) != 6:
        return None
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        return None


def main():
    print(f"Connecting to {PORT} @ {BAUD}...\n")

    # Buffers (time + 3 signals), sized to hold WINDOW_SEC at PRINT_HZ
    maxlen = max(10, int(WINDOW_SEC * PRINT_HZ))
    ts = deque(maxlen=maxlen)
    roll_buf = deque(maxlen=maxlen)
    pitch_buf = deque(maxlen=maxlen)
    yaw_buf = deque(maxlen=maxlen)

    # --- Matplotlib setup ---
    plt.ion()
    plt.style.use('bmh')
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

    with serial.Serial(PORT, BAUD, timeout=1) as s:
        s.reset_input_buffer()

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

                ts.append(t)
                roll_buf.append(roll)
                pitch_buf.append(pitch)
                yaw_buf.append(yaw)

                # Update plot data
                ln_roll.set_data(ts, roll_buf)
                ln_pitch.set_data(ts, pitch_buf)
                ln_yaw.set_data(ts, yaw_buf)

                # Keep a scrolling window in X
                if len(ts) >= 2:
                    xmin = max(0.0, ts[-1] - WINDOW_SEC)
                    xmax = ts[-1]
                    ax.set_xlim(xmin, xmax)

                # Auto-scale Y to current visible data (simple + robust)
                all_y = list(roll_buf) + list(pitch_buf) + list(yaw_buf)
                if all_y:
                    ymin = min(all_y)
                    ymax = max(all_y)
                    pad = max(1.0, 0.1 * (ymax - ymin) if ymax > ymin else 1.0)
                    ax.set_ylim(ymin - pad, ymax + pad)

                fig.canvas.draw_idle()
                plt.pause(0.001)  # allows GUI to update


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
