# SecureMark-V2 harness with post-quantum suites, bare-metal FRDM-MCXN947.
#
# Reuses the upstream securemark-v2 self-hosted harness (profile/ee_*.c and
# profile/wolfssl_th_api/th_*.c) with two additions:
#   - profile/ee_pqc.c + profile/th_pqc_support.c  (PQC bench layer + support)
#   - profile/wolfssl_th_api/th_mlkem.c / th_mldsa.c (primitive shims)
# and a bare-metal platform patch in examples/selfhosted/main.c
# (DWT timestamp instead of clock_gettime) plus retarget.c for printf.
#
# Sources are added via target_sources with absolute paths: mcux_add_source
# prepends the project directory and breaks absolute paths.

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(securemark_v2_pqc LANGUAGES C CXX ASM
        PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)
include("${board}_${core_id}/board_files.cmake")

set(SMV2 "${CMAKE_CURRENT_LIST_DIR}/../../../securemark-v2")
set(THAPI "${SMV2}/examples/selfhosted/profile/wolfssl_th_api")
set(WOLFSSL_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../wolfssl")
set(WOLFSSL_US   "${CMAKE_CURRENT_LIST_DIR}/../wolfssl-m33")

target_sources(${MCUX_SDK_PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}/retarget.c"
    "${SMV2}/examples/selfhosted/main.c"
    "${SMV2}/monitor/ee_main.c"
    "${SMV2}/monitor/th_api/th_lib.c"
    "${SMV2}/monitor/th_api/th_libc.c"
    "${SMV2}/profile/ee_aes.c"
    "${SMV2}/profile/ee_bench.c"
    "${SMV2}/profile/ee_buffer.c"
    "${SMV2}/profile/ee_chachapoly.c"
    "${SMV2}/profile/ee_profile.c"
    "${SMV2}/profile/ee_sha.c"
    "${SMV2}/profile/ee_util.c"
    "${SMV2}/profile/ee_variations.c"
    "${SMV2}/examples/selfhosted/profile/ee_pqc.c"
    "${SMV2}/examples/selfhosted/profile/th_pqc_support.c"
    "${THAPI}/th_aes.c"
    "${THAPI}/th_chachapoly.c"
    "${THAPI}/th_ecdh.c"
    "${THAPI}/th_ecdsa.c"
    "${THAPI}/th_rng.c"
    "${THAPI}/th_rsa.c"
    "${THAPI}/th_sha.c"
    "${THAPI}/th_util.c"
    "${THAPI}/th_mlkem.c"
    "${THAPI}/th_mldsa.c"
)

mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )

target_include_directories(${MCUX_SDK_PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}"
    "${SMV2}/examples/selfhosted"
    "${SMV2}/examples/selfhosted/profile"
    "${THAPI}"
    "${SMV2}/profile"
    "${SMV2}/profile/th_api"
    "${SMV2}/monitor"
    "${SMV2}/monitor/th_api"
    "${WOLFSSL_ROOT}"
    "${WOLFSSL_US}"
)

target_compile_definitions(${MCUX_SDK_PROJECT_NAME} PRIVATE
    EE_CFG_SELFHOSTED=1
    EE_CFG_QUIET=1
    WOLFSSL_USER_SETTINGS
)
# wolfSSL emits an advisory #warning about harden options; not an error.
# Methodology: every primitive at -O2 (overrides the SDK -Os).
target_compile_options(${MCUX_SDK_PROJECT_NAME} PRIVATE -O2 -Wno-error=cpp -Wno-error=maybe-uninitialized -Wno-error=format -Wno-error=incompatible-pointer-types)

target_link_libraries(${MCUX_SDK_PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}/../wolfssl-m33/build/libwolfssl_crypto.a"
)

# 96 KB stack (below the MSPLIM trip point) + float printf for the ips columns.
set(CMAKE_EXE_LINKER_FLAGS
    "${CMAKE_EXE_LINKER_FLAGS} -Wl,--defsym=__stack_size__=0x18000 -u _printf_float")
