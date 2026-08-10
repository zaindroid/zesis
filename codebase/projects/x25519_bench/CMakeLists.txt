
# Copyright 2026 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(x25519_bench LANGUAGES C CXX ASM PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)


include("${board}_${core_id}/board_files.cmake")

mcux_add_source(
    SOURCES hello_world.c
)
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )
mcux_add_include(INCLUDES .)

mcux_add_source(SOURCES x25519/x25519.c x25519/x25519.h)
mcux_add_include(INCLUDES ./x25519)

# Builds the GPIO-triggered energy-measurement firmware variant instead
# of the default performance/memory variant. OFF by default.
# Enable with: cmake --preset debug -DX25519_ENERGY_MODE=ON
option(X25519_ENERGY_MODE "Build the GPIO-triggered energy-measurement firmware variant" OFF)
if(X25519_ENERGY_MODE)
  mcux_add_macro(CC "-DENERGY_MODE")
endif()
