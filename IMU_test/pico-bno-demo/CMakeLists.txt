cmake_minimum_required(VERSION 3.13)

# Build for Pico 2 / RP2350
set(PICO_BOARD pico2)

# Include the SDK (expects pico-sdk directory inside this project)
include(pico-sdk/pico_sdk_init.cmake)
pico_sdk_init()

project(pico_bno_demo C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# External library
add_subdirectory(BNO08x_Pico_Library)

# Single executable: human-readable test firmware
add_executable(main
    src/main.cpp
)

# Enable USB stdio (so printf goes to USB serial)
pico_enable_stdio_usb(main 1)
pico_enable_stdio_uart(main 0)

# Link libs
target_link_libraries(main
    pico_stdlib
    BNO08x_Pico_Library
)

# Produce UF2
pico_add_extra_outputs(main)

