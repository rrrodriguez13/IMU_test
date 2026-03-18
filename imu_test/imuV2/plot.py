#!/usr/bin/env python3
"""
plotter.py  –  IMU log plotter
==============================
Auto-detects how many IMUs are in the CSV and plots one subplot per IMU,
with roll/pitch/yaw as separate coloured lines within each subplot.

Usage
-----
    python3 plotter.py logs/imu_data000.csv
    python3 plotter.py logs/imu_data0*.csv --overlay
    python3 plotter.py logs/imu_data000.csv --x t_rel_s --y imu0_roll_deg,imu1_roll_deg
"""

import argparse
import glob
import os
import sys

import matplotlib.pyplot as plt

# Colours for roll / pitch / yaw within each subplot
RPY_COLORS = {"roll": "tab:blue", "pitch": "tab:orange", "yaw": "tab:green"}


def load_csv(path: str):
    data = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().strip().split(",")
        if len(header) < 2:
            raise ValueError(f"{path}: missing/invalid header")
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
    return data


def expand_inputs(inputs):
    paths, seen = [], set()
    for item in inputs:
        for p in (glob.glob(item) or [item]):
            if p not in seen:
                paths.append(p)
                seen.add(p)
    return paths


def detect_imu_indices(columns: list[str]) -> list[int]:
    """Return sorted list of IMU indices found in column names."""
    indices = set()
    for col in columns:
        if col.startswith("imu") and "_" in col:
            try:
                indices.add(int(col.split("_")[0][3:]))
            except ValueError:
                pass
    # Fall back to legacy single-IMU columns (roll_deg, pitch_deg, yaw_deg)
    return sorted(indices)


def get_rpy_cols(columns: list[str], imu_idx: int | None):
    """Return (roll_col, pitch_col, yaw_col) for a given IMU index, or legacy names."""
    if imu_idx is None:
        # legacy single-IMU CSV
        return "roll_deg", "pitch_deg", "yaw_deg"
    prefix = f"imu{imu_idx}_"
    roll  = next((c for c in columns if c == f"{prefix}roll_deg"),  None)
    pitch = next((c for c in columns if c == f"{prefix}pitch_deg"), None)
    yaw   = next((c for c in columns if c == f"{prefix}yaw_deg"),   None)
    return roll, pitch, yaw


def plot_file_auto(path: str, x_col: str, title: str):
    """One figure per file, one subplot per IMU, roll/pitch/yaw coloured lines."""
    data = load_csv(path)
    cols = list(data.keys())

    if x_col not in data:
        raise KeyError(f"{path}: missing x column '{x_col}'. Columns: {cols}")

    x = data[x_col]
    imu_indices = detect_imu_indices(cols)

    # Fall back to legacy column names if no imu0_ prefix found
    if not imu_indices:
        if "roll_deg" in cols:
            imu_indices = [None]   # sentinel for legacy
        else:
            raise KeyError(f"{path}: no IMU columns found. Columns: {cols}")

    n = len(imu_indices)
    fig, axes = plt.subplots(n, 1, sharex=True,
                             figsize=(10, 3 * n),
                             squeeze=False)
    fig.suptitle(f"{title} — {os.path.basename(path)}")

    for row, idx in enumerate(imu_indices):
        ax = axes[row][0]
        roll_col, pitch_col, yaw_col = get_rpy_cols(cols, idx)
        label = f"IMU {idx}" if idx is not None else "IMU"

        for col, name, color in [
            (roll_col,  "roll",  RPY_COLORS["roll"]),
            (pitch_col, "pitch", RPY_COLORS["pitch"]),
            (yaw_col,   "yaw",   RPY_COLORS["yaw"]),
        ]:
            if col and col in data:
                ax.plot(x, data[col], label=name, color=color)
            else:
                print(f"WARNING: column '{col}' not found, skipping.")

        ax.set_title(label)
        ax.set_ylabel("Degrees")
        ax.legend(loc="upper right")
        ax.grid(True)

    axes[-1][0].set_xlabel(x_col)
    fig.tight_layout()


def plot_overlay(files: list[str], x_col: str, y_cols: list[str], title: str):
    """All files on one axes with explicit --y columns."""
    fig, ax = plt.subplots()
    ax.set_title(title)
    ax.set_xlabel(x_col)
    ax.set_ylabel("value")
    ax.grid(True)

    for path in files:
        data = load_csv(path)
        if x_col not in data:
            raise KeyError(f"{path}: missing x column '{x_col}'")
        x = data[x_col]
        for y in y_cols:
            if y not in data:
                raise KeyError(f"{path}: missing y column '{y}'. Columns: {list(data.keys())}")
            ax.plot(x, data[y], label=f"{os.path.basename(path)}:{y}")

    ax.legend(loc="best")


def main():
    ap = argparse.ArgumentParser(description="Plot IMU log CSV files.")
    ap.add_argument("files", nargs="+",
                    help='Files or globs, e.g. logs/imu_data000.csv "logs/*.csv"')
    ap.add_argument("--x", default="t_rel_s",
                    help="X-axis column (default: t_rel_s)")
    ap.add_argument("--y", default=None,
                    help="Comma-separated Y columns (default: auto-detect roll/pitch/yaw per IMU)")
    ap.add_argument("--overlay", action="store_true",
                    help="Overlay all files on one axes (requires --y)")
    ap.add_argument("--title", default="IMU Log",
                    help="Figure title (default: IMU Log)")
    args = ap.parse_args()

    files = [f for f in expand_inputs(args.files) if os.path.exists(f)]
    if not files:
        print("No existing files matched your inputs.", file=sys.stderr)
        sys.exit(1)

    y_cols = [c.strip() for c in args.y.split(",")] if args.y else None

    if args.overlay:
        if not y_cols:
            # Auto-build overlay columns from first file
            data = load_csv(files[0])
            indices = detect_imu_indices(list(data.keys()))
            y_cols = []
            for idx in indices:
                rc, pc, yc = get_rpy_cols(list(data.keys()), idx)
                y_cols += [c for c in [rc, pc, yc] if c]
        plot_overlay(files, args.x, y_cols, args.title)
    else:
        if y_cols:
            # Explicit columns requested — one figure per file, single subplot
            for path in files:
                data = load_csv(path)
                if args.x not in data:
                    raise KeyError(f"{path}: missing x column '{args.x}'")
                x = data[args.x]
                fig, ax = plt.subplots()
                ax.set_title(f"{args.title} — {os.path.basename(path)}")
                ax.set_xlabel(args.x)
                ax.set_ylabel("value")
                ax.grid(True)
                for y in y_cols:
                    if y not in data:
                        raise KeyError(f"{path}: missing y column '{y}'. Columns: {list(data.keys())}")
                    ax.plot(x, data[y], label=y)
                ax.legend(loc="best")
        else:
            # Auto mode — one subplot per IMU
            for path in files:
                plot_file_auto(path, args.x, args.title)

    plt.show()


if __name__ == "__main__":
    main()
