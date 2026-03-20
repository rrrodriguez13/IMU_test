#!/usr/bin/env python3
"""
plotter.py - plot IMU log CSVs

    python3 plotter.py logs/imu_data000.csv
    python3 plotter.py logs/imu_data0*.csv --overlay
    python3 plotter.py logs/imu_data000.csv --y imu0_roll_deg,imu1_roll_deg
"""

import argparse
import glob
import os
import sys

import matplotlib.pyplot as plt

RPY_COLORS = {"roll": "tab:blue", "pitch": "tab:orange", "yaw": "tab:green"}


def load_csv(path):
    data = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().strip().split(",")
        if len(header) < 2:
            raise ValueError(f"{path}: bad header")
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


def detect_imu_indices(columns):
    indices = set()
    for col in columns:
        if col.startswith("imu") and "_" in col:
            try:
                indices.add(int(col.split("_")[0][3:]))
            except ValueError:
                pass
    return sorted(indices)


def get_rpy_cols(columns, imu_idx):
    if imu_idx is None:
        return "roll_deg", "pitch_deg", "yaw_deg"
    prefix = f"imu{imu_idx}_"
    roll  = next((c for c in columns if c == f"{prefix}roll_deg"),  None)
    pitch = next((c for c in columns if c == f"{prefix}pitch_deg"), None)
    yaw   = next((c for c in columns if c == f"{prefix}yaw_deg"),   None)
    return roll, pitch, yaw


def plot_file_auto(path, x_col, title):
    data = load_csv(path)
    cols = list(data.keys())

    if x_col not in data:
        raise KeyError(f"{path}: no column '{x_col}' (have: {cols})")

    x = data[x_col]
    imu_indices = detect_imu_indices(cols)

    if not imu_indices:
        if "roll_deg" in cols:
            imu_indices = [None]  # old single-imu format
        else:
            raise KeyError(f"{path}: no IMU columns found")

    n = len(imu_indices)
    fig, axes = plt.subplots(n, 1, sharex=True, figsize=(10, 3 * n), squeeze=False)
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
                print(f"warning: '{col}' not found, skipping")

        ax.set_title(label)
        ax.set_ylabel("Degrees")
        ax.legend(loc="upper right")
        ax.grid(True)

    axes[-1][0].set_xlabel(x_col)
    fig.tight_layout()


def plot_overlay(files, x_col, y_cols, title):
    fig, ax = plt.subplots()
    ax.set_title(title)
    ax.set_xlabel(x_col)
    ax.set_ylabel("value")
    ax.grid(True)

    for path in files:
        data = load_csv(path)
        if x_col not in data:
            raise KeyError(f"{path}: missing '{x_col}'")
        x = data[x_col]
        for y in y_cols:
            if y not in data:
                raise KeyError(f"{path}: missing '{y}'")
            ax.plot(x, data[y], label=f"{os.path.basename(path)}:{y}")

    ax.legend(loc="best")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--x", default="t_rel_s")
    ap.add_argument("--y", default=None, help="comma-separated columns")
    ap.add_argument("--overlay", action="store_true")
    ap.add_argument("--title", default="IMU Log")
    args = ap.parse_args()

    files = [f for f in expand_inputs(args.files) if os.path.exists(f)]
    if not files:
        print("no files found", file=sys.stderr)
        sys.exit(1)

    y_cols = [c.strip() for c in args.y.split(",")] if args.y else None

    if args.overlay:
        if not y_cols:
            data = load_csv(files[0])
            indices = detect_imu_indices(list(data.keys()))
            y_cols = []
            for idx in indices:
                rc, pc, yc = get_rpy_cols(list(data.keys()), idx)
                y_cols += [c for c in [rc, pc, yc] if c]
        plot_overlay(files, args.x, y_cols, args.title)
    else:
        if y_cols:
            for path in files:
                data = load_csv(path)
                x = data[args.x]
                fig, ax = plt.subplots()
                ax.set_title(f"{args.title} -- {os.path.basename(path)}")
                ax.set_xlabel(args.x)
                ax.set_ylabel("value")
                ax.grid(True)
                for y in y_cols:
                    if y not in data:
                        raise KeyError(f"{path}: missing '{y}'")
                    ax.plot(x, data[y], label=y)
                ax.legend(loc="best")
        else:
            for path in files:
                plot_file_auto(path, args.x, args.title)

    plt.show()


if __name__ == "__main__":
    main()
