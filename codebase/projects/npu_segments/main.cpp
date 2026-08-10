/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * NPU segmentation-overhead experiment.
 *
 * Runs the SAME toy 3-block CNN (A -> B -> C) in seven configurations, all in
 * one boot, free-running:
 *   1) monolithic : one NPU dispatch for the whole graph
 *   2) 2-segment  : AB dispatched, feature map requantize-copied, C dispatched
 *   3) 3-segment  : A, B, C each dispatched separately (2 boundaries)
 *   4) 4-segment  : A, B, C1, C2 each dispatched separately (3 boundaries) --
 *                   C is split further at its internal Conv/GAP+FC boundary
 *   5-7) same as 2/3/4 but using a fixed-point (Q16.16 integer multiply-shift)
 *        requantize copy instead of the naive per-element float divide, to
 *        separate "real" NPU dispatch overhead from CPU-side copy cost.
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

/* Naive baseline: float divide + round per element. */
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

/* Optimized: precomputed Q16.16 fixed-point multiplier, no float ops in the loop. */
struct FixedRequant
{
    int32_t multiplier; /* Q16.16 representation of srcScale/dstScale */
    int32_t srcZp;
    int32_t dstZp;
};

static FixedRequant MakeFixedRequant(TfLiteTensor* src, TfLiteTensor* dst)
{
    float ratio = src->params.scale / dst->params.scale;
    FixedRequant fr;
    fr.multiplier = (int32_t)(ratio * 65536.0f + (ratio >= 0.0f ? 0.5f : -0.5f));
    fr.srcZp = src->params.zero_point;
    fr.dstZp = dst->params.zero_point;
    return fr;
}

static inline void RequantizeCopyFixed(TfLiteTensor* src, TfLiteTensor* dst, const FixedRequant& fr)
{
    int n = (int)src->bytes;
    const int8_t* s = src->data.int8;
    int8_t* d = dst->data.int8;
    for (int i = 0; i < n; i++)
    {
        int32_t x = (int32_t)s[i] - fr.srcZp;
        int32_t q = (int32_t)(((int64_t)x * (int64_t)fr.multiplier) >> 16) + fr.dstZp;
        if (q < -128) q = -128;
        if (q > 127) q = 127;
        d[i] = (int8_t)q;
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
    ok = SEGC1_Init() && ok;
    ok = SEGC2_Init() && ok;
    if (!ok)
    {
        PRINTF("Model init failed\r\n");
        for (;;) {}
    }

    FillInputFromPattern(MONO_Input());
    FillInputFromPattern(SEGAB_Input());
    FillInputFromPattern(SEGA_Input());

    /* Precompute fixed-point multipliers once (mirrors real deployment: quant
     * params are static for the model chain's lifetime, not recomputed per inference). */
    FixedRequant frBtoC_2seg = MakeFixedRequant(SEGAB_Output(), SEGC_Input());
    FixedRequant frAtoB = MakeFixedRequant(SEGA_Output(), SEGB_Input());
    FixedRequant frBtoC_3seg = MakeFixedRequant(SEGB_Output(), SEGC_Input());
    FixedRequant frBtoC1_4seg = MakeFixedRequant(SEGB_Output(), SEGC1_Input());
    FixedRequant frC1toC2 = MakeFixedRequant(SEGC1_Output(), SEGC2_Input());

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

    for (int i = 0; i < NUM_ITER; i++)
    {
        auto t0 = TIMER_GetTimeInUS();
        SEGA_Invoke();
        RequantizeCopy(SEGA_Output(), SEGB_Input());
        SEGB_Invoke();
        RequantizeCopy(SEGB_Output(), SEGC1_Input());
        SEGC1_Invoke();
        RequantizeCopy(SEGC1_Output(), SEGC2_Input());
        SEGC2_Invoke();
        auto t1 = TIMER_GetTimeInUS();
        PRINTF("seg4,%d,%d\r\n", i, (int)(t1 - t0));
    }

    /* --- Fixed-point-copy variants (same NPU graphs/boundaries, optimized copy) --- */

    for (int i = 0; i < NUM_ITER; i++)
    {
        auto t0 = TIMER_GetTimeInUS();
        SEGAB_Invoke();
        RequantizeCopyFixed(SEGAB_Output(), SEGC_Input(), frBtoC_2seg);
        SEGC_Invoke();
        auto t1 = TIMER_GetTimeInUS();
        PRINTF("seg2f,%d,%d\r\n", i, (int)(t1 - t0));
    }

    for (int i = 0; i < NUM_ITER; i++)
    {
        auto t0 = TIMER_GetTimeInUS();
        SEGA_Invoke();
        RequantizeCopyFixed(SEGA_Output(), SEGB_Input(), frAtoB);
        SEGB_Invoke();
        RequantizeCopyFixed(SEGB_Output(), SEGC_Input(), frBtoC_3seg);
        SEGC_Invoke();
        auto t1 = TIMER_GetTimeInUS();
        PRINTF("seg3f,%d,%d\r\n", i, (int)(t1 - t0));
    }

    for (int i = 0; i < NUM_ITER; i++)
    {
        auto t0 = TIMER_GetTimeInUS();
        SEGA_Invoke();
        RequantizeCopyFixed(SEGA_Output(), SEGB_Input(), frAtoB);
        SEGB_Invoke();
        RequantizeCopyFixed(SEGB_Output(), SEGC1_Input(), frBtoC1_4seg);
        SEGC1_Invoke();
        RequantizeCopyFixed(SEGC1_Output(), SEGC2_Input(), frC1toC2);
        SEGC2_Invoke();
        auto t1 = TIMER_GetTimeInUS();
        PRINTF("seg4f,%d,%d\r\n", i, (int)(t1 - t0));
    }

    PRINTF("done\r\n");
    for (;;) {}
}
