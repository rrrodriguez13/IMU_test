# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/_deps/picotool-src"
  "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/_deps/picotool-build"
  "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/_deps"
  "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/pico-sdk/src/rp2350/boot_stage2/picotool/tmp"
  "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/pico-sdk/src/rp2350/boot_stage2/picotool/src/picotoolBuild-stamp"
  "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/pico-sdk/src/rp2350/boot_stage2/picotool/src"
  "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/pico-sdk/src/rp2350/boot_stage2/picotool/src/picotoolBuild-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/pico-sdk/src/rp2350/boot_stage2/picotool/src/picotoolBuild-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/home/an0mie/Projects/IMU_test/IMU_live/pico-bno-demo/build/pico-sdk/src/rp2350/boot_stage2/picotool/src/picotoolBuild-stamp${cfgdir}") # cfgdir has leading slash
endif()
