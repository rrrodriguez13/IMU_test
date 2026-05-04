import sys
import numpy as np
import matplotlib.pyplot as plt

path = sys.argv[1]
data = np.genfromtxt(path, delimiter=',', names=True)

t = data['t_rel_s']

angle_cols = ['theta_deg', 'phi_deg']
accel_cols  = ['imu0_ax', 'imu0_ay', 'imu0_az',
               'imu1_ax', 'imu1_ay', 'imu1_az']

all_cols = [c for c in angle_cols + accel_cols if c in data.dtype.names]

fig, axes = plt.subplots(len(all_cols), 1, sharex=True, figsize=(12, 3 * len(all_cols)))
fig.suptitle('Stability over Time')

for ax, col in zip(axes, all_cols):
    x = data[col]
    mean = np.mean(x)
    std  = np.std(x)
    ax.plot(t, x, lw=0.8, alpha=0.8, label=col)
    ax.axhline(mean, ls='--', lw=1.5, label=f'mean = {mean:.3f}')
    ax.fill_between(t, mean - std, mean + std, alpha=0.2, label=f'±1σ = {std:.3f}')
    ax.set_ylabel('deg' if col.endswith('_deg') else 'm/s²')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True)

axes[-1].set_xlabel('time (s)')
plt.tight_layout()

print(f"{'Column':<20} {'Mean':>10} {'Std':>10} {'Min':>10} {'Max':>10}")
for col in all_cols:
    x = data[col]
    print(f"{col:<20} {np.mean(x):>10.4f} {np.std(x):>10.4f} {np.min(x):>10.4f} {np.max(x):>10.4f}")

plt.show()
