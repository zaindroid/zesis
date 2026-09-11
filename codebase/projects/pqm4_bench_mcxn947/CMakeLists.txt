# Copyright 2026
# SPDX-License-Identifier: BSD-3-Clause
# pqm4 benchmark on FRDM-MCXN947 — measures pqm4 (M-profile optimized) PQC.
# Build one algorithm+level+variant at a time (unprefixed symbols):
#   cmake --preset debug -DALG=MLKEM -DLEVEL=768 -DVARIANT=m4fspeed
#   cmake --preset debug -DALG=MLDSA -DLEVEL=44  -DVARIANT=m4f
# PQM4_ROOT must point at codebase/ (parent of pqm4).

cmake_minimum_required(VERSION 3.22.0)

set(PQM4_ROOT "H:/z_thesis/codebase" CACHE PATH "codebase root (parent of pqm4)")

# algorithm / level / variant selection
set(ALG "MLKEM" CACHE STRING "MLKEM or MLDSA")
set_property(CACHE ALG PROPERTY STRINGS MLKEM MLDSA)
set(LEVEL "768" CACHE STRING "512/768/1024 (MLKEM) or 44/65/87 (MLDSA)")
set_property(CACHE LEVEL PROPERTY STRINGS 512 768 1024 44 65 87)
set(VARIANT "m4fspeed" CACHE STRING "m4fspeed|m4fstack (MLKEM) or m4f|m4fstack (MLDSA)")
set_property(CACHE VARIANT PROPERTY STRINGS m4fspeed m4fstack m4f)
set(REPS "100" CACHE STRING "repetitions per op")


cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(pqm4_bench_mcxn947 LANGUAGES C CXX ASM PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)

include("${board}_${core_id}/board_files.cmake")

mcux_add_source(SOURCES main.c)
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )
mcux_add_include(INCLUDES .)

# ---- select the pqm4 sources (absolute paths via target_sources) ----
if(ALG STREQUAL "MLKEM")
  set(PQM4_DIR ${PQM4_ROOT}/pqm4/crypto_kem/ml-kem-${LEVEL}/${VARIANT})
else()
  set(PQM4_DIR ${PQM4_ROOT}/pqm4/crypto_sign/ml-dsa-${LEVEL}/${VARIANT})
endif()

file(GLOB PQM4_SOURCES ${PQM4_DIR}/*.c ${PQM4_DIR}/*.S ${PQM4_DIR}/*.s)
target_sources(${MCUX_SDK_PROJECT_NAME} PRIVATE ${PQM4_SOURCES})
target_include_directories(${MCUX_SDK_PROJECT_NAME} PRIVATE
    ${PQM4_DIR} ${PQM4_ROOT}/pqm4/mupq/common)

# randombytes/fips202 support (PQClean common, copied into mupq/common)
target_sources(${MCUX_SDK_PROJECT_NAME} PRIVATE
    ${PQM4_ROOT}/pqm4/mupq/common/randombytes.c
    ${PQM4_ROOT}/pqm4/mupq/common/fips202.c)

# macros (plain CMake logic - generator expressions may not pass through mcux_add_macro)
if(ALG STREQUAL "MLKEM")
  set(ALG_DEFS "-DALG=${ALG} -DALG_MLKEM=1 -DALG_MLDSA=0 -DLEVEL=${LEVEL} -DREPS=${REPS}")
else()
  set(ALG_DEFS "-DALG=${ALG} -DALG_MLKEM=0 -DALG_MLDSA=1 -DLEVEL=${LEVEL} -DREPS=${REPS}")
endif()
mcux_add_macro(CC ${ALG_DEFS})
mcux_add_macro(CX ${ALG_DEFS})

# Exp 2 verification: the m4f ML-DSA path overruns the 32KB default stack
# (CFSR.STKOF). Match the clean-C ML-DSA bench stack (128KB). Appended AFTER
# the SDK setup so the linker script (-T) flags are preserved.
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--defsym=__stack_size__=0x20000")
