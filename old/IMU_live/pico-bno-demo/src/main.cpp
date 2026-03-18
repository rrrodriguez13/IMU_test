#include <stdio.h>
#include <math.h>

#include "pico/stdlib.h"
#include "hardware/i2c.h"
#include "hardware/gpio.h"

#include "bno08x.h"

static const uint SDA_PIN = 16;
static const uint SCL_PIN = 17;

BNO08x IMU;

static void i2c_scan(i2c_inst_t *i2c) {
    printf("Scanning I2C bus on SDA=GP%u SCL=GP%u...\n", SDA_PIN, SCL_PIN);

    int found = 0;
    for (uint8_t addr = 0x08; addr <= 0x77; addr++) {
        uint8_t dummy;
        int ret = i2c_read_blocking(i2c, addr, &dummy, 1, false);
        if (ret >= 0) {
            printf("I2C device found at 0x%02X\n", addr);
            found++;
        }
    }

    if (!found) {
        printf("No I2C devices found.\n");
    }
}

static bool try_begin(i2c_inst_t *i2c, uint8_t addr) {
    printf("Trying BNO08x at 0x%02X...\n", addr);
    return IMU.begin(addr, i2c);
}

int main() {
    stdio_init_all();
    sleep_ms(2000);

    // Use I2C0 on GP16/GP17
    i2c_inst_t *i2c_port = i2c0;
    i2c_init(i2c_port, 400 * 1000);  // 400 kHz

    gpio_set_function(SDA_PIN, GPIO_FUNC_I2C);
    gpio_set_function(SCL_PIN, GPIO_FUNC_I2C);
    gpio_pull_up(SDA_PIN);
    gpio_pull_up(SCL_PIN);

    i2c_scan(i2c_port);

    // Try both common BNO08x I2C addresses
    while (true) {
        if (try_begin(i2c_port, 0x4A) || try_begin(i2c_port, 0x4B)) {
            printf("BNO08x detected!\n");
            break;
        }
        printf("Waiting for BNO08x...\n");
        sleep_ms(1000);
    }

    IMU.enableRotationVector();

    while (true) {
        if (IMU.getSensorEvent() &&
            IMU.getSensorEventID() == SENSOR_REPORTID_ROTATION_VECTOR) {

            float yaw   = IMU.getYaw()   * 180.0f / M_PI;
            float pitch = IMU.getPitch() * 180.0f / M_PI;
            float roll  = IMU.getRoll()  * 180.0f / M_PI;

            if (yaw < 0) yaw += 360.0f;

            // Human-readable columns
            printf("Yaw: %7.2f°  Pitch: %7.2f°  Roll: %7.2f°\n", yaw, pitch, roll);
        }
        sleep_ms(50);
    }
}

