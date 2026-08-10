
# Copyright 2026 NXP
#
# SPDX-License-Identifier: BSD-3-Clause


externalzephyrproject_add(
    
    APPLICATION hello_world_secondary_core
    SOURCE_DIR ${APP_DIR}/../secondary
    core_id cm33_core1
    config debug
    toolchain armgcc
)
add_dependencies(${DEFAULT_IMAGE} hello_world_secondary_core)
