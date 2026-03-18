IMU CSV LOGGING SETUP
====================

This directory contains a complete setup for logging IMU orientation data
from a Raspberry Pi Pico 2 (RP2350) using a BNO08x sensor. The firmware
outputs CSV data over USB serial, which is recorded on the host computer
and optionally converted into a human-readable table.

This version is intended for:
- Long data collection runs
- Saving IMU data to disk
- Offline analysis and post-processing

It does NOT provide live, human-readable output on the microcontroller.

------------------------------------------------------------
Directory Layout
------------------------------------------------------------

IMU_log/
├── pico-bno-demo/
│   ├── CMakeLists.txt
│   ├── src/
│   │   └── main.cpp        (CSV firmware)
│   ├── build/              (created after build)
│   ├── pico-sdk/
│   └── BNO08x_Pico_Library/
├── log_imu.py              (PC-side logger)
├── imu_table.py            (CSV → table converter)
├── imu_log.csv             (generated)
├── imu_log_table.txt       (generated)
└── README.txt

Files marked “generated” will not exist until the corresponding steps
are performed.

------------------------------------------------------------
System Requirements
------------------------------------------------------------

Hardware:
- Raspberry Pi Pico 2 (RP2350)
- BNO08x IMU (I2C)

Software:
- Linux (Debian/Ubuntu-style)
- pico-sdk (develop branch, RP2350-compatible)
- GNU Arm Embedded Toolchain
- Python 3
- python3-serial (pyserial)

------------------------------------------------------------
CSV Output Format
------------------------------------------------------------

The firmware outputs one CSV row per IMU sample:

    phi_deg,theta_deg,psi_deg

Where:
- phi   = yaw / azimuth, range 0–360 degrees
- theta = pitch, range −90 to +90 degrees
- psi   = roll, range −180 to +180 degrees

Example row:

    123.456,-2.314,0.872

All values are derived from the BNO08x fused rotation vector and converted
from radians to degrees on the microcontroller.

------------------------------------------------------------
Building the Firmware
------------------------------------------------------------

From the IMU_log directory:

    cd pico-bno-demo

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
Recording IMU Data to CSV
------------------------------------------------------------

The script log_imu.py reads CSV data from the Pico over USB serial and
writes it to a file.

From the IMU_log directory:

    python3 log_imu.py

While running:
- Incoming CSV rows are printed to the terminal
- All rows are written to imu_log.csv

Stop recording with:

    Ctrl-C

The file imu_log.csv will remain on disk after logging stops.

------------------------------------------------------------
Converting CSV to a Table
------------------------------------------------------------

The script imu_table.py converts the recorded CSV file into a
human-readable text table with labels and degree symbols.

From the IMU_log directory:

    python3 imu_table.py

This produces:

    imu_log_table.txt

View the table:

    less imu_log_table.txt

Exit the viewer:

    q

------------------------------------------------------------
Common Issues and Fixes
------------------------------------------------------------

No UF2 file produced:
- Ensure cmake was run from inside the build directory.
- Ensure CMakeLists.txt exists in pico-bno-demo/.

UF2 copy fails with “Not a directory”:
- The Pico is not in BOOTSEL mode.
- Re-enter BOOTSEL and confirm the mount exists under /media/$USER.

log_imu.py cannot open /dev/ttyACM0:
- Another program is using the serial port.

Check and fix:

    sudo lsof /dev/ttyACM0
    sudo kill <PID>

imu_log.csv is empty:
- Ensure the Pico is running the CSV firmware.
- Ensure USB stdio is enabled in CMakeLists.txt.
- Ensure log_imu.py is run from the IMU_log directory.

------------------------------------------------------------
Intended Use
------------------------------------------------------------

This setup is designed exclusively for CSV-based IMU data logging and
offline analysis.

For interactive or human-readable live output, use a separate firmware
variant rather than modifying this one.

------------------------------------------------------------
End of Document
------------------------------------------------------------

