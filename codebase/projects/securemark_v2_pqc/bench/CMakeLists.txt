# Standalone PQC bench: native wolfSSL ML-KEM/ML-DSA on FRDM-MCXN947.
# Links the crypto-only wolfSSL static library built in ../wolfssl-m33.

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(pqc_bench_wolfssl LANGUAGES C CXX ASM
        PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)
include("${board}_${core_id}/board_files.cmake")

mcux_add_source(
    SOURCES main_pqc.c
            v2th/th_mlkem.c
            v2th/th_mldsa.c
)
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )

# wolfSSL headers, the user_settings.h directory, and the shim headers.
set(WOLFSSL_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../wolfssl")
set(WOLFSSL_US   "${CMAKE_CURRENT_LIST_DIR}/../wolfssl-m33")

target_include_directories(${MCUX_SDK_PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}"
    "${CMAKE_CURRENT_LIST_DIR}/v2th"
    "${WOLFSSL_ROOT}"
    "${WOLFSSL_US}"
)
target_compile_definitions(${MCUX_SDK_PROJECT_NAME} PRIVATE WOLFSSL_USER_SETTINGS)
# wolfSSL emits an advisory #warning about harden options; not an error.
target_compile_options(${MCUX_SDK_PROJECT_NAME} PRIVATE -Wno-error=cpp)

# Native wolfSSL crypto library (ML-KEM + ML-DSA), built crypto-only.
target_link_libraries(${MCUX_SDK_PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}/../wolfssl-m33/build/libwolfssl_crypto.a"
)

# ML-DSA signing needs ~120KB peak stack; the SDK default is 32KB.
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--defsym=__stack_size__=0x18000")
