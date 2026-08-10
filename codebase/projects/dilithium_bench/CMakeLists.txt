
# Copyright 2026 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(dilithium_bench LANGUAGES C CXX ASM PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)


include("${board}_${core_id}/board_files.cmake")

mcux_add_source(
    SOURCES main.c
)
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )
mcux_add_include(INCLUDES .)

file(GLOB PQCLEAN_SOURCES RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/pqclean/*.c)
mcux_add_source(SOURCES ${PQCLEAN_SOURCES})
mcux_add_include(INCLUDES ./pqclean)

# Set to ON to build the GPIO-triggered energy-measurement variant instead
# of the default UART-per-iteration performance/memory variant. OFF by
# default so normal `ninja` builds are unaffected.
option(DILITHIUM_ENERGY_MODE "Build the GPIO-triggered energy-measurement firmware variant" OFF)
if(DILITHIUM_ENERGY_MODE)
  mcux_add_macro(CC "-DENERGY_MODE")
endif()

# ML-DSA signing needs a deeper stack than ML-KEM (signatures are larger,
# signing recurses through a rejection-sampling loop with more live
# polyvec state). Override via -DDILITHIUM_STACK_SIZE=0xNNNN; default
# starting point is 0x8000 (32 KiB), same as mlkem_bench's default -- raise
# until zero HardFaults are observed across a full run (see
# BENCHMARK_METHODOLOGY.md in this directory once written).
set(DILITHIUM_STACK_SIZE "0x8000" CACHE STRING "Stack size in bytes (hex), passed to the linker as __stack_size__")
mcux_add_linker_symbol(SYMBOLS "__stack_size__=${DILITHIUM_STACK_SIZE}")
