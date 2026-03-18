#include <stdio.h>
#include <math.h>

#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/gpio.h"

#include "bno08x.h"
#include "utils.h"

BNO08x IMU;

// Pins for your custom board
static const uint SDA_PIN = 16; // GP16
static const uint SCL_PIN = 17; // GP17

int main() {
    stdio_init_all();
    sleep_ms(2000); // allow USB to enumerate

    // Initialize I2C0 at 400 kHz using GP16/GP17
    i2c_inst_t* i2c_port = i2c0;
    i2c_init(i2c_port, 400 * 1000);

    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    // enable internal pull-ups (recommended to have external pull-ups on board)
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);

    // Optional quick I2C scan to show what devices respond
    printf("Scanning I2C on SDA=GP%u SCL=GP%u...\n", SDA_PIN, SCL_PIN);
    int found = 0;
    for (uint8_t addr = 0x03; addr <= 0x77; ++addr) {
        uint8_t buf;
        int ret = i2c_read_blocking(i2c_port, addr, &buf, 1, false);
        if (ret >= 0) {
            printf("I2C device responding at 0x%02X\n", addr);
            ++found;
        }
    }
    if (!found) {
        printf("No I2C devices found on those pins.\n");
    }

    // Try common BNO08x addresses until one initializes
    const uint8_t addrs_to_try[] = { 0x4A, 0x4B };
    bool began = false;
    for (;;) {
        for (size_t i = 0; i < sizeof(addrs_to_try); ++i) {
            uint8_t addr = addrs_to_try[i];
            printf("Trying BNO08x at 0x%02X...\n", addr);
            if (IMU.begin(addr, i2c_port)) {
                printf("BNO08x detected at 0x%02X\n", addr);
                began = true;
                break;
            }
            sleep_ms(200);
        }
        if (began) break;
        printf("Waiting for BNO08x...\n");
        sleep_ms(1000);
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

            // Print CSV line
            printf("%.3f,%.3f,%.3f\n", phi_deg, theta_deg, psi_deg);
        }
        sleep_ms(50); // ~20 Hz
    }

    return 0;
}

