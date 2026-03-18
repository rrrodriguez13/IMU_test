import serial

PORT = "/dev/ttyACM0"
BAUD = 115200

with serial.Serial(PORT, BAUD, timeout=1) as ser, open("imu_log.csv", "w") as f:
    while True:
        line = ser.readline().decode(errors="replace").strip()
        if not line:
            continue
        print(line)
        f.write(line + "\n")
        f.flush()
