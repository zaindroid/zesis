/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Re-run of KQ5 (NPU-vs-crypto resource contention) with the REAL trained,
 * quantized, conformally-calibrated GTSRB multi-exit classifier
 * (gtsrb_multiexit/segments/) chained on core 0, instead of the toy
 * cifarnet demo model used for the original feasibility-sprint measurement.
 * Core 1 runs the same ML-KEM-768 hammering loop as npu_dc (secondary/
 * main.c, CORE1_CRYPTO toggle) completely unchanged.
 *
 * This is deliberately NOT the contention-aware exit policy yet -- no
 * inter-core communication exists here (matches npu_dc: MCMGR only boots
 * core 1, no runtime IPC channel). This build only re-confirms KQ5's
 * zero-resource-contention result holds for the real model, before any
 * policy/IPC layer is designed.
 */
extern "C" {
#include "fsl_debug_console.h"
#include "board.h"
#include "app.h"
#include "mcmgr.h"
#include <string.h>
}

#include "board_init.h"
#include "segments.h"
#include "golden_input.h"
#include "timer.h"

#include <math.h>

#define NUM_CLASSES 43
#define NUM_ITER 100

#define TAU1 0.957f
#define TAU2 0.926f

static int Softmax(const TfLiteTensor* t, float* outProbs)
{
    float scale = t->params.scale;
    int32_t zp = t->params.zero_point;
    float maxLogit = -1e30f;
    float logits[NUM_CLASSES];
    for (int i = 0; i < NUM_CLASSES; i++)
    {
        logits[i] = ((float)t->data.int8[i] - (float)zp) * scale;
        if (logits[i] > maxLogit) { maxLogit = logits[i]; }
    }
    float sum = 0.0f;
    for (int i = 0; i < NUM_CLASSES; i++)
    {
        outProbs[i] = expf(logits[i] - maxLogit);
        sum += outProbs[i];
    }
    int argmax = 0;
    float best = -1.0f;
    for (int i = 0; i < NUM_CLASSES; i++)
    {
        outProbs[i] /= sum;
        if (outProbs[i] > best) { best = outProbs[i]; argmax = i; }
    }
    return argmax;
}

int main(void)
{
    (void)MCMGR_Init();
    BOARD_Init();
    TIMER_Init();

    PRINTF("KQ5 re-run: real GTSRB multi-exit model, dual-core, "
           "core1=ML-KEM-768 hammer\r\n");

    bool ok = true;
    ok = SEGA_Init() && ok;
    ok = SEGB_Init() && ok;
    ok = SEGC_Init() && ok;
    if (!ok)
    {
        PRINTF("Segment init failed\r\n");
        for (;;) {}
    }

    /* Boot core 1 (crypto hammer) -- identical sequence to npu_dc's
     * original main.cpp; no runtime IPC, core 1 just runs independently
     * from here on (see secondary/main.c). */
#ifdef CORE1_IMAGE_COPY_TO_RAM
    uint32_t core1_image_size = get_core1_image_size();
    (void)PRINTF("Copy core1 image to 0x%x, size %d\r\n",
                 (void *)(char *)CORE1_BOOT_ADDRESS, core1_image_size);
    (void)memcpy((void *)(char *)CORE1_BOOT_ADDRESS, (void *)CORE1_IMAGE_START, core1_image_size);
#endif
    (void)PRINTF("Starting core 1 (crypto)...\r\n");
    (void)MCMGR_StartCore(kMCMGR_Core1, (void *)(char *)CORE1_BOOT_ADDRESS, 2, kMCMGR_Start_Synchronous);
    (void)PRINTF("Core 1 started.\r\n");

    PRINTF("golden test image loaded, true_label=%d\r\n", (int)GOLDEN_TRUE_LABEL);

    /* Free-running timed loop: same fixed input every iteration (matches
     * the KQ5 methodology -- fixed workload, measure latency impact of
     * contention, not accuracy). Core 1 has been hammering crypto since
     * before this loop starts. */
    PRINTF("iter,segA_us,copy1_us,segB_us,copy2_us,segC_us,total_us,"
           "exit1_conf,exit1_accept,exit2_conf,exit2_accept,exit3_conf,exit3_pred\r\n");

    float probs[NUM_CLASSES];
    for (int iter = 0; iter < NUM_ITER; iter++)
    {
        memcpy(SEGA_Input()->data.int8, golden_image_int8, sizeof(golden_image_int8));

        uint32_t t0 = TIMER_GetTimeInUS();
        SEGA_Invoke();
        uint32_t t1 = TIMER_GetTimeInUS();

        int pred1 = Softmax(SEGA_OutputLogits(), probs);
        float conf1 = probs[pred1];
        bool accept1 = conf1 >= TAU1;

        TfLiteTensor* segAFeatures = SEGA_OutputFeatures();
        uint32_t t2 = TIMER_GetTimeInUS();
        memcpy(SEGB_Input()->data.int8, segAFeatures->data.int8, segAFeatures->bytes);
        uint32_t t3 = TIMER_GetTimeInUS();

        SEGB_Invoke();
        uint32_t t4 = TIMER_GetTimeInUS();

        int pred2 = Softmax(SEGB_OutputLogits(), probs);
        float conf2 = probs[pred2];
        bool accept2 = conf2 >= TAU2;

        TfLiteTensor* segBFeatures = SEGB_OutputFeatures();
        uint32_t t5 = TIMER_GetTimeInUS();
        memcpy(SEGC_Input()->data.int8, segBFeatures->data.int8, segBFeatures->bytes);
        uint32_t t6 = TIMER_GetTimeInUS();

        SEGC_Invoke();
        uint32_t t7 = TIMER_GetTimeInUS();

        int pred3 = Softmax(SEGC_OutputLogits(), probs);
        float conf3 = probs[pred3];

        int segA_us = (int)(t1 - t0);
        int copy1_us = (int)(t3 - t2);
        int segB_us = (int)(t4 - t3);
        int copy2_us = (int)(t6 - t5);
        int segC_us = (int)(t7 - t6);
        int total_us = (int)(t7 - t0);

        PRINTF("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\r\n",
               iter, segA_us, copy1_us, segB_us, copy2_us, segC_us, total_us,
               (int)(conf1 * 1000), (int)accept1, (int)(conf2 * 1000), (int)accept2,
               (int)(conf3 * 1000), pred3);
    }

    PRINTF("done\r\n");
    for (;;) {}
}
