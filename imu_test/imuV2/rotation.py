#!/usr/bin/env python3
"""
rotation_plot.py - visualize which axis a rotation happened around

    python3 rotation_plot.py logs/imu_data000.csv
    python3 rotation_plot.py logs/imu_data000.csv --imu 1
"""

import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

COLORS = {
    "roll":  "#1f77b4",
    "pitch": "#e07b00",
    "yaw":   "#2ca02c",
}


def load_csv(path):
    data = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().strip().split(",")
        for col in header:
            data[col.strip()] = []
        for line in f:
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
    return {k: np.array(v) for k, v in data.items()}


def draw_dial(ax, angle_deg, color, label):
    """Circular progress ring showing how much of 360° this axis swept."""
    circle = np.linspace(0, 2 * np.pi, 300)
    ax.plot(np.cos(circle), np.sin(circle),
            color="#e8e8e8", lw=10, solid_capstyle="round", zorder=1)

    fraction = min(abs(angle_deg) / 360.0, 1.0)
    if fraction > 0.005:
        arc = np.linspace(np.pi / 2, np.pi / 2 - 2 * np.pi * fraction, 300)
        ax.plot(np.cos(arc), np.sin(arc),
                color=color, lw=10, solid_capstyle="round", zorder=2)

    ax.text(0,  0.15, f"{abs(angle_deg):.0f}°",
            ha="center", va="center", fontsize=15, fontweight="bold", color=color)
    ax.text(0, -0.25, label,
            ha="center", va="center", fontsize=10, color="#555555")

    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect("equal")
    ax.axis("off")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--imu", type=int, default=0,
                    help="which IMU index to plot (default: 0)")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"error: {args.file} not found", file=sys.stderr)
        sys.exit(1)

    data = load_csv(args.file)
    idx  = args.imu

    for col in (f"imu{idx}_roll_deg", f"imu{idx}_pitch_deg", f"imu{idx}_yaw_deg"):
        if col not in data:
            print(f"error: column '{col}' not found", file=sys.stderr)
            sys.exit(1)

    t     = data["t_rel_s"]
    roll  = data[f"imu{idx}_roll_deg"]
    pitch = data[f"imu{idx}_pitch_deg"]
    yaw   = data[f"imu{idx}_yaw_deg"]

    # unwrap each axis so ±180° jumps don't break the range calculation
    def unwrap_deg(x):
        return np.degrees(np.unwrap(np.radians(x)))

    roll_u  = unwrap_deg(roll)
    pitch_u = unwrap_deg(pitch)
    yaw_u   = unwrap_deg(yaw)

    # normalise to start at 0 so the time series shows excursion from start
    roll_rel  = roll_u  - roll_u[0]
    pitch_rel = pitch_u - pitch_u[0]
    yaw_rel   = yaw_u   - yaw_u[0]

    # net angular displacement on each axis (end - start, on the unwrapped signal)
    roll_range  = float(abs(roll_u[-1]  - roll_u[0]))
    pitch_range = float(abs(pitch_u[-1] - pitch_u[0]))
    yaw_range   = float(abs(yaw_u[-1]   - yaw_u[0]))

    fig = plt.figure(figsize=(13, 5.5), facecolor="white")
    fig.suptitle(
        f"Rotation Analysis  —  {os.path.basename(args.file)}",
        fontsize=13, fontweight="bold",
    )

    gs = gridspec.GridSpec(1, 2, width_ratios=[2.2, 1],
                           left=0.06, right=0.97, wspace=0.06)

    # ── time series ──────────────────────────────────────────────────────────
    ax_ts = fig.add_subplot(gs[0])
    ax_ts.plot(t, roll_rel,  color=COLORS["roll"],  lw=1.5, label="Roll")
    ax_ts.plot(t, pitch_rel, color=COLORS["pitch"], lw=1.5, label="Pitch")
    ax_ts.plot(t, yaw_rel,   color=COLORS["yaw"],   lw=1.5, label="Yaw")
    ax_ts.axhline(0, color="#cccccc", lw=0.8, zorder=0)
    ax_ts.set_xlabel("Time (s)", fontsize=9)
    ax_ts.set_ylabel("Angle from start (°)", fontsize=9)
    ax_ts.legend(loc="upper right", fontsize=9, framealpha=0.9)
    ax_ts.set_facecolor("white")
    ax_ts.grid(True, color="#eeeeee")
    for spine in ax_ts.spines.values():
        spine.set_edgecolor("#cccccc")

    # ── rotation dials ───────────────────────────────────────────────────────
    gs_dials = gridspec.GridSpecFromSubplotSpec(
        3, 1, subplot_spec=gs[1], hspace=0.05,
    )
    for i, (rng, color, label) in enumerate([
        (roll_range,  COLORS["roll"],  "Roll"),
        (pitch_range, COLORS["pitch"], "Pitch"),
        (yaw_range,   COLORS["yaw"],   "Yaw"),
    ]):
        draw_dial(fig.add_subplot(gs_dials[i]), rng, color, label)

    plt.show()


if __name__ == "__main__":
    main()
