# Task 3A: 128 KB firmware signature verification on FRDM-MCXN947.
# Links the crypto-only wolfSSL static library built in ../wolfssl-m33.

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(task3a_fw_verify LANGUAGES C CXX ASM
        PROJECT_BOARD_PORT_PATH ${board_root}/${board}/demo_apps/hello_world)

include(${SdkRootDirPath}/CMakeLists.txt)
include("${board}_${core_id}/board_files.cmake")

mcux_add_source(SOURCES main_task3a.c)
mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)
mcux_add_config_mex_path( PATH ${board}_${core_id} )

set(WOLFSSL_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../wolfssl")
set(WOLFSSL_US   "${CMAKE_CURRENT_LIST_DIR}/../wolfssl-m33")

target_include_directories(${MCUX_SDK_PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}"
    "${WOLFSSL_ROOT}"
    "${WOLFSSL_US}"
)
target_compile_definitions(${MCUX_SDK_PROJECT_NAME} PRIVATE WOLFSSL_USER_SETTINGS)

# Methodology: -O2 for every primitive.
target_compile_options(${MCUX_SDK_PROJECT_NAME} PRIVATE
    -O2 -Wno-error=cpp -Wno-error=maybe-uninitialized -Wno-error=format
    -Wno-error=incompatible-pointer-types)

target_link_libraries(${MCUX_SDK_PROJECT_NAME} PRIVATE
    "${CMAKE_CURRENT_LIST_DIR}/../wolfssl-m33/build/libwolfssl_crypto.a"
)

# 64 KB stack + 96 KB static pool + the 128 KB payload buffer, inside m_data.
set(CMAKE_EXE_LINKER_FLAGS
    "${CMAKE_EXE_LINKER_FLAGS} -Wl,--defsym=__stack_size__=0x10000 -u _printf_float")
