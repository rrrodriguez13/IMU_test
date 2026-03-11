import serial
import time
import sys

PORT = "/dev/ttyACM0"
BAUD = 115200

PRINT_HZ = 24

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

    with serial.Serial(PORT, BAUD, timeout=1) as s:
        s.reset_input_buffer()

        period = 1.0 / PRINT_HZ
        last_print = 0.0
        latest = None

        while True:
            raw = s.readline()
            if raw:
                line = raw.decode("utf-8", errors="replace")
                parsed = parse_csv_line(line)
                if parsed:
                    latest = parsed

            now = time.time()
            if latest and (now - last_print) >= period:
                last_print = now
                roll, pitch, yaw, ax, ay, az = latest

                print(
                    f"roll: {roll:8.2f}    "
                    f"pitch: {pitch:8.2f}    "
                    f"yaw: {yaw:8.2f}"
                )
                sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
