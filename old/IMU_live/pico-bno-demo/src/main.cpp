#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"

#include "bno08x.h"
#include "utils.h"

// IMU object
BNO08x IMU;

int main() {
    // Initialize USB stdio
    stdio_init_all();

    // Allow time for USB enumeration
    sleep_ms(2000);
    printf("IMU human-readable output started\n");

    // Initialize I2C (i2c0: default GP4=SDA, GP5=SCL)
    i2c_inst_t* i2c_port0;
    initI2C(i2c_port0, false);

    const uint8_t BNO08X_ADDR = 0x4A; // change to 0x4B if needed

    // Wait until IMU is ready
    while (!IMU.begin(BNO08X_ADDR, i2c_port0)) {
        printf("Waiting for BNO08x...\n");
        sleep_ms(1000);
    }

    printf("BNO08x detected — starting live output\n");

    // Enable fused orientation output
    IMU.enableRotationVector();

    // Main loop: read fused rotation vector and print labeled degrees
    while (true) {
        if (IMU.getSensorEvent()) {
            if (IMU.getSensorEventID() == SENSOR_REPORTID_ROTATION_VECTOR) {

                float yaw_rad   = IMU.getYaw();
                float pitch_rad = IMU.getPitch();
                float roll_rad  = IMU.getRoll();

                float phi_deg   = yaw_rad   * 180.0f / M_PI; // phi = yaw
                float theta_deg = pitch_rad * 180.0f / M_PI; // theta = pitch
                float psi_deg   = roll_rad  * 180.0f / M_PI; // psi = roll

                // Map yaw (phi) into 0..360 degrees
                if (phi_deg < 0) phi_deg += 360.0f;

                // Print human-readable labeled line
                printf(
                    "phi: %7.2f° (yaw)   "
                    "theta: %7.2f° (pitch)   "
                    "psi: %7.2f° (roll)\n",
                    phi_deg, theta_deg, psi_deg
                );
            }
        }
        sleep_ms(200); // ~5 Hz (easy to read)
    }

    return 0;
}

