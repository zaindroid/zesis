# Copyright 2026
# SPDX-License-Identifier: BSD-3-Clause
# SecureMark-TLS (EEMBC self-hosted) on FRDM-MCXN947.
# Compiles the EEMBC profile + our th_* mbedTLS layer + mbedTLS 3.6.3.

cmake_minimum_required(VERSION 3.22.0)

set(MBEDTLS_ROOT "H:/z_thesis/codebase/projects/securemark_tls_mcxn947/mbedtls" CACHE PATH "mbedtls root")
set(SM_ROOT "H:/z_thesis/codebase/securemark-tls" CACHE PATH "securemark-tls repo root")

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(securemark_tls_mcxn947 LANGUAGES C CXX ASM PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)

include("${board}_${core_id}/board_files.cmake")

mcux_add_source(SOURCES board_main.c sm_main.c th_aes.c th_sha.c th_ecdh.c th_ecdsa.c th_util.c retarget.c)
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )
mcux_add_include(INCLUDES .)

# ---- EEMBC profile sources ----
file(GLOB SM_PROFILE ${SM_ROOT}/profile/ee_*.c)
target_sources(${MCUX_SDK_PROJECT_NAME} PRIVATE ${SM_PROFILE})
target_include_directories(${MCUX_SDK_PROJECT_NAME} PRIVATE
    ${SM_ROOT}/profile
    ${SM_ROOT}/profile/th_api
    ${SM_ROOT}/monitor
    ${SM_ROOT}/monitor/th_api
    ${SM_ROOT}/examples/selfhosted)

# ---- mbedTLS sources ----
file(GLOB MBEDTLS_SOURCES ${MBEDTLS_ROOT}/library/*.c)
# exclude platform-specific files not needed for the crypto-only benchmark
list(FILTER MBEDTLS_SOURCES EXCLUDE REGEX "entropy_poll|net_sockets|timing\\.c$")
target_sources(${MCUX_SDK_PROJECT_NAME} PRIVATE ${MBEDTLS_SOURCES})
target_include_directories(${MCUX_SDK_PROJECT_NAME} PRIVATE ${MBEDTLS_ROOT})
# enable float printf (%f) with newlib-nano
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -u _printf_float -Wl,--defsym=__stack_size__=0x18000 -Wl,--defsym=__heap_size__=0x18000")
# mbedTLS needs -O2 for its inline asm (MULADDC) to compile on M33
set_source_files_properties(${MBEDTLS_SOURCES} PROPERTIES COMPILE_OPTIONS "-O2")

# ---- flags ----
mcux_add_macro(CC "-DEE_CFG_SELFHOSTED=1 -DEE_CFG_BAREMETAL=1 -DEE_CFG_QUIET=0 -DMBEDTLS_NO_ASM")
mcux_add_macro(CX "-DEE_CFG_SELFHOSTED=1 -DEE_CFG_BAREMETAL=1 -DEE_CFG_QUIET=0 -DMBEDTLS_NO_ASM")
