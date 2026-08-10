
# Copyright 2026 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(mldsa_bench_nxp LANGUAGES C CXX ASM PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)


include("${board}_${core_id}/board_files.cmake")

mcux_add_source(
    SOURCES hello_world.c
)
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )
mcux_add_include(INCLUDES .)

# ML-DSA security level: set -DMLDSA_LEVEL=<44|65|87> at configure time.
set(MLDSA_LEVEL "44" CACHE STRING "ML-DSA level: 44/65/87")
if(NOT MLDSA_LEVEL MATCHES "^(44|65|87)$")
  message(FATAL_ERROR "MLDSA_LEVEL must be 44, 65, or 87")
endif()

# Instrumented PQClean ML-DSA sources for the selected level.
file(GLOB MLDSA_SOURCES RELATIVE ${CMAKE_CURRENT_SOURCE_DIR}
     ${CMAKE_CURRENT_SOURCE_DIR}/pqclean/ml-dsa-${MLDSA_LEVEL}/*.c
     ${CMAKE_CURRENT_SOURCE_DIR}/pqclean/fips202.c
     ${CMAKE_CURRENT_SOURCE_DIR}/pqclean/randombytes.c)
mcux_add_source(SOURCES ${MLDSA_SOURCES})
mcux_add_include(INCLUDES ./pqclean ./pqclean/ml-dsa-${MLDSA_LEVEL})
mcux_add_macro(CC "-DMLDSA_LEVEL=${MLDSA_LEVEL}")

# ML-DSA sign() needs ~120KB peak stack (mat[K][L] arrays); the SDK default is
# 32KB. Grow the linker stack region to 128KB via the standard __stack_size__ hook.
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--defsym=__stack_size__=0x20000")
