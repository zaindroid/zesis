
# Copyright 2026 NXP
#
# SPDX-License-Identifier: BSD-3-Clause

mcux_add_configuration(
    CC "-DSDK_DEBUGCONSOLE=1"
    CX "-DSDK_DEBUGCONSOLE=1"
)


mcux_add_source(
    SOURCES frdmmcxn947/board.c
            frdmmcxn947/board.h
)

mcux_add_include(
    INCLUDES frdmmcxn947
)

mcux_add_source(
    SOURCES frdmmcxn947/clock_config.c
            frdmmcxn947/clock_config.h
)

mcux_add_include(
    INCLUDES frdmmcxn947
)

mcux_add_source(
    SOURCES cm33_core0/pin_mux.c
            cm33_core0/pin_mux.h
)

mcux_add_include(
    INCLUDES cm33_core0
)

mcux_add_source(
    SOURCES cm33_core0/app.h
            cm33_core0/hardware_init.c
)

mcux_add_include(
    INCLUDES cm33_core0
)

mcux_add_source(
    SOURCES driver_include/NeutronDriver.h
            include/NeutronErrors.h
)

mcux_add_include(
    INCLUDES driver_include
             include
)

mcux_add_library(
    LIBS mcxn/libNeutronDriver.a mcxn/libNeutronFirmware.a
    TOOLCHAINS armgcc mcux mdk iar
    DEVICE_IDS MCXN947 MCXN547
)
mcux_add_iar_configuration(
  LD "--diag_suppress Li026,Lt065,Lt066,Lt069"
  )

mcux_add_cmakelists(${SdkRootDirPath}/middleware/eiq/tensorflow-lite)

set(ETHOSU_STUB Y)

