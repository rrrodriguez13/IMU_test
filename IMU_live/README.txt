IMU HUMAN-READABLE TEST FIRMWARE
===============================

This document describes how to build, flash, and run a Raspberry Pi Pico 2
(RP2350) firmware that outputs live, human-readable IMU orientation data
(phi, theta, psi) in degrees over USB serial.

This version is intended for:
- Live viewing
- Sanity checking orientation
- Interactive testing and debugging

It does NOT include CSV logging or file output.

------------------------------------------------------------
Repository Layout
------------------------------------------------------------

The repository is assumed to be cloned as:

    IMU_live/

Repository contents:

    IMU_live/
    ├── pico-bno-demo/
    │   ├── CMakeLists.txt
    │   ├── src/
    │   │   └── main.cpp
    │   ├── build/
    │   ├── pico-sdk/
    │   └── BNO08x_Pico_Library/
    └── README.txt

------------------------------------------------------------
System Overview
------------------------------------------------------------

Hardware:
- Raspberry Pi Pico 2 (RP2350)
- BNO08x IMU (I2C)

Software:
- Linux (Debian/Ubuntu-style)
- pico-sdk (develop branch, RP2350-compatible)
- GNU Arm Embedded Toolchain
- screen (or equivalent serial monitor)

------------------------------------------------------------
Orientation Output
------------------------------------------------------------

The firmware prints three orientation angles in degrees:

    phi   (yaw)   : heading / azimuth, range 0–360°
    theta (pitch) : forward/back tilt, range −90° to +90°
    psi   (roll)  : left/right tilt, range −180° to +180°

All values are derived from the BNO08x fused rotation vector.

Example output:

    phi: 123.45° (yaw)   theta:  -2.31° (pitch)   psi:  0.87° (roll)

------------------------------------------------------------
Building the Firmware
------------------------------------------------------------

From the repository root:

    cd IMU_live/pico-bno-demo

Create the build directory (one time):

    mkdir -p build

Configure and build:

    cd build
    cmake ..
    make

After a successful build, the following file will be created:

    build/main.uf2

------------------------------------------------------------
Flashing the Pico
------------------------------------------------------------

1. Unplug the Pico from USB.
2. Hold the BOOTSEL button.
3. Plug the Pico into USB while holding BOOTSEL.
4. Release BOOTSEL.

The Pico will mount as a USB drive (example name: RP2350).

From the build directory:

    cp main.uf2 /media/$USER/RP2350/main.uf2

After copying:
- The Pico will reboot automatically.
- Unplug and replug the Pico normally (do NOT hold BOOTSEL).

------------------------------------------------------------
Viewing Live Output
------------------------------------------------------------

Check that the USB serial device exists:

    ls /dev/ttyACM*

Open the serial monitor:

    screen /dev/ttyACM0 115200

Exit screen:

    Ctrl-a
    k
    y

------------------------------------------------------------
Common Issues and Fixes
------------------------------------------------------------

No UF2 file produced:
- Ensure you ran cmake from inside the build directory.
- Ensure CMakeLists.txt exists in pico-bno-demo/.

UF2 copy fails with “Not a directory”:
- The Pico is not in BOOTSEL mode.
- Re-enter BOOTSEL and confirm the mount exists under /media/$USER.

screen immediately says “terminating”:
- Another process is using the serial port.

Check and fix:

    sudo lsof /dev/ttyACM0
    sudo kill <PID>

Then reopen screen.

No output appears:
- Ensure the Pico is not still in BOOTSEL mode.
- Ensure USB stdio is enabled in CMakeLists.txt.
- Wait ~2 seconds after plugging in before opening screen.

------------------------------------------------------------
Intended Use
------------------------------------------------------------

This firmware is designed exclusively for live, human-readable IMU output.

If data logging or CSV export is required in the future, a separate firmware
variant should be created rather than modifying this one.

------------------------------------------------------------
End of Document
------------------------------------------------------------

