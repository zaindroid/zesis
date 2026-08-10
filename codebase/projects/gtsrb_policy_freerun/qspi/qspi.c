/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * W25Q64 over FLEXSPI0 implementation. Uses the same device config and LUT
 * scheme as the SDK's flexspi_nor example for FRDM-MCXN947 (W25Q64, 4-pad,
 * 75MHz, read command 0xEB quad fast read). See qspi.h for the API contract.
 */
#include "qspi.h"
#include "board.h"
#include "fsl_clock.h"
#include "fsl_common.h"
#include "fsl_flexspi.h"
#include "fsl_debug_console.h"
#include <string.h>

#define EXAMPLE_FLEXSPI FLEXSPI0
#define FLASH_PORT      kFLEXSPI_PortA1
#define FLASH_SIZE      (8u * 1024u * 1024u)
#define SECTOR_SIZE     4096u
#define PAGE_SIZE       256u

/* LUT index layout (matches the SDK flexspi_nor example). */
#define LUT_SEQ_IDX_READ          0u
#define LUT_SEQ_IDX_READSTATUS    1u
#define LUT_SEQ_IDX_WRITEENABLE   2u
#define LUT_SEQ_IDX_ERASE_SECTOR  3u
#define LUT_SEQ_IDX_PAGE_PROGRAM  4u
#define CUSTOM_LUT_LENGTH         (5u * 4u)

static flexspi_device_config_t s_deviceconfig = {
    .flexspiRootClk       = 75000000U,
    .flashSize            = FLASH_SIZE,
    .CSIntervalUnit       = kFLEXSPI_CsIntervalUnit1SckCycle,
    .CSInterval           = 2,
    .CSHoldTime           = 3,
    .CSSetupTime          = 3,
    .dataValidTime        = 2,
    .columnspace          = 0,
    .enableWordAddress    = false,
    .AWRSeqIndex          = LUT_SEQ_IDX_PAGE_PROGRAM,
    .AWRSeqNumber         = 1,
    .ARDSeqIndex          = LUT_SEQ_IDX_READ,
    .ARDSeqNumber         = 1,
    .AHBWriteWaitUnit     = kFLEXSPI_AhbWriteWaitUnit2AhbCycle,
    .AHBWriteWaitInterval = 0,
    .enableWriteMask      = false,
};

static const uint32_t s_customLUT[CUSTOM_LUT_LENGTH] = {
    /* Read: 0xEB quad fast read, 4-pad addr, 8 dummy, 4-pad data */
    [4 * LUT_SEQ_IDX_READ + 0] =
        FLEXSPI_LUT_SEQ(kFLEXSPI_Command_SDR, kFLEXSPI_1PAD, 0xEB, kFLEXSPI_Command_RADDR_SDR, kFLEXSPI_4PAD, 0x18),
    [4 * LUT_SEQ_IDX_READ + 1] =
        FLEXSPI_LUT_SEQ(kFLEXSPI_Command_DUMMY_SDR, kFLEXSPI_4PAD, 0x08, kFLEXSPI_Command_READ_SDR, kFLEXSPI_4PAD, 0x04),
    /* Read status register -- 1 byte, matches xfer.dataSize=1 in
     * flexspi_nor_wait_bus_busy(). */
    [4 * LUT_SEQ_IDX_READSTATUS + 0] =
        FLEXSPI_LUT_SEQ(kFLEXSPI_Command_SDR, kFLEXSPI_1PAD, 0x05, kFLEXSPI_Command_READ_SDR, kFLEXSPI_1PAD, 0x01),
    /* Write enable */
    [4 * LUT_SEQ_IDX_WRITEENABLE + 0] =
        FLEXSPI_LUT_SEQ(kFLEXSPI_Command_SDR, kFLEXSPI_1PAD, 0x06, kFLEXSPI_Command_STOP, kFLEXSPI_1PAD, 0x00),
    /* Erase sector (4KB) */
    [4 * LUT_SEQ_IDX_ERASE_SECTOR + 0] =
        FLEXSPI_LUT_SEQ(kFLEXSPI_Command_SDR, kFLEXSPI_1PAD, 0x20, kFLEXSPI_Command_RADDR_SDR, kFLEXSPI_1PAD, 0x18),
    /* Page program (256B) */
    [4 * LUT_SEQ_IDX_PAGE_PROGRAM + 0] =
        FLEXSPI_LUT_SEQ(kFLEXSPI_Command_SDR, kFLEXSPI_1PAD, 0x02, kFLEXSPI_Command_RADDR_SDR, kFLEXSPI_1PAD, 0x18),
    [4 * LUT_SEQ_IDX_PAGE_PROGRAM + 1] =
        FLEXSPI_LUT_SEQ(kFLEXSPI_Command_WRITE_SDR, kFLEXSPI_1PAD, 0x04, kFLEXSPI_Command_STOP, kFLEXSPI_1PAD, 0x00),
};

static status_t flexspi_nor_wait_bus_busy(void)
{
    uint32_t status;
    /* Clear any pending AHB buffered reads before issuing an IP command --
     * a stale AHB transaction can otherwise make the IP command sequence
     * fail immediately. */
    FLEXSPI_SoftwareReset(EXAMPLE_FLEXSPI);
    do
    {
        flexspi_transfer_t xfer = {0};
        xfer.deviceAddress = 0;
        xfer.port = FLASH_PORT;
        xfer.cmdType = kFLEXSPI_Read;
        xfer.SeqNumber = 1;
        xfer.seqIndex = LUT_SEQ_IDX_READSTATUS;
        xfer.data = &status;
        xfer.dataSize = 1;
        if (FLEXSPI_TransferBlocking(EXAMPLE_FLEXSPI, &xfer) != kStatus_Success)
        {
            return kStatus_Fail;
        }
        if ((status & 0x01u) == 0u) /* WIP=0: idle */
        {
            break;
        }
    } while (1);
    return kStatus_Success;
}

static status_t flexspi_nor_write_enable(void)
{
    flexspi_transfer_t xfer = {0};
    xfer.deviceAddress = 0;
    xfer.port = FLASH_PORT;
    xfer.cmdType = kFLEXSPI_Command;
    xfer.SeqNumber = 1;
    xfer.seqIndex = LUT_SEQ_IDX_WRITEENABLE;
    return FLEXSPI_TransferBlocking(EXAMPLE_FLEXSPI, &xfer);
}

bool QSPI_Init(void)
{
    flexspi_config_t config;

    /* FlexSPI root clock: PLL0 150MHz / 2 = 75MHz (same as SDK example).
     * Re-attaching the FlexSPI clock mux disrupts the debug-UART clock
     * (both share a clock-select resource) -- the SDK's own reference
     * FlexSPI example (examples/driver_examples/flexspi/octal/
     * polling_transfer/.../hardware_init.c) defensively re-attaches
     * BOARD_DEBUG_UART_CLK_ATTACH immediately before touching FlexSPI's
     * clock for exactly this reason. Without this, every PRINTF after
     * QSPI_Init() (i.e. all of them, since this runs first in main())
     * silently produces no UART output even though the firmware is
     * otherwise running normally. */
    CLOCK_AttachClk(BOARD_DEBUG_UART_CLK_ATTACH);
    CLOCK_SetClkDiv(kCLOCK_DivFlexcom4Clk, 1u);
    CLOCK_AttachClk(kPLL0_to_FLEXSPI);
    CLOCK_SetClkDiv(kCLOCK_DivFlexspiClk, 2U);

    /* Copy LUT to RAM first (updating LUT from flash could corrupt the read
     * sequence while we are executing from flash). */
    uint32_t tempLUT[CUSTOM_LUT_LENGTH];
    memcpy(tempLUT, s_customLUT, sizeof(tempLUT));

    FLEXSPI_GetDefaultConfig(&config);
    config.ahbConfig.enableAHBPrefetch = true;
    config.ahbConfig.enableAHBBufferable = true;
    config.ahbConfig.enableReadAddressOpt = true;
    config.ahbConfig.enableAHBCachable = true;
    config.rxSampleClock = kFLEXSPI_ReadSampleClkLoopbackFromDqsPad;
    FLEXSPI_Init(EXAMPLE_FLEXSPI, &config);

    FLEXSPI_SetFlashConfig(EXAMPLE_FLEXSPI, &s_deviceconfig, FLASH_PORT);
    FLEXSPI_UpdateLUT(EXAMPLE_FLEXSPI, 0, tempLUT, CUSTOM_LUT_LENGTH);
    FLEXSPI_SoftwareReset(EXAMPLE_FLEXSPI);
    return true;
}

void QSPI_Read(uint32_t offset, void* dst, size_t len)
{
    memcpy(dst, (const void*)(QSPI_FLASH_BASE + offset), len);
}

bool QSPI_EraseSector(uint32_t offset)
{
    status_t st;
    st = flexspi_nor_wait_bus_busy();
    if (st != kStatus_Success)
    {
        PRINTF("ERASE fail: pre wait_bus_busy status=%d\r\n", (int)st);
        return false;
    }
    st = flexspi_nor_write_enable();
    if (st != kStatus_Success)
    {
        PRINTF("ERASE fail: write_enable status=%d\r\n", (int)st);
        return false;
    }
    flexspi_transfer_t xfer = {0};
    xfer.deviceAddress = offset;
    xfer.port = FLASH_PORT;
    xfer.cmdType = kFLEXSPI_Command;
    xfer.SeqNumber = 1;
    xfer.seqIndex = LUT_SEQ_IDX_ERASE_SECTOR;
    st = FLEXSPI_TransferBlocking(EXAMPLE_FLEXSPI, &xfer);
    if (st != kStatus_Success)
    {
        PRINTF("ERASE fail: erase transfer status=%d offset=%u\r\n", (int)st, (unsigned)offset);
        return false;
    }
    st = flexspi_nor_wait_bus_busy();
    if (st != kStatus_Success)
    {
        PRINTF("ERASE fail: post wait_bus_busy status=%d\r\n", (int)st);
        return false;
    }
    /* Clear AHB buffers so subsequent memory-mapped reads see fresh data. */
    FLEXSPI_SoftwareReset(EXAMPLE_FLEXSPI);
    return true;
}

bool QSPI_PageProgram(uint32_t offset, const void* src, size_t len)
{
    if (len > PAGE_SIZE || (offset % PAGE_SIZE) != 0)
    {
        return false;
    }
    if (flexspi_nor_wait_bus_busy() != kStatus_Success ||
        flexspi_nor_write_enable() != kStatus_Success)
    {
        return false;
    }
    flexspi_transfer_t xfer = {0};
    xfer.deviceAddress = offset;
    xfer.port = FLASH_PORT;
    xfer.cmdType = kFLEXSPI_Write;
    xfer.SeqNumber = 1;
    xfer.seqIndex = LUT_SEQ_IDX_PAGE_PROGRAM;
    xfer.data = (uint32_t*)(uintptr_t)src;
    xfer.dataSize = len;
    if (FLEXSPI_TransferBlocking(EXAMPLE_FLEXSPI, &xfer) != kStatus_Success)
    {
        return false;
    }
    if (flexspi_nor_wait_bus_busy() != kStatus_Success)
    {
        return false;
    }
    /* Clear AHB buffers so subsequent memory-mapped reads see fresh data. */
    FLEXSPI_SoftwareReset(EXAMPLE_FLEXSPI);
    return true;
}

bool QSPI_Verify(uint32_t offset, const void* src, size_t len)
{
    /* Flush AHB read buffers: with AHB caching enabled, a memory-mapped read
     * right after a write/erase can return stale data. */
    FLEXSPI_SoftwareReset(EXAMPLE_FLEXSPI);
    return memcmp((const void*)(QSPI_FLASH_BASE + offset), src, len) == 0;
}
