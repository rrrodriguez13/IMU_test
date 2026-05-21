#!/usr/bin/env python3
# drift_analysis.py
# plot angle drift over time from a static imu log + pop up a stats table
#
#   python3 drift_analysis.py logs/imu_data001.csv
#   python3 drift_analysis.py logs/imu_data001.csv --every 100
#   python3 drift_analysis.py logs/imu_data001.csv --cols elevation_deg,azimuth_deg

import argparse
import os
import sys
import numpy as np
import matplotlib.pyplot as plt


NAMES = {
    "elevation_deg":  "Elevation",
    "azimuth_deg":    "Azimuth",
    "imu0_roll_deg":  "IMU 0 Roll",
    "imu0_pitch_deg": "IMU 0 Pitch",
    "imu0_yaw_deg":   "IMU 0 Yaw",
    "imu1_roll_deg":  "IMU 1 Roll",
    "imu1_pitch_deg": "IMU 1 Pitch",
    "imu1_yaw_deg":   "IMU 1 Yaw",
}

COLORS = ["#1565c0", "#e07b00", "#2ca02c", "#c62828",
          "#7b1fa2", "#00838f", "#558b2f", "#6d4c41"]


def load_csv(path, every=1):
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


ap = argparse.ArgumentParser()
ap.add_argument("file")
ap.add_argument("--cols", default=None)
ap.add_argument("--every", type=int, default=1)
args = ap.parse_args()

if not os.path.exists(args.file):
    print(f"file not found: {args.file}", file=sys.stderr)
    sys.exit(1)

print(f"loading {args.file} ...", flush=True)
header, data = load_csv(args.file, every=args.every)

t = data["t_rel_s"]
t_h = t / 3600.0
duration_h = (t[-1] - t[0]) / 3600.0
dt = float(np.median(np.diff(t)))
print(f"{len(t)} samples  |  {duration_h:.2f} h  |  dt={dt*1e3:.1f} ms")

if args.cols:
    cols = [c.strip() for c in args.cols.split(",")]
else:
    cols = [c for c in header if c.endswith("_deg")]

# unwrap and fit a line to each column
results = []
for col in cols:
    x = np.degrees(np.unwrap(np.radians(data[col])))
    slope, intercept = np.polyfit(t, x, 1)
    fit = slope * t + intercept
    rms = np.std(x - fit)
    start = x[:10].mean()
    end = x[-10:].mean()
    results.append({
        "col":   col,
        "x":     x,
        "fit":   fit,
        "slope": slope,
        "rms":   rms,
        "start": start,
        "end":   end,
        "total": end - start,
    })
    print(f"  {col:<22}  {slope*3600:+.4f} deg/hr   total {end-start:+.4f} deg   rms {rms:.4f} deg")

# ── figure 1: time series ────────────────────────────────────────────────────
n = len(results)
fig1, axes = plt.subplots(n, 1, figsize=(11, 3 * n), sharex=True, facecolor="white")
if n == 1:
    axes = [axes]

fig1.suptitle(
    f"IMU Drift  —  {os.path.basename(args.file)}  ({duration_h:.1f} h)",
    fontsize=11, fontweight="bold"
)

for i, r in enumerate(results):
    ax = axes[i]
    ax.plot(t_h, r["x"],   color=COLORS[i % len(COLORS)], lw=0.8, alpha=0.6, label="measured")
    ax.plot(t_h, r["fit"], color="#333333", lw=1.5, ls="--", label=f"fit  {r['slope']*3600:+.4f} °/hr")
    ax.set_ylabel("deg", fontsize=9)
    ax.set_title(NAMES.get(r["col"], r["col"]), fontsize=10, fontweight="bold", loc="left", pad=4)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, color="#eeeeee", lw=0.8)
    ax.set_facecolor("white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#cccccc")

axes[-1].set_xlabel("Time (hours)", fontsize=9)
fig1.tight_layout()

# ── figure 2: stats table ────────────────────────────────────────────────────
col_labels = ["Signal", "Start (°)", "End (°)", "Total Drift (°)", "Rate (°/hr)", "Noise RMS (°)"]
rows = [
    [
        NAMES.get(r["col"], r["col"]),
        f"{r['start']:.3f}",
        f"{r['end']:.3f}",
        f"{r['total']:+.4f}",
        f"{r['slope']*3600:+.4f}",
        f"{r['rms']:.4f}",
    ]
    for r in results
]

fig2, ax2 = plt.subplots(figsize=(10, 0.5 * n + 1.5), facecolor="white")
ax2.axis("off")
fig2.suptitle(
    f"Drift Summary  —  {os.path.basename(args.file)}  ({duration_h:.1f} h  |  {len(t):,} samples)",
    fontsize=10, fontweight="bold"
)

tbl = ax2.table(
    cellText=rows,
    colLabels=col_labels,
    loc="center",
    cellLoc="center",
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(9)
tbl.scale(1, 1.8)

for (row, col), cell in tbl.get_celld().items():
    cell.set_edgecolor("#cccccc")
    if row == 0:
        cell.set_facecolor("#1565c0")
        cell.set_text_props(color="white", fontweight="bold")
    elif row % 2 == 0:
        cell.set_facecolor("#f0f4f8")
    else:
        cell.set_facecolor("white")

fig2.tight_layout()
plt.show()
