#!/usr/bin/env python3
"""
two_axis_angles.py - recover elevation and azimuth from two IMUs without gimbal lock

    python3 two_axis_angles.py logs/imu_data000.csv
    python3 two_axis_angles.py logs/imu_data000.csv --m0 0 0 0 --m1 0 90 0
    python3 two_axis_angles.py logs/imu_data000.csv --unwrap
"""

import argparse
import os
import sys

import numpy as np
import matplotlib.pyplot as plt


def euler_to_matrix(yaw_deg, pitch_deg, roll_deg):
    y = np.radians(yaw_deg)
    p = np.radians(pitch_deg)
    r = np.radians(roll_deg)
    cy, sy = np.cos(y), np.sin(y)
    cp, sp = np.cos(p), np.sin(p)
    cr, sr = np.cos(r), np.sin(r)
    R = np.zeros((*np.shape(y), 3, 3))
    R[..., 0, 0] =  cy*cp
    R[..., 0, 1] =  cy*sp*sr - sy*cr
    R[..., 0, 2] =  cy*sp*cr + sy*sr
    R[..., 1, 0] =  sy*cp
    R[..., 1, 1] =  sy*sp*sr + cy*cr
    R[..., 1, 2] =  sy*sp*cr - cy*sr
    R[..., 2, 0] = -sp
    R[..., 2, 1] =  cp*sr
    R[..., 2, 2] =  cp*cr
    return R


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


def recover_angles(data, M0, M1):
    R0 = euler_to_matrix(data["imu0_yaw_deg"], data["imu0_pitch_deg"], data["imu0_roll_deg"])
    R1 = euler_to_matrix(data["imu1_yaw_deg"], data["imu1_pitch_deg"], data["imu1_roll_deg"])

    R_elev = R0 @ M0.T
    theta_deg = np.degrees(np.arctan2(R_elev[:, 2, 1], R_elev[:, 2, 2]))

    t = np.radians(theta_deg)
    c, s = np.cos(t), np.sin(t)
    z = np.zeros_like(c)
    o = np.ones_like(c)
    Rx_T = np.stack([
        np.stack([o,  z,  z], axis=-1),
        np.stack([z,  c,  s], axis=-1),
        np.stack([z, -s,  c], axis=-1),
    ], axis=-2)

    R_az = Rx_T @ R1 @ M1.T
    phi_deg = np.degrees(np.arctan2(R_az[:, 1, 0], R_az[:, 0, 0]))

    return theta_deg, phi_deg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument(
        "--m0", nargs=3, type=float, metavar=("YAW", "PITCH", "ROLL"),
        default=[0.0, 0.0, 0.0],
        help="IMU0 mount rotation in degrees yaw pitch roll (default: identity)",
    )
    ap.add_argument(
        "--m1", nargs=3, type=float, metavar=("YAW", "PITCH", "ROLL"),
        default=[0.0, 0.0, 0.0],
        help="IMU1 mount rotation in degrees yaw pitch roll (default: identity)",
    )
    ap.add_argument(
        "--unwrap", action="store_true",
        help="unwrap φ across the ±180° boundary for continuous azimuth",
    )
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"error: {args.file} not found", file=sys.stderr)
        sys.exit(1)

    data = load_csv(args.file)

    required = (
        "imu0_roll_deg", "imu0_pitch_deg", "imu0_yaw_deg",
        "imu1_roll_deg", "imu1_pitch_deg", "imu1_yaw_deg",
    )
    missing = [c for c in required if c not in data]
    if missing:
        print(f"error: missing columns {missing} — file needs two IMUs", file=sys.stderr)
        sys.exit(1)

    M0 = euler_to_matrix(*args.m0)
    M1 = euler_to_matrix(*args.m1)

    t = data["t_rel_s"]
    theta, phi = recover_angles(data, M0, M1)

    if args.unwrap:
        phi = np.degrees(np.unwrap(np.radians(phi)))

    fig, (ax_t, ax_p) = plt.subplots(
        2, 1, sharex=True, figsize=(11, 6), facecolor="white"
    )
    fig.suptitle(
        f"Recovered θ / φ  —  {os.path.basename(args.file)}",
        fontsize=12, fontweight="bold",
    )

    ax_t.plot(t, theta, color="#e07b00", lw=1.5)
    ax_t.set_ylabel("Elevation θ (°)", fontsize=9)
    ax_t.axhline(0, color="#cccccc", lw=0.8, zorder=0)
    ax_t.grid(True, color="#eeeeee")
    ax_t.set_facecolor("white")

    ax_p.plot(t, phi, color="#2ca02c", lw=1.5)
    ax_p.set_ylabel("Azimuth φ (°)", fontsize=9)
    ax_p.set_xlabel("Time (s)", fontsize=9)
    ax_p.axhline(0, color="#cccccc", lw=0.8, zorder=0)
    ax_p.grid(True, color="#eeeeee")
    ax_p.set_facecolor("white")

    for ax in (ax_t, ax_p):
        for spine in ax.spines.values():
            spine.set_edgecolor("#cccccc")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
