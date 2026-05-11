#!/usr/bin/env python3
"""
allan_variance.py - Allan deviation analysis of imuV4 pointing angle logs

    python3 allan_variance.py logs/imu_data000.csv
    python3 allan_variance.py logs/imu_data000.csv --cols elevation_deg,azimuth_deg
    python3 allan_variance.py logs/imu_data000.csv --cols imu0_roll_deg,imu1_roll_deg

Produces two figures:

  Fig 1 — Rate ADEV  (deg/s)
    The angle is differentiated to angular rate, then the standard overlapping
    Allan deviation is computed.  This is the classic IMU noise characterisation:
      slope −½  →  angle random walk (sensor noise floor)
      slope  0  →  bias instability (the minimum of the curve)
      slope +½  →  rate random walk (long-term drift growth)
    The minimum ADEV value (deg/s) × any time window (s) ≈ worst-case pointing
    error from bias drift over that window.

  Fig 2 — Angle ADEV  (deg)
    The angle is used directly as the phase signal (no differentiation).
    Units are degrees, so the curve directly reads as:
    "at averaging time τ, the pointing is uncertain by this many degrees."
      flat curve   →  measurement jitter, but pointing is stable
      slope +½     →  pointing drifts as √time (random walk)
      steep rise   →  significant long-term drift
    Note: the second-difference formula cancels any constant drift rate,
    so only time-varying drift components appear here.
"""

import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt


LABEL = {
    "elevation_deg":  "Elevation",
    "azimuth_deg":    "Azimuth",
    "imu0_roll_deg":  "IMU 0  Roll",
    "imu0_pitch_deg": "IMU 0  Pitch",
    "imu0_yaw_deg":   "IMU 0  Yaw",
    "imu1_roll_deg":  "IMU 1  Roll",
    "imu1_pitch_deg": "IMU 1  Pitch",
    "imu1_yaw_deg":   "IMU 1  Yaw",
    "imu0_ax": "IMU 0  Accel X",
    "imu0_ay": "IMU 0  Accel Y",
    "imu0_az": "IMU 0  Accel Z",
    "imu1_ax": "IMU 1  Accel X",
    "imu1_ay": "IMU 1  Accel Y",
    "imu1_az": "IMU 1  Accel Z",
}


# ── CSV loader ────────────────────────────────────────────────────────────────

def load_csv(path, every=1):
    data = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header = f.readline().strip().split(",")
        if len(header) < 2:
            raise ValueError(f"{path}: bad header")
        for col in header:
            data[col.strip()] = []
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
    return {k: np.array(v) for k, v in data.items()}


# ── signal helpers ────────────────────────────────────────────────────────────

def differentiate(x, dt):
    dx = np.empty_like(x, dtype=float)
    dx[1:-1] = (x[2:] - x[:-2]) / (2 * dt)
    dx[0]    = (x[1] - x[0]) / dt
    dx[-1]   = (x[-1] - x[-2]) / dt
    return dx


def unwrap_deg(x):
    return np.degrees(np.unwrap(np.radians(x)))


def cluster_sizes(N):
    max_m = N // 2
    ms = np.unique(np.round(np.logspace(0, np.log10(max_m), 200)).astype(int))
    return ms[(ms >= 1) & (ms <= max_m)]


# ── Allan deviation variants ──────────────────────────────────────────────────

def adev_rate(rate, dt):
    """
    Standard overlapping ADEV.  Treats `rate` as angular rate (deg/s), integrates
    to get phase, then applies the second-difference formula.
    Returns (tau, adev) in seconds and deg/s.
    """
    N = len(rate)
    theta = np.zeros(N + 1)
    theta[1:] = np.cumsum(rate) * dt

    taus, adevs = [], []
    for m in cluster_sizes(N):
        n = N - 2 * m
        if n < 1:
            continue
        d2 = theta[2*m:2*m+n] - 2*theta[m:m+n] + theta[:n]
        tau = m * dt
        taus.append(tau)
        adevs.append(np.sqrt(np.sum(d2**2) / (2 * tau**2 * n)))

    return np.array(taus), np.array(adevs)


def adev_angle(angle, dt):
    """
    Angle-phase ADEV.  Uses `angle` (deg) directly as the phase signal — no
    integration step.  The formula is the same second-difference but WITHOUT
    dividing by tau², so the result has units of degrees.
    Returns (tau, adev) in seconds and degrees.
    """
    N = len(angle)

    taus, adevs = [], []
    for m in cluster_sizes(N):
        n = N - 2 * m
        if n < 1:
            continue
        d2 = angle[2*m:2*m+n] - 2*angle[m:m+n] + angle[:n]
        taus.append(m * dt)
        adevs.append(np.sqrt(np.sum(d2**2) / (2 * n)))

    return np.array(taus), np.array(adevs)


# ── column selection ──────────────────────────────────────────────────────────

def default_cols(columns):
    pointing = [c for c in ("elevation_deg", "azimuth_deg") if c in columns]
    if pointing:
        return pointing
    return [c for c in columns
            if c.endswith("_deg") or c.endswith(("_ax", "_ay", "_az"))]


# ── plotting helpers ──────────────────────────────────────────────────────────

def slope_guide(ax, taus, adev, slope, label):
    ref_tau  = np.exp(0.5 * (np.log(taus[0]) + np.log(taus[-1])))
    ref_adev = np.exp(np.interp(np.log(ref_tau), np.log(taus), np.log(adev)))
    t = np.array([taus[0], taus[-1]])
    y = ref_adev * (t / ref_tau) ** slope
    ax.plot(t, y, color="#cccccc", lw=0.9, ls="--", zorder=1)
    # label at the left end, offset slightly above
    ax.text(t[0] * 1.6, y[0] * 1.35, label, fontsize=7, color="#aaaaaa", ha="left")


def annotate_min(ax, taus, adev, unit):
    i = np.argmin(adev)
    tm, am = taus[i], adev[i]
    ax.scatter([tm], [am], color="#c62828", s=55, edgecolors="white", lw=1.0, zorder=5)
    ax.annotate(
        f"min  {am:.3g} {unit}\nτ = {tm:.2g} s",
        xy=(tm, am), xytext=(tm * 4, am * 1.8),
        fontsize=7.5, color="#c62828",
        arrowprops=dict(arrowstyle="->", color="#c62828", lw=0.8),
    )


def style_ax(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.grid(True, which="major", color="#e0e0e0", lw=0.8)
    ax.grid(True, which="minor", color="#f2f2f2", lw=0.4, ls=":")
    ax.set_facecolor("white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#cccccc")


def panel_rate(ax, taus, adev, col):
    ax.loglog(taus, adev, color="#1565c0", lw=2, solid_capstyle="round", zorder=3)
    for slope, lbl in [(-0.5, "−½"), (0.0, "  0"), (0.5, "+½")]:
        slope_guide(ax, taus, adev, slope, lbl)
    annotate_min(ax, taus, adev, "deg/s")
    style_ax(ax,
             xlabel="Averaging time  τ  (s)",
             ylabel="ADEV  (deg/s)",
             title=LABEL.get(col, col))


def panel_angle(ax, taus, adev, col):
    ax.loglog(taus, adev, color="#e07b00", lw=2, solid_capstyle="round", zorder=3)
    for slope, lbl in [(0.0, "  0  (stable)"), (0.5, "+½  (random walk)")]:
        slope_guide(ax, taus, adev, slope, lbl)
    # Mark the value at a few key timescales instead of the minimum,
    # since this curve is usually monotonically non-decreasing.
    for tau_target in [1.0, 10.0, 60.0]:
        if taus[0] <= tau_target <= taus[-1]:
            val = np.exp(np.interp(np.log(tau_target), np.log(taus), np.log(adev)))
            ax.scatter([tau_target], [val], color="#555555", s=30,
                       edgecolors="white", lw=0.8, zorder=5)
            ax.annotate(
                f"{val:.3g}°\nτ={tau_target:.0f}s",
                xy=(tau_target, val), xytext=(tau_target * 2.2, val * 0.6),
                fontsize=7, color="#555555",
                arrowprops=dict(arrowstyle="->", color="#aaaaaa", lw=0.7),
            )
    style_ax(ax,
             xlabel="Averaging time  τ  (s)",
             ylabel="ADEV  (deg)",
             title=LABEL.get(col, col))


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Allan deviation of imuV4 pointing log")
    ap.add_argument("file", help="path to the imuV4 CSV log")
    ap.add_argument("--cols", default=None,
                    help="comma-separated columns (default: elevation_deg, azimuth_deg)")
    ap.add_argument("--every", type=int, default=1, metavar="N",
                    help="use every Nth row (e.g. --every 10 for large files; increases min tau by N)")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"error: {args.file} not found", file=sys.stderr)
        sys.exit(1)

    data = load_csv(args.file, every=args.every)
    columns = list(data.keys())

    if "t_rel_s" not in data:
        print("error: no 't_rel_s' column", file=sys.stderr)
        sys.exit(1)

    t  = data["t_rel_s"]
    dt = float(np.median(np.diff(t)))
    fname = os.path.basename(args.file)
    print(f"File   : {fname}")
    print(f"Samples: {len(t)}   dt ≈ {dt*1e3:.2f} ms   fs ≈ {1/dt:.1f} Hz")

    if args.cols:
        sel_cols = [c.strip() for c in args.cols.split(",")]
        missing  = [c for c in sel_cols if c not in data]
        if missing:
            print(f"error: columns not found: {missing}", file=sys.stderr)
            sys.exit(1)
    else:
        sel_cols = default_cols(columns)
        if not sel_cols:
            print("error: no suitable columns found", file=sys.stderr)
            sys.exit(1)

    print(f"Columns: {sel_cols}\n")

    n = len(sel_cols)

    fig1, ax1s = plt.subplots(n, 1, figsize=(9, 4.5 * n), facecolor="white", squeeze=False)
    fig1.suptitle(
        f"Fig 1 — Rate ADEV  ({fname})\n"
        "angle → d/dt → deg/s → standard overlapping ADEV\n"
        "minimum = bias instability;  slope −½ = noise floor;  slope +½ = drift growth",
        fontsize=9, fontweight="bold", y=1.0,
    )

    fig2, ax2s = plt.subplots(n, 1, figsize=(9, 4.5 * n), facecolor="white", squeeze=False)
    fig2.suptitle(
        f"Fig 2 — Angle ADEV  ({fname})\n"
        "angle used directly as phase — no differentiation\n"
        "y-axis in degrees: read directly as pointing uncertainty at each averaging time τ",
        fontsize=9, fontweight="bold", y=1.0,
    )

    for i, col in enumerate(sel_cols):
        raw       = data[col]
        is_angle  = col.endswith("_deg")
        is_accel  = col.endswith(("_ax", "_ay", "_az"))

        # ── Fig 1: rate ADEV ─────────────────────────────────────────────────
        print(f"  [{col}]  rate ADEV ...", end=" ", flush=True)
        if is_angle:
            rate  = differentiate(unwrap_deg(raw), dt)
            unit1 = "deg/s"
        else:
            rate  = raw
            unit1 = "m/s²" if is_accel else "?"
        taus1, adev1 = adev_rate(rate, dt)
        mi = np.argmin(adev1)
        print(f"min {adev1[mi]:.4g} {unit1}  @ τ = {taus1[mi]:.3g} s")
        panel_rate(ax1s[i][0], taus1, adev1, col)
        # override ylabel for accel
        if is_accel:
            ax1s[i][0].set_ylabel(f"ADEV  ({unit1})", fontsize=9)

        # ── Fig 2: angle ADEV (only for angle columns) ───────────────────────
        if is_angle:
            print(f"  [{col}]  angle ADEV ...", end=" ", flush=True)
            taus2, adev2 = adev_angle(unwrap_deg(raw), dt)
            print(f"value at τ=1s ≈ {np.exp(np.interp(np.log(max(1.0, taus2[0])), np.log(taus2), np.log(adev2))):.4g}°")
            panel_angle(ax2s[i][0], taus2, adev2, col)
        else:
            # Accel columns don't have a meaningful angle-ADEV; just note that
            ax2 = ax2s[i][0]
            taus2, adev2 = adev_rate(raw, dt)
            ax2.loglog(taus2, adev2, color="#888888", lw=2, zorder=3)
            style_ax(ax2,
                     xlabel="Averaging time  τ  (s)",
                     ylabel=f"ADEV  (m/s²)",
                     title=f"{LABEL.get(col, col)}  (standard ADEV — not an angle column)")

    fig1.tight_layout()
    fig2.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
