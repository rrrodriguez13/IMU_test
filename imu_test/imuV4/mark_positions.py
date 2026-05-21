#!/usr/bin/env python3
# mark_positions.py
# run this in a second terminal alongside imu_collect.py during a sweep test
# type the wheel angle and press Enter each time you settle at a new position
#
# automatically matches the number of the latest imu_data log:
#   imu_data002.csv  ->  marks/marks002.csv
#
#   python3 mark_positions.py
#   python3 mark_positions.py marks/marks005.csv  (override)

import argparse
import csv
import glob
import os
import re
import sys
import time

MARKS_DIR = "marks"
LOGS_DIR  = "logs"


def next_marks_path():
    os.makedirs(MARKS_DIR, exist_ok=True)
    imu_files = sorted(glob.glob(os.path.join(LOGS_DIR, "imu_data*.csv")))
    if imu_files:
        m = re.search(r"imu_data(\d+)\.csv", imu_files[-1])
        num = int(m.group(1)) if m else 0
    else:
        num = 0
    return os.path.join(MARKS_DIR, f"marks{num:03d}.csv")


ap = argparse.ArgumentParser()
ap.add_argument("outfile", nargs="?", default=None,
                help="output CSV (default: marks/marksNNN.csv matching latest log)")
args = ap.parse_args()
outfile = args.outfile if args.outfile else next_marks_path()

print(f"saving to {outfile}")
print("type the wheel angle (deg) and press Enter at each position  |  Ctrl-C to stop\n")

with open(outfile, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["unix_time", "angle_deg"])
    f.flush()

    count = 0
    try:
        while True:
            raw = input("angle: ").strip()
            t = time.time()
            if not raw:
                continue
            try:
                angle = float(raw)
            except ValueError:
                print("  not a number, skipping")
                continue
            writer.writerow([f"{t:.6f}", f"{angle:.2f}"])
            f.flush()
            count += 1
            print(f"  [{count}] marked {angle:.1f} deg\n")
    except (KeyboardInterrupt, EOFError):
        print(f"\ndone — {count} marks saved to {outfile}")
