
# Copyright 2026 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(mlkem_bench LANGUAGES C CXX ASM PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)


include("${board}_${core_id}/board_files.cmake")

if(MLKEM_ACTIVITY_MODE)
  mcux_add_source(SOURCES activity_capture.c)
else()
  mcux_add_source(SOURCES hello_world.c)
endif()
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )
mcux_add_include(INCLUDES .)

file(GLOB PQCLEAN_SOURCES RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/pqclean/*.c)
mcux_add_source(SOURCES ${PQCLEAN_SOURCES})
mcux_add_include(INCLUDES ./pqclean)

# Set to ON to build the GPIO-triggered energy-measurement variant (see
# hello_world.c's ENERGY_MODE block and BENCHMARK_METHODOLOGY.md Section
# 6) instead of the default UART-per-iteration performance/memory
# variant. OFF by default so normal `ninja` builds are unaffected; flip
# via `cmake --preset debug -DMLKEM_ENERGY_MODE=ON` once the PPK2 is
# physically wired.
option(MLKEM_ENERGY_MODE "Build the GPIO-triggered energy-measurement firmware variant" OFF)
if(MLKEM_ENERGY_MODE)
  mcux_add_macro(CC "-DENERGY_MODE")
endif()

# Option A (reframed): activity-leakage capture firmware (activity_capture.c).
# Builds the segmentable per-op burst variant with per-rep key variation for
# the PPK2+CNN activity-classification study.
option(MLKEM_ACTIVITY_MODE "Build the activity-leakage capture firmware variant" OFF)
if(MLKEM_ACTIVITY_MODE)
  mcux_add_macro(CC "-DACTIVITY_MODE")
endif()