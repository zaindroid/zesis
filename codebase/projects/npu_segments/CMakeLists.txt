
# Copyright 2026 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

cmake_minimum_required(VERSION 3.22.0)

cmake_path(APPEND conf_file_path ${CMAKE_CURRENT_LIST_DIR} ${board}_${core_id} prj.conf)
set(CONF_FILE ${conf_file_path} ${CONF_FILE})
include(${SdkRootDirPath}/cmake/extension/mcux.cmake)

project(npu_segments LANGUAGES C CXX ASM PROJECT_BOARD_PORT_PATH ${board_root}/${board}/eiq_examples/tflm_cifar10)


mcux_add_include(
    INCLUDES .
             common
             segments
)

mcux_add_source(
    SOURCES common/board_init.h
            common/timer.c
            common/timer.h
            main.cpp
            segments/segments.h
            segments/model_mono.cpp
            segments/model_data_mono.h
            segments/model_AB.cpp
            segments/model_data_AB.h
            segments/model_A.cpp
            segments/model_data_A.h
            segments/model_B.cpp
            segments/model_data_B.h
            segments/model_C.cpp
            segments/model_data_C.h
            segments/model_C1.cpp
            segments/model_data_C1.h
            segments/model_C2.cpp
            segments/model_data_C2.h
)
include(${SdkRootDirPath}/CMakeLists.txt)


include("${board}_${core_id}/board_files.cmake")

mcux_remove_iar_linker_script(
  BASE_PATH ${SdkRootDirPath}
  TARGETS flash_debug flash_release
  LINKER ${device_root}/MCX/MCXN/MCXN947/iar/MCXN947_cm33_core0_flash.icf
  )

mcux_remove_mdk_linker_script(
  BASE_PATH ${SdkRootDirPath}
  TARGETS flash_debug flash_release
  LINKER ${device_root}/MCX/MCXN/MCXN947/arm/MCXN947_cm33_core0_flash.scf
  )

mcux_remove_armgcc_linker_script(
  BASE_PATH ${SdkRootDirPath}
  TARGETS flash_debug flash_release
  LINKER ${device_root}/MCX/MCXN/MCXN947/gcc/MCXN947_cm33_core0_flash.ld
  )


mcux_add_iar_linker_script(
    LINKER linker_files/MCXN947_cm33_core0_flash.icf
    TARGETS flash_debug flash_release
)

mcux_add_mdk_linker_script(
    LINKER linker_files/MCXN947_cm33_core0_flash.scf
    TARGETS flash_debug flash_release
)

mcux_add_armgcc_linker_script(
    LINKER linker_files/MCXN947_cm33_core0_flash.ld
    TARGETS flash_debug flash_release
)
mcux_add_iar_configuration(
  CC "--diag_suppress=Pe260,Pe1031"
  )

mcux_remove_iar_configuration(
  TARGETS release
  CC "-Oh"
  )

mcux_add_iar_configuration(
  TARGETS release
  CC "-Ohs"
  )

mcux_add_mdk_configuration(
  LD "--diag_suppress=6439,6776"
  )

mcux_add_mdk_configuration(
  TARGETS release
  CC "-O3"
  )

mcux_add_armgcc_configuration(
  TARGETS release
  CC "-O3"
  CX "-O3"
  )

mcux_add_macro(
  CC "-DSDK_DEBUGCONSOLE_UART\
  -DARM_MATH_CM33\
  -D__FPU_PRESENT=1"
  CX "-DSDK_DEBUGCONSOLE_UART\
  -DARM_MATH_CM33\
  -D__FPU_PRESENT=1"
  )

mcux_remove_iar_configuration(
  TARGETS release
  CC "-Om"
  )

mcux_remove_mdk_configuration(
  CC "-fshort-wchar"
  CX "-fshort-wchar"
  )

mcux_remove_mdk_configuration(
  TARGETS release
  CC "-Oz"
  )

mcux_remove_armgcc_configuration(
  TARGETS release
  CC "-Os"
  CX "-Os"
  )

mcux_add_iar_configuration(
  LD "--config_def=__stack_size__=0x8000"
  )

mcux_add_mdk_configuration(
  LD "--predefine=\"-D__stack_size__=0x8000\""
  )

mcux_add_armgcc_configuration(
  LD "-Xlinker --defsym=__stack_size__=0x8000"
  )

mcux_add_mcux_configuration(
  LD "-Xlinker --defsym=__heap_size__=0x8000\
      -Xlinker --defsym=__stack_size__=0x8000"
)

mcux_add_mdk_configuration(LD "--library_type=standardlib")

mcux_convert_binary(BINARY ${APPLICATION_BINARY_DIR}/${MCUX_SDK_PROJECT_NAME}.bin)


mcux_add_include(INCLUDES tflm)

