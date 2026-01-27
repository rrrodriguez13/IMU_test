import csv

rows = []
with open("imu_log.csv", newline="") as f:
    r = csv.reader(f)
    next(r, None)  # skip header
    for row in r:
        if len(row) < 3:
            continue
        try:
            phi = float(row[0]); theta = float(row[1]); psi = float(row[2])
        except ValueError:
            continue
        rows.append((phi, theta, psi))

with open("imu_log_table.txt", "w") as f:
    f.write("phi (yaw) [deg]     theta (pitch) [deg]   psi (roll) [deg]\n")
    f.write("-----------------------------------------------------------\n")
    for phi, theta, psi in rows:
        f.write(f"{phi:10.2f}°          {theta:10.2f}°          {psi:10.2f}°\n")

print("Wrote imu_log_table.txt")
