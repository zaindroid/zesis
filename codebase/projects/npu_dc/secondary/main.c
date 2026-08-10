/*
 * Copyright (c) 2015, Freescale Semiconductor, Inc.
 * Copyright 2016-2025 NXP
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include "board.h"
#include "app.h"
#include "mcmgr.h"

/* 0 = core 1 idles (baseline run), 1 = core 1 hammers ML-KEM-768 continuously (contention run) */
#define CORE1_CRYPTO 1

#if CORE1_CRYPTO
#include "api.h"
#include "randombytes.h"
#endif

/*******************************************************************************
 * Code
 ******************************************************************************/
/*!
 * @brief Main function
 */
int main(void)
{
    uint32_t startupData, i;
    mcmgr_status_t status;

    /* Init board hardware.*/
    BOARD_InitHardware();

    /* Initialize MCMGR, install generic event handlers */
    (void)MCMGR_Init();

    /* Get the startup data */
    do
    {
        status = MCMGR_GetStartupData(kMCMGR_Core0, &startupData);
    } while (status != kStatus_MCMGR_Success);

    /* Make a noticable delay after the reset */
    /* Use startup parameter from the master core... */
    for (i = 0; i < startupData; i++)
    {
        SDK_DelayAtLeastUs(1000000U, SDK_DEVICE_MAXIMUM_CPU_CLOCK_FREQUENCY);
    }

    /* Configure LED */
    LED_INIT();

#if CORE1_CRYPTO
    static uint8_t pk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_PUBLICKEYBYTES];
    static uint8_t sk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_SECRETKEYBYTES];
    static uint8_t ct[PQCLEAN_MLKEM768_CLEAN_CRYPTO_CIPHERTEXTBYTES];
    static uint8_t ss_enc[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
    static uint8_t ss_dec[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];

    (void)PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(pk, sk);

    /* Continuous encaps/decaps loop -- memory-contention noise for core 0's NPU inference */
    for (;;)
    {
        (void)PQCLEAN_MLKEM768_CLEAN_crypto_kem_enc(ct, ss_enc, pk);
        (void)PQCLEAN_MLKEM768_CLEAN_crypto_kem_dec(ss_dec, ct, sk);
        LED_TOGGLE();
    }
#else
    for (;;)
    {
        SDK_DelayAtLeastUs(500000U, SDK_DEVICE_MAXIMUM_CPU_CLOCK_FREQUENCY);
        LED_TOGGLE();
    }
#endif
}
