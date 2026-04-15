#!/usr/bin/env python3
"""
plotter_accel.py - post-hoc IMU log viewer with accel + |a| magnitude

    python3 plotter_accel.py logs/imu_data000.csv
    python3 plotter_accel.py logs/imu_data000.csv --accel-only
    python3 plotter_accel.py logs/imu_data000.csv --angles-only
    python3 plotter_accel.py logs/imu_data0*.csv --overlay-mag
"""

import argparse
import glob
import math
import os
import sys

import matplotlib.pyplot as plt


def load_csv(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        header = [c.strip() for c in f.readline().split(",")]
        data = {c: [] for c in header}
        for line in f:
            parts = line.strip().split(",")
            if len(parts) != len(header):
                continue
            try:
                for col, val in zip(header, parts):
                    data[col].append(float(val))
            except ValueError:
                pass
    return data


def imu_indices(cols):
    seen = set()
    for c in cols:
        if c.startswith("imu") and "_" in c:
            try:
                seen.add(int(c.split("_")[0][3:]))
            except ValueError:
                pass
    return sorted(seen)


def rpy_cols(cols, i):
    p = f"imu{i}_"
    return (
        next((c for c in cols if c == f"{p}roll_deg"),  None),
        next((c for c in cols if c == f"{p}pitch_deg"), None),
        next((c for c in cols if c == f"{p}yaw_deg"),   None),
    )


def acc_cols(cols, i):
    p = f"imu{i}_"
    return (
        next((c for c in cols if c == f"{p}ax"), None),
        next((c for c in cols if c == f"{p}ay"), None),
        next((c for c in cols if c == f"{p}az"), None),
    )


def magnitude(data, ax, ay, az):
    return [math.sqrt(a**2 + b**2 + c**2)
            for a, b, c in zip(data[ax], data[ay], data[az])]


def angle_subplot(ax, x, data, cols, idx):
    rc, pc, yc = rpy_cols(cols, idx)
    for col, label, color in [
        (rc, "roll",  "tab:blue"),
        (pc, "pitch", "tab:orange"),
        (yc, "yaw",   "tab:green"),
    ]:
        if col and col in data:
            ax.plot(x, data[col], label=label, color=color, lw=1.4)
    ax.set_title(f"IMU {idx} — angles")
    ax.set_ylabel("deg")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True)


def accel_subplot(ax, x, data, cols, idx):
    axc, ayc, azc = acc_cols(cols, idx)
    for col, label, color in [
        (axc, "ax", "tab:red"),
        (ayc, "ay", "tab:purple"),
        (azc, "az", "tab:brown"),
    ]:
        if col and col in data:
            ax.plot(x, data[col], label=label, color=color, lw=1.2, alpha=0.7)
    if all(c and c in data for c in [axc, ayc, azc]):
        mag = magnitude(data, axc, ayc, azc)
        mean = sum(mag) / len(mag)
        ax.plot(x, mag, color="black", lw=1.8, ls="--", label="|a|")
        ax.axhline(mean, color="crimson", lw=1.2, ls=":", alpha=0.8,
                   label=f"mean {mean:.3f}")
    ax.set_title(f"IMU {idx} — accel")
    ax.set_ylabel("m/s²")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True)


def plot_full(path, x_col):
    data = load_csv(path)
    cols = list(data.keys())
    x = data[x_col]
    idxs = imu_indices(cols)
    n = len(idxs)

    fig, axes = plt.subplots(n * 2, 1, sharex=True,
                             figsize=(12, 4 * n * 2), squeeze=False)
    fig.suptitle(os.path.basename(path), fontsize=11)
    for row, idx in enumerate(idxs):
        angle_subplot(axes[row * 2][0],     x, data, cols, idx)
        accel_subplot(axes[row * 2 + 1][0], x, data, cols, idx)
    axes[-1][0].set_xlabel(x_col)
    fig.tight_layout()


def plot_angles(path, x_col):
    data = load_csv(path)
    cols = list(data.keys())
    x = data[x_col]
    idxs = imu_indices(cols)

    fig, axes = plt.subplots(len(idxs), 1, sharex=True,
                             figsize=(10, 3 * len(idxs)), squeeze=False)
    fig.suptitle(os.path.basename(path), fontsize=11)
    for row, idx in enumerate(idxs):
        angle_subplot(axes[row][0], x, data, cols, idx)
    axes[-1][0].set_xlabel(x_col)
    fig.tight_layout()


def plot_accel(path, x_col):
    data = load_csv(path)
    cols = list(data.keys())
    x = data[x_col]
    idxs = imu_indices(cols)

    fig, axes = plt.subplots(len(idxs), 1, sharex=True,
                             figsize=(10, 3 * len(idxs)), squeeze=False)
    fig.suptitle(os.path.basename(path), fontsize=11)
    for row, idx in enumerate(idxs):
        accel_subplot(axes[row][0], x, data, cols, idx)
    axes[-1][0].set_xlabel(x_col)
    fig.tight_layout()


def plot_overlay_mag(files, x_col):
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.set_title("|a| magnitude — overlay")
    ax.set_xlabel(x_col)
    ax.set_ylabel("m/s²")
    ax.grid(True)
    for path in files:
        data = load_csv(path)
        cols = list(data.keys())
        x = data[x_col]
        for idx in imu_indices(cols):
            axc, ayc, azc = acc_cols(cols, idx)
            if all(c and c in data for c in [axc, ayc, azc]):
                mag = magnitude(data, axc, ayc, azc)
                ax.plot(x, mag, lw=1.4,
                        label=f"{os.path.basename(path)} imu{idx}")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--x", default="t_rel_s")
    ap.add_argument("--angles-only", action="store_true")
    ap.add_argument("--accel-only",  action="store_true")
    ap.add_argument("--overlay-mag", action="store_true")
    args = ap.parse_args()

    paths = []
    for item in args.files:
        for p in (glob.glob(item) or [item]):
            if os.path.exists(p) and p not in paths:
                paths.append(p)

    if not paths:
        print("no files found", file=sys.stderr)
        sys.exit(1)

    if args.overlay_mag:
        plot_overlay_mag(paths, args.x)
    else:
        for path in paths:
            if args.angles_only:
                plot_angles(path, args.x)
            elif args.accel_only:
                plot_accel(path, args.x)
            else:
                plot_full(path, args.x)

    plt.show()


if __name__ == "__main__":
    main()
