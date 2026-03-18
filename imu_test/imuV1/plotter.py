#!/usr/bin/env python3
import argparse
import glob
import os
import sys

import matplotlib.pyplot as plt


def load_csv(path: str):
    """
    Loads a log CSV with header like:
      unix_time,t_rel_s,roll_deg,pitch_deg,yaw_deg,ax,ay,az
    Returns: dict of column -> list[float]
    """
    data = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().strip().split(",")
        if len(header) < 2:
            raise ValueError(f"{path}: missing/invalid header")

        # init lists
        for col in header:
            col = col.strip()
            data[col] = []

        # rows
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
                # skip malformed line
                continue

    return data


def expand_inputs(inputs):
    """Expand globs and keep explicit paths."""
    paths = []
    for item in inputs:
        matches = glob.glob(item)
        if matches:
            paths.extend(matches)
        else:
            paths.append(item)
    # Dedup while preserving order
    out = []
    seen = set()
    for p in paths:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Plot IMU log CSV files (roll/pitch/yaw etc.)."
    )
    ap.add_argument(
        "files",
        nargs="+",
        help='Files or globs, e.g. logs/imu_data000.csv logs/imu_data0*.csv "logs/*.csv"',
    )
    ap.add_argument(
        "--x",
        default="t_rel_s",
        help="X-axis column (default: t_rel_s). Common: t_rel_s or unix_time",
    )
    ap.add_argument(
        "--y",
        default="roll_deg,pitch_deg,yaw_deg",
        help="Comma-separated Y columns to plot (default: roll_deg,pitch_deg,yaw_deg)",
    )
    ap.add_argument(
        "--overlay",
        action="store_true",
        help="Overlay multiple files on the same axes (default: separate figures per file).",
    )
    ap.add_argument(
        "--title",
        default="IMU Log Plot",
        help="Figure title (default: IMU Log Plot).",
    )
    args = ap.parse_args()

    files = expand_inputs(args.files)
    files = [f for f in files if os.path.exists(f)]

    if not files:
        print("No existing files matched your inputs.", file=sys.stderr)
        sys.exit(1)

    y_cols = [c.strip() for c in args.y.split(",") if c.strip()]

    if args.overlay:
        fig, ax = plt.subplots()
        ax.set_title(args.title)
        ax.set_xlabel(args.x)
        ax.set_ylabel("value")
        ax.grid(True)

        for path in files:
            data = load_csv(path)
            if args.x not in data:
                raise KeyError(f"{path}: missing x column '{args.x}'. Columns: {list(data.keys())}")

            x = data[args.x]
            for y in y_cols:
                if y not in data:
                    raise KeyError(f"{path}: missing y column '{y}'. Columns: {list(data.keys())}")
                # label includes file so you can tell them apart
                label = f"{os.path.basename(path)}:{y}"
                ax.plot(x, data[y], label=label)

        ax.legend(loc="best")
        plt.show()

    else:
        # One figure per file
        for path in files:
            data = load_csv(path)

            if args.x not in data:
                raise KeyError(f"{path}: missing x column '{args.x}'. Columns: {list(data.keys())}")

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

        plt.show()


if __name__ == "__main__":
    main()
