#include <stdio.h>
#include <math.h>
#include "pico/stdlib.h"

#include "bno08x.h"
#include "utils.h"

BNO08x IMU;

int main() {
    stdio_init_all();
    sleep_ms(2000);

    // I2C (default pins for this library setup: GP4 SDA, GP5 SCL)
    i2c_inst_t* i2c_port0;
    initI2C(i2c_port0, false);

    const uint8_t BNO08X_ADDR = 0x4A; // use 0x4B if required by your wiring/board

    while (!IMU.begin(BNO08X_ADDR, i2c_port0)) {
        sleep_ms(500);
    }

    IMU.enableRotationVector();

    // CSV header once
    printf("phi_deg,theta_deg,psi_deg\n");

    while (true) {
        if (IMU.getSensorEvent() &&
            IMU.getSensorEventID() == SENSOR_REPORTID_ROTATION_VECTOR) {

            float yaw_rad   = IMU.getYaw();
            float pitch_rad = IMU.getPitch();
            float roll_rad  = IMU.getRoll();

            float phi_deg   = yaw_rad   * 180.0f / M_PI;
            float theta_deg = pitch_rad * 180.0f / M_PI;
            float psi_deg   = roll_rad  * 180.0f / M_PI;

            if (phi_deg < 0) phi_deg += 360.0f;

            printf("%.3f,%.3f,%.3f\n", phi_deg, theta_deg, psi_deg);
        }
        sleep_ms(50); // ~20 Hz
    }

    return 0;
}
