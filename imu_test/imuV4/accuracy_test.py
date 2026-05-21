#!/usr/bin/env python3
# accuracy_test.py
# compare IMU readings against known ground-truth positions from a wheel sweep
#
#   python3 accuracy_test.py logs/imu_data002.csv marks.csv
#   python3 accuracy_test.py logs/imu_data002.csv marks.csv --col azimuth_deg
#   python3 accuracy_test.py logs/imu_data002.csv marks.csv --every 10

import argparse
import os
import re
import sys
import numpy as np
import matplotlib.pyplot as plt


def load_imu(path, every=1):
    data = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = [h.strip() for h in f.readline().strip().split(",")]
        for col in header:
            data[col] = []
        for i, line in enumerate(f):
            if i % every != 0:
                continue
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != len(header):
                continue
            try:
                for col, val in zip(header, parts):
                    data[col].append(float(val))
            except ValueError:
                continue
    return header, {k: np.array(v) for k, v in data.items()}


def load_marks(path):
    times, angles = [], []
    with open(path, "r") as f:
        header = f.readline()  # skip header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) != 2:
                continue
            try:
                times.append(float(parts[0]))
                angles.append(float(parts[1]))
            except ValueError:
                continue
    return np.array(times), np.array(angles)


ap = argparse.ArgumentParser()
ap.add_argument("imu_file")
ap.add_argument("marks_file", nargs="?", default=None,
                help="marks CSV (default: marks/marksNNN.csv matching the log number)")
ap.add_argument("--col", default="pitch_deg",
                help="IMU column to compare against (default: pitch_deg)")
ap.add_argument("--every", type=int, default=1)
args = ap.parse_args()

if args.marks_file is None:
    m = re.search(r"imu_data(\d+)\.csv", args.imu_file)
    num = int(m.group(1)) if m else 0
    args.marks_file = os.path.join("marks", f"marks{num:03d}.csv")

for f in [args.imu_file, args.marks_file]:
    if not os.path.exists(f):
        print(f"file not found: {f}", file=sys.stderr)
        sys.exit(1)

print(f"loading {args.imu_file} ...", flush=True)
header, imu = load_imu(args.imu_file, every=args.every)

if args.col not in imu:
    print(f"column '{args.col}' not found. available: {[c for c in header if c.endswith('_deg')]}", file=sys.stderr)
    sys.exit(1)

mark_times, mark_angles = load_marks(args.marks_file)
print(f"loaded {len(mark_times)} marks from {args.marks_file}")
if len(mark_times) == 0:
    print("error: no marks found — did mark_positions.py run during collection?", file=sys.stderr)
    sys.exit(1)

imu_times = imu["unix_time"]
imu_angles = np.degrees(np.unwrap(np.radians(imu[args.col])))

# for each mark, find the closest IMU sample by timestamp
imu_at_mark = []
for t in mark_times:
    idx = np.argmin(np.abs(imu_times - t))
    imu_at_mark.append(imu_angles[idx])
imu_at_mark = np.array(imu_at_mark)

# offset imu readings so the first mark aligns — removes mounting offset
offset = mark_angles[0] - imu_at_mark[0]
imu_at_mark_corrected = imu_at_mark + offset

errors = imu_at_mark_corrected - mark_angles

print(f"\nResults ({args.col}, offset corrected by {offset:.3f} deg):")
print(f"  {'Wheel (deg)':<14}  {'IMU (deg)':<14}  {'Error (deg)':<14}")
print(f"  {'-'*14}  {'-'*14}  {'-'*14}")
for w, m, e in zip(mark_angles, imu_at_mark_corrected, errors):
    print(f"  {w:<14.2f}  {m:<14.3f}  {e:+.3f}")

print(f"\n  RMS error : {np.sqrt(np.mean(errors**2)):.4f} deg")
print(f"  Max error : {np.max(np.abs(errors)):.4f} deg")
print(f"  Mean error: {np.mean(errors):+.4f} deg")

# detect forward vs backward passes based on angle direction
# split at the turning points (where direction reverses)
diffs = np.diff(mark_angles)
passes = [[0]]
for i, d in enumerate(diffs):
    if len(passes[-1]) > 1:
        prev_dir = mark_angles[passes[-1][-1]] - mark_angles[passes[-1][-2]]
        if (d > 0) != (prev_dir > 0):
            passes.append([])
    passes[-1].append(i + 1)

# ── figure 1: measured vs ground truth ───────────────────────────────────────
fig1, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), facecolor="white")
fig1.suptitle(
    f"IMU Accuracy Test  —  {os.path.basename(args.imu_file)}\n"
    f"{args.col}  |  {len(mark_times)} positions  |  offset corrected",
    fontsize=11, fontweight="bold"
)

colors = ["#1565c0", "#e07b00", "#2ca02c", "#c62828"]
for i, p in enumerate(passes):
    label = f"pass {i+1} ({'fwd' if i % 2 == 0 else 'bck'})"
    ax1.plot(mark_angles[p], imu_at_mark_corrected[p],
             "o-", color=colors[i % len(colors)], lw=1.5, ms=6, label=label)
    ax2.plot(mark_angles[p], errors[p],
             "o-", color=colors[i % len(colors)], lw=1.5, ms=6, label=label)

# ideal line
mn, mx = mark_angles.min(), mark_angles.max()
ax1.plot([mn, mx], [mn, mx], "--", color="#aaaaaa", lw=1, label="ideal (y=x)")
ax1.set_ylabel("IMU reading (deg)", fontsize=9)
ax1.set_title("IMU vs. Wheel", fontsize=10, fontweight="bold", loc="left")
ax1.legend(fontsize=8)
ax1.grid(True, color="#eeeeee")
ax1.set_facecolor("white")

ax2.axhline(0, color="#aaaaaa", lw=1, ls="--")
ax2.set_xlabel("Wheel angle (deg)", fontsize=9)
ax2.set_ylabel("Error: IMU − wheel (deg)", fontsize=9)
ax2.set_title("Error", fontsize=10, fontweight="bold", loc="left")
ax2.legend(fontsize=8)
ax2.grid(True, color="#eeeeee")
ax2.set_facecolor("white")

for ax in (ax1, ax2):
    for sp in ax.spines.values():
        sp.set_edgecolor("#cccccc")

fig1.tight_layout()

# ── figure 2: stats table ────────────────────────────────────────────────────
rows = [[f"{w:.1f}", f"{m:.3f}", f"{e:+.3f}"]
        for w, m, e in zip(mark_angles, imu_at_mark_corrected, errors)]

rms = np.sqrt(np.mean(errors**2))
rows.append(["—", "—", "—"])
rows.append(["RMS", "—", f"{rms:.4f}"])
rows.append(["Max |err|", "—", f"{np.max(np.abs(errors)):.4f}"])
rows.append(["Mean err", "—", f"{np.mean(errors):+.4f}"])

fig2, ax_t = plt.subplots(figsize=(7, 0.4 * len(rows) + 2), facecolor="white")
ax_t.axis("off")
fig2.suptitle(
    f"Accuracy Summary  —  {os.path.basename(args.imu_file)}  /  {os.path.basename(args.marks_file)}",
    fontsize=10, fontweight="bold"
)

tbl = ax_t.table(
    cellText=rows,
    colLabels=["Wheel (deg)", "IMU (deg)", "Error (deg)"],
    loc="center",
    cellLoc="center",
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(9)
tbl.scale(1, 1.6)

for (row, col), cell in tbl.get_celld().items():
    cell.set_edgecolor("#cccccc")
    if row == 0:
        cell.set_facecolor("#1565c0")
        cell.set_text_props(color="white", fontweight="bold")
    elif rows[row - 1][0] in ("RMS", "Max |err|", "Mean err", "—"):
        cell.set_facecolor("#e8f0fe")
    elif row % 2 == 0:
        cell.set_facecolor("#f0f4f8")
    else:
        cell.set_facecolor("white")

fig2.tight_layout()
plt.show()
