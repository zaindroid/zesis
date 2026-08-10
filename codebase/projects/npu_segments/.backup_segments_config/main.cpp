/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * NPU segmentation-overhead experiment.
 *
 * Runs the SAME toy 3-block CNN (A -> B -> C) in three configurations, all in
 * one boot, free-running:
 *   1) monolithic : one NPU dispatch for the whole graph
 *   2) 2-segment  : AB dispatched, feature map requantize-copied, C dispatched
 *   3) 3-segment  : A, B, C each dispatched separately, with requantize-copy
 *                   of the feature map between each pair
 *
 * 100 timed iterations per configuration. The gap between the monolithic
 * mean and each segmented configuration's mean is the per-boundary NPU
 * dispatch + intermediate-activation-handling overhead.
 */
#include "board_init.h"
#include "fsl_debug_console.h"
#include "timer.h"
#include "segments.h"

static void FillInputFromPattern(TfLiteTensor* t)
{
    float scale = t->params.scale;
    int32_t zp = t->params.zero_point;
    int n = (int)t->bytes;
    for (int i = 0; i < n; i++)
    {
        float v = 0.1f + 0.008f * (float)(i % 100); /* deterministic ramp in [0.1, 0.892] */
        int32_t q = (int32_t)(v / scale + 0.5f) + zp;
        if (q < -128) q = -128;
        if (q > 127) q = 127;
        t->data.int8[i] = (int8_t)q;
    }
}

static void RequantizeCopy(TfLiteTensor* src, TfLiteTensor* dst)
{
    float srcScale = src->params.scale;
    int32_t srcZp = src->params.zero_point;
    float dstScale = dst->params.scale;
    int32_t dstZp = dst->params.zero_point;
    int n = (int)src->bytes;
    for (int i = 0; i < n; i++)
    {
        float real = (float)((int32_t)src->data.int8[i] - srcZp) * srcScale;
        float scaled = real / dstScale;
        int32_t q = (int32_t)(scaled >= 0.0f ? scaled + 0.5f : scaled - 0.5f) + dstZp;
        if (q < -128) q = -128;
        if (q > 127) q = 127;
        dst->data.int8[i] = (int8_t)q;
    }
}

#define NUM_ITER 100

int main(void)
{
    BOARD_Init();
    TIMER_Init();

    PRINTF("NPU segmentation overhead experiment\r\n");

    bool ok = true;
    ok = MONO_Init() && ok;
    ok = SEGAB_Init() && ok;
    ok = SEGA_Init() && ok;
    ok = SEGB_Init() && ok;
    ok = SEGC_Init() && ok;
    if (!ok)
    {
        PRINTF("Model init failed\r\n");
        for (;;) {}
    }

    FillInputFromPattern(MONO_Input());
    FillInputFromPattern(SEGAB_Input());
    FillInputFromPattern(SEGA_Input());

    PRINTF("phase,iteration,total_us\r\n");

    for (int i = 0; i < NUM_ITER; i++)
    {
        auto t0 = TIMER_GetTimeInUS();
        MONO_Invoke();
        auto t1 = TIMER_GetTimeInUS();
        PRINTF("mono,%d,%d\r\n", i, (int)(t1 - t0));
    }

    for (int i = 0; i < NUM_ITER; i++)
    {
        auto t0 = TIMER_GetTimeInUS();
        SEGAB_Invoke();
        RequantizeCopy(SEGAB_Output(), SEGC_Input());
        SEGC_Invoke();
        auto t1 = TIMER_GetTimeInUS();
        PRINTF("seg2,%d,%d\r\n", i, (int)(t1 - t0));
    }

    for (int i = 0; i < NUM_ITER; i++)
    {
        auto t0 = TIMER_GetTimeInUS();
        SEGA_Invoke();
        RequantizeCopy(SEGA_Output(), SEGB_Input());
        SEGB_Invoke();
        RequantizeCopy(SEGB_Output(), SEGC_Input());
        SEGC_Invoke();
        auto t1 = TIMER_GetTimeInUS();
        PRINTF("seg3,%d,%d\r\n", i, (int)(t1 - t0));
    }

    PRINTF("done\r\n");
    for (;;) {}
}
