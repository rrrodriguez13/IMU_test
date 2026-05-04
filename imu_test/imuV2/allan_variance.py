#!/usr/bin/env python3
"""
allan_variance.py - Allan Deviation analysis of IMU log CSVs

Usage:
    python3 allan_variance.py 042
    python3 allan_variance.py 042 --cols imu0_ax,imu0_ay,imu0_az
    python3 allan_variance.py 042 --cols imu0_roll_deg --no-diff
    python3 allan_variance.py logs/imu_data070.csv

Angle columns (roll/pitch/yaw) are differentiated to gyro rates before
analysis.  Accel columns are used as-is.  Pass --no-diff to skip
differentiation for any column.
"""

import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── style ─────────────────────────────────────────────────────────────────────

CURVE_COLOR  = "#1565c0"   # deep blue for the ADEV curve
REGION_LEFT  = "#e3f2fd"   # light blue  — short-term noise
REGION_MID   = "#e8f5e9"   # light green — sweet spot
REGION_RIGHT = "#fce4ec"   # light red   — long-term drift

PRETTY_NAMES = {
    "imu0_roll_deg":  "IMU 0 — Roll",
    "imu0_pitch_deg": "IMU 0 — Pitch",
    "imu0_yaw_deg":   "IMU 0 — Yaw",
    "imu0_ax":        "IMU 0 — Accel X",
    "imu0_ay":        "IMU 0 — Accel Y",
    "imu0_az":        "IMU 0 — Accel Z",
    "imu1_roll_deg":  "IMU 1 — Roll",
    "imu1_pitch_deg": "IMU 1 — Pitch",
    "imu1_yaw_deg":   "IMU 1 — Yaw",
    "imu1_ax":        "IMU 1 — Accel X",
    "imu1_ay":        "IMU 1 — Accel Y",
    "imu1_az":        "IMU 1 — Accel Z",
}

def pretty(col):
    return PRETTY_NAMES.get(col, col)


# ── helpers ───────────────────────────────────────────────────────────────────

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
    return {k: np.array(v) for k, v in data.items()}


def allan_deviation(x, dt):
    """
    Overlapping Allan Deviation for a 1-D rate array x sampled at dt [s].
    Uses all overlapping cluster positions for better statistical confidence
    at long tau values — squeezes more information out of the same data.
    Returns (tau_array, adev_array).
    """
    N = len(x)
    theta = np.zeros(N + 1)
    theta[1:] = np.cumsum(x) * dt

    # extend to N//2 (vs N//4 for non-overlapping) for better long-tau coverage
    max_m = N // 2
    m_vals = np.unique(
        np.round(np.logspace(0, np.log10(max_m), 200)).astype(int)
    )
    m_vals = m_vals[(m_vals >= 1) & (m_vals <= max_m)]

    taus, adevs = [], []
    for m in m_vals:
        # overlapping: slide the cluster window one sample at a time
        n_terms = N - 2 * m
        if n_terms < 1:
            continue
        # vectorised second difference over all overlapping positions
        diff2 = theta[2*m:2*m+n_terms] - 2*theta[m:m+n_terms] + theta[:n_terms]
        tau  = m * dt
        avar = np.sum(diff2 ** 2) / (2 * tau ** 2 * n_terms)
        taus.append(tau)
        adevs.append(np.sqrt(avar))

    return np.array(taus), np.array(adevs)


def is_angle_col(name):
    return name.endswith("_deg")

def is_accel_col(name):
    return name.endswith(("_ax", "_ay", "_az"))

def detect_analysis_cols(columns):
    return [c for c in columns if is_angle_col(c) or is_accel_col(c)]

def differentiate(x, dt):
    dxdt = np.empty_like(x, dtype=float)
    dxdt[1:-1] = (x[2:] - x[:-2]) / (2 * dt)
    dxdt[0]    = (x[1]  - x[0])  / dt
    dxdt[-1]   = (x[-1] - x[-2]) / dt
    return dxdt


# ── plotting ──────────────────────────────────────────────────────────────────

def style_axes(ax):
    ax.set_facecolor("white")
    ax.tick_params(colors="#333333", labelsize=9)
    ax.xaxis.label.set_color("#333333")
    ax.yaxis.label.set_color("#333333")
    ax.title.set_color("#111111")
    for spine in ax.spines.values():
        spine.set_edgecolor("#cccccc")
    ax.grid(True, which="major", color="#e0e0e0", linewidth=0.8, linestyle="-")
    ax.grid(True, which="minor", color="#f0f0f0", linewidth=0.4, linestyle=":")


def draw_noise_regions(ax, taus, adev):
    xlim = (taus[0], taus[-1])
    ylim = ax.get_ylim()

    min_idx = np.argmin(adev)
    tau_min = taus[min_idx]
    band    = 0.3
    tau_lo  = tau_min * 10 ** (-band)
    tau_hi  = tau_min * 10 ** (+band)

    ax.axvspan(xlim[0], tau_lo,  alpha=1.0, color=REGION_LEFT,  zorder=0)
    ax.axvspan(tau_lo,  tau_hi,  alpha=1.0, color=REGION_MID,   zorder=0)
    ax.axvspan(tau_hi,  xlim[1], alpha=1.0, color=REGION_RIGHT, zorder=0)

    ax.set_xlim(xlim)
    ax.set_ylim(ylim)


def plot_adev(ax, taus, adev, col, unit, fname):
    ax.loglog(taus, adev, color=CURVE_COLOR, linewidth=2.5, zorder=3,
              solid_capstyle="round")

    min_idx     = np.argmin(adev)
    tau_m       = taus[min_idx]
    adev_m      = adev[min_idx]
    min_at_edge = min_idx >= int(0.8 * len(taus))

    dot_color = "#d32f2f" if min_at_edge else "#2e7d32"
    ax.scatter([tau_m], [adev_m], color=dot_color, s=90, zorder=6,
               edgecolors="white", linewidths=1.2)

    ax.set_xlabel("Averaging time (s)", fontsize=9)
    ax.set_ylabel(f"Error ({unit})", fontsize=9)
    ax.set_title(pretty(col), fontsize=11, fontweight="bold", pad=8)

    style_axes(ax)
    draw_noise_regions(ax, taus, adev)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Allan Deviation of IMU log data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "num",
        help="log file number (e.g. 042) or path (e.g. logs/imu_data042.csv)",
    )
    ap.add_argument(
        "--cols",
        default=None,
        help="comma-separated column names to analyse (default: all IMU cols)",
    )
    ap.add_argument(
        "--no-diff",
        action="store_true",
        help="skip differentiation even for angle columns",
    )
    args = ap.parse_args()

    # resolve file path — accept a bare number OR a direct path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate = args.num
    if os.path.exists(candidate):
        csv_path = os.path.abspath(candidate)
    elif os.path.exists(os.path.join(script_dir, candidate)):
        csv_path = os.path.join(script_dir, candidate)
    else:
        csv_path = os.path.join(script_dir, "logs", f"imu_data{candidate}.csv")
    if not os.path.exists(csv_path):
        print(f"error: file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    data = load_csv(csv_path)
    columns = list(data.keys())

    if "t_rel_s" not in data:
        print("error: no 't_rel_s' column found", file=sys.stderr)
        sys.exit(1)
    t  = data["t_rel_s"]
    dt = float(np.median(np.diff(t)))
    fs = 1.0 / dt
    print(f"File   : {os.path.basename(csv_path)}")
    print(f"Samples: {len(t)}   dt≈{dt*1e3:.2f} ms   fs≈{fs:.1f} Hz")

    if args.cols:
        sel_cols = [c.strip() for c in args.cols.split(",")]
        missing  = [c for c in sel_cols if c not in data]
        if missing:
            print(f"error: columns not found: {missing}", file=sys.stderr)
            sys.exit(1)
    else:
        sel_cols = detect_analysis_cols(columns)
        if not sel_cols:
            print("error: no IMU data columns detected", file=sys.stderr)
            sys.exit(1)

    print(f"Columns: {sel_cols}\n")

    n   = len(sel_cols)
    fig = plt.figure(figsize=(10, 4.5 * n), facecolor="white")
    fig.suptitle(
        f"IMU Stability  —  {os.path.basename(csv_path)}",
        fontsize=12, fontweight="bold", color="#111111", y=1.01,
    )

    for i, col in enumerate(sel_cols, 1):
        raw = data[col]

        if is_angle_col(col) and not args.no_diff:
            rate = differentiate(np.degrees(np.unwrap(np.radians(raw))), dt)
            unit = "deg/s"
        elif is_accel_col(col):
            rate = raw
            unit = "m/s²"
        else:
            rate = raw
            unit = "?"

        print(f"  computing {col} ...", end=" ", flush=True)
        taus, adev = allan_deviation(rate, dt)
        print("done")

        ax = fig.add_subplot(n, 1, i)
        plot_adev(ax, taus, adev, col, unit, os.path.basename(csv_path))

        min_idx = np.argmin(adev)
        print(f"    min ADEV = {adev[min_idx]:.4g} {unit}  @ τ = {taus[min_idx]:.3f} s")

    fig.tight_layout(rect=[0, 0, 1, 0.98])
    plt.show()


if __name__ == "__main__":
    main()
