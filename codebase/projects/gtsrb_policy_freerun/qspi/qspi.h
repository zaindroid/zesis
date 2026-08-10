/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Minimal W25Q64 (8MB quad SPI NOR) driver over FLEXSPI0 for the
 * free-running interleaved experiment. Two capabilities:
 *
 *  - QSPI_Init(): bring up FlexSPI0 at 75MHz with the W25Q64 config (same
 *    FCB/LUT scheme as the SDK flexspi_nor example for FRDM-MCXN947), then
 *    leave the flash in memory-mapped (AHB) mode so QSPI_Read() is a plain
 *    memcpy from the 0x80000000 alias.
 *  - QSPI_EraseSector()/QSPI_PageProgram(): used ONLY by the one-time burn
 *    step (host streams the workload blob over UART; this driver writes it
 *    to the external flash). Burn happens with serial connected, before any
 *    measurement; the measurement firmware only uses the memory-mapped read.
 *
 * Layout (burned once, then read-only for the experiment):
 *   frame i  ->  offset i * 6912  (48x48x3 INT8), i in [0, 1200)
 */
#ifndef _QSPI_H_
#define _QSPI_H_

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

#if defined(__cplusplus)
extern "C" {
#endif

#define QSPI_FLASH_BASE 0x80000000UL
#define QSPI_IMAGE_BYTES 6912

bool QSPI_Init(void);
void QSPI_Read(uint32_t offset, void* dst, size_t len);
bool QSPI_EraseSector(uint32_t offset);
bool QSPI_PageProgram(uint32_t offset, const void* src, size_t len);
bool QSPI_Verify(uint32_t offset, const void* src, size_t len);

#if defined(__cplusplus)
}
#endif

#endif /* _QSPI_H_ */
