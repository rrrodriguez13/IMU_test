cmake_minimum_required(VERSION 3.13)

# Build for Pico 2 / RP2350
set(PICO_BOARD pico2)

include(pico-sdk/pico_sdk_init.cmake)
pico_sdk_init()

project(imu_log C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

add_subdirectory(BNO08x_Pico_Library)

add_executable(main
    src/main.cpp
)

pico_enable_stdio_usb(main 1)
pico_enable_stdio_uart(main 0)

target_link_libraries(main
    pico_stdlib
    BNO08x_Pico_Library
)

pico_add_extra_outputs(main)
