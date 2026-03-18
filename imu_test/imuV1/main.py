# main.py (MicroPython on Pico 2)
# Reads BNO085 UART-RVC on UART1 and prints labeled Roll/Pitch/Yaw + Accel at a readable rate.

from machine import UART, Pin
import time
import struct

# UART CONFIG
# Example: UART1 TX=GP4, RX=GP5
uart = UART(0, baudrate=115200, tx=Pin(4), rx=Pin(5))

def checksum_8bit(data: bytes) -> int:
    return sum(data) & 0xFF

def read_frame():
    """
    Reads one UART-RVC frame:
      AA AA <len> <msgid> <payload...> <checksum>
    checksum = sum(all bytes except checksum) & 0xFF
    Returns payload bytes or None.
    """
    while True:
        b = uart.read(1)
        if not b:
            return None

        if b != b"\xAA":
            continue

        b2 = uart.read(1)
        if not b2:
            return None
        if b2 != b"\xAA":
            continue

        rest = uart.read(2)
        if not rest or len(rest) < 2:
            return None

        length = rest[0]
        msgid = rest[1]  # not used here

        payload = uart.read(length)
        if not payload or len(payload) < length:
            return None

        ck = uart.read(1)
        if not ck or len(ck) < 1:
            return None

        frame_wo_ck = b"\xAA\xAA" + bytes([length, msgid]) + payload
        if checksum_8bit(frame_wo_ck) != ck[0]:
            return None

        return payload

def decode_rvc_heading(payload: bytes):
    """
    Common RVC heading payload begins with 7 little-endian int16 values:
      yaw, pitch, roll (centi-deg)
      ax, ay, az (centi m/s^2)
      extra (status/reserved)
    We return: roll, pitch, yaw, ax, ay, az
    """
    if len(payload) < 14:
        return None

    v = struct.unpack_from("<7h", payload, 0)

    yaw_cdeg, pitch_cdeg, roll_cdeg = v[0], v[1], v[2]
    ax_c, ay_c, az_c = v[3], v[4], v[5]

    yaw = yaw_cdeg / 100.0
    pitch = pitch_cdeg / 100.0
    roll = roll_cdeg / 100.0

    ax = ax_c / 100.0
    ay = ay_c / 100.0
    az = az_c / 100.0

    return roll, pitch, yaw, ax, ay, az

# -------- OUTPUT SETTINGS --------
PRINT_HZ = 5               # lower = slower scrolling
period_ms = int(1000 / PRINT_HZ)
last_print = time.ticks_ms()

# Print a clear header once at boot
print("\nBNO085 UART-RVC via Pico 2")
print("Units: angles=deg, accel=m/s^2")
print("Rotate/tilt the board to confirm axes:")
print("  - Yaw changes when you rotate flat on the table")
print("  - Pitch changes when you tilt nose up/down")
print("  - Roll changes when you tilt side-to-side")
print("-" * 86)

while True:
    payload = read_frame()
    if not payload:
        continue

    decoded = decode_rvc_heading(payload)
    if not decoded:
        continue

    roll, pitch, yaw, ax, ay, az = decoded

    now = time.ticks_ms()
    if time.ticks_diff(now, last_print) < period_ms:
        continue
    last_print = now

    # Explicit labeled line (no ambiguity)
    print(
        "ROLL: {:7.2f}°   PITCH: {:7.2f}°   YAW: {:7.2f}°   |   "
        "AX: {:7.3f}  AY: {:7.3f}  AZ: {:7.3f}".format(
            roll, pitch, yaw, ax, ay, az
        )
    )
