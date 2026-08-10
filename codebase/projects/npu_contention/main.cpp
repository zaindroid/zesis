/*
 * Copyright 2020-2022 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 */
#include "board_init.h"
#include "demo_config.h"
#include "demo_info.h"
#include "fsl_debug_console.h"
#include "image.h"
#include "image_utils.h"
#include "model.h"
#include "output_postproc.h"
#include "timer.h"

extern "C" {
#include "api.h"
}

/* 0 = baseline (NPU alone), 1 = contention (crypto before each inference) */
#define CRYPTO_ON 1

#if CRYPTO_ON
static uint8_t c_pk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t c_sk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t c_ct[PQCLEAN_MLKEM768_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t c_ss[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
#endif

int main(void)
{
    BOARD_Init();
    TIMER_Init();
    DEMO_PrintInfo();
    if (MODEL_Init() != kStatus_Success)
    {
        PRINTF("Failed initializing model" EOL);
        for (;;) {}
    }

    tensor_dims_t inputDims;
    tensor_type_t inputType;
    uint8_t* inputData = MODEL_GetInputTensorData(&inputDims, &inputType);
    tensor_dims_t outputDims;
    tensor_type_t outputType;
    uint8_t* outputData = MODEL_GetOutputTensorData(&outputDims, &outputType);

#if CRYPTO_ON
    PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(c_pk, c_sk);
    PRINTF("CRYPTO_ON: crypto runs before each inference\r\n");
#else
    PRINTF("BASELINE: NPU alone\r\n");
#endif

    while (1)
    {
        if (IMAGE_GetImage(inputData, inputDims.data[2], inputDims.data[1], inputDims.data[3]) != kStatus_Success)
        {
            PRINTF("Failed retrieving input image" EOL);
            for (;;) {}
        }
        MODEL_ConvertInput(inputData, &inputDims, inputType);

#if CRYPTO_ON
        /* Pound memory with crypto right before inference */
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_enc(c_ct, c_ss, c_pk);
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_dec(c_ss, c_ct, c_sk);
#endif

        auto startTime = TIMER_GetTimeInUS();
        MODEL_RunInference();
        auto endTime = TIMER_GetTimeInUS();
        MODEL_ProcessOutput(outputData, &outputDims, outputType, endTime - startTime);
    }
}