/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * GTSRB multi-exit classifier firmware: chains three NPU segments (segA ->
 * segB -> segC), applying CPU-side softmax + confidence thresholding after
 * each of the first two exits (tau_1, tau_2 -- calibrated in Brief 3,
 * alpha=0.05 tier, the primary/first-specified operating point, all three
 * of which passed coverage validation on held-out test data). exit3 is
 * final -- always accepted, no further segment to fall back to.
 *
 * The chain always runs ALL THREE segments every iteration (never actually
 * stops early), timing each stage individually and recording whether each
 * tau WOULD have accepted. This gives one free-running run enough data to
 * derive all three "what if we'd stopped here" latencies
 * (exit1-only = segA time; exit2 = segA+copy+segB; exit3 = full chain)
 * rather than needing three separate captures with different inputs.
 *
 * Between-segment copies (segA->segB, segB->segC): both sides' scale/
 * zero_point are IDENTICAL (0.0235294/-128 for every intermediate feature
 * map -- a consequence of ReLU6's fixed [0,6] output range always
 * quantizing to the same scale regardless of which layer produced it, see
 * results/segments/quant_params.json), so this degenerates to a plain
 * memcpy rather than needing per-element requantization.
 */
#include "board_init.h"
#include "fsl_debug_console.h"
#include "timer.h"
#include "segments.h"
#include "golden_input.h"

#include <string.h>
#include <math.h>

#define NUM_CLASSES 43
#define NUM_ITER 100

/* Brief 3 conformal calibration, alpha=0.05 tier (margin-corrected,
 * validated on held-out test: exit1 achieved_miss=0.0067, exit2=0.0296,
 * both <= 0.05). Device gets only these constants, per the brief. */
#define TAU1 0.957f
#define TAU2 0.926f

/* fsl_debug_console's lightweight PRINTF does not sign-extend "%d" for
 * negative values here -- it prints the raw uint32 two's-complement bit
 * pattern instead (e.g. -24 comes out as 4294967272). Print the sign and
 * magnitude explicitly to sidestep it. */
static void PrintInt8Array(const char* label, const int8_t* data, int count)
{
    PRINTF("GOLDEN %s: [", label);
    for (int i = 0; i < count; i++)
    {
        int v = (int)data[i];
        if (v < 0) { PRINTF("-%d", -v); }
        else { PRINTF("%d", v); }
        if (i < count - 1) { PRINTF(","); }
    }
    PRINTF("]\r\n");
}

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
    BOARD_Init();
    TIMER_Init();

    PRINTF("GTSRB multi-exit firmware\r\n");

    bool ok = true;
    ok = SEGA_Init() && ok;
    ok = SEGB_Init() && ok;
    ok = SEGC_Init() && ok;
    if (!ok)
    {
        PRINTF("Segment init failed\r\n");
        for (;;) {}
    }

    /* Load the fixed golden-check test image (true label %d, see
     * tools/golden/gen_golden.py) into segA's input. */
    memcpy(SEGA_Input()->data.int8, golden_image_int8, sizeof(golden_image_int8));
    PRINTF("golden test image loaded, true_label=%d\r\n", (int)GOLDEN_TRUE_LABEL);

    /* One-shot golden-input dump: PC-computed reference values (see
     * tools/golden/golden_reference.txt) are compared against these by
     * hand/script -- this is not a per-iteration timing run. */
    SEGA_Invoke();
    TfLiteTensor* e1 = SEGA_OutputLogits();
    PrintInt8Array("exit1_logits_int8", e1->data.int8, NUM_CLASSES);
    TfLiteTensor* f1 = SEGA_OutputFeatures();
    PrintInt8Array("block3_features_int8_first10", f1->data.int8, 10);

    memcpy(SEGB_Input()->data.int8, f1->data.int8, f1->bytes);
    SEGB_Invoke();
    TfLiteTensor* e2 = SEGB_OutputLogits();
    PrintInt8Array("exit2_logits_int8", e2->data.int8, NUM_CLASSES);
    TfLiteTensor* f2 = SEGB_OutputFeatures();
    PrintInt8Array("block6_features_int8_first10", f2->data.int8, 10);

    memcpy(SEGC_Input()->data.int8, f2->data.int8, f2->bytes);
    SEGC_Invoke();
    TfLiteTensor* e3 = SEGC_OutputLogits();
    PrintInt8Array("exit3_logits_int8", e3->data.int8, NUM_CLASSES);
    PRINTF("GOLDEN done\r\n");

    /* Free-running timed loop: same fixed input every iteration (matches
     * the measurement rule -- no debugger, reset-button free-running). */
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

    /* On-device conformal coverage validation batch mode: host streams
     * pre-quantized INT8 images one at a time ('I' + exactly
     * sizeof(golden_image_int8) raw bytes), board runs the real chain and
     * replies with a CSV line of per-exit prediction + confidence. This
     * lets the PC-side conformal calibration (tau_k thresholds, computed
     * from a PC TFLite-interpreter simulation of the INT8 model) be
     * re-checked against genuine NPU hardware output, since golden-input
     * check showed the two are not bit-exact (1-4 LSB drift, see
     * tools/golden/DEPLOYMENT_REPORT.md). 'Q' ends the batch. GETCHAR() is
     * non-blocking (polls the debug UART once and returns -1 if nothing is
     * ready), so every byte read is wrapped in a busy-wait. */
    PRINTF("BATCH_READY\r\n");
    for (;;)
    {
        int cmd = -1;
        while (cmd == -1) { cmd = GETCHAR(); }
        if (cmd == 'Q') { PRINTF("BATCH_DONE\r\n"); break; }
        if (cmd != 'I') { continue; }

        uint8_t* dst = (uint8_t*)SEGA_Input()->data.int8;
        for (uint32_t i = 0; i < sizeof(golden_image_int8); i++)
        {
            int b = -1;
            while (b == -1) { b = GETCHAR(); }
            dst[i] = (uint8_t)b;
        }

        SEGA_Invoke();
        int pred1 = Softmax(SEGA_OutputLogits(), probs);
        float conf1 = probs[pred1];

        TfLiteTensor* bf1 = SEGA_OutputFeatures();
        memcpy(SEGB_Input()->data.int8, bf1->data.int8, bf1->bytes);
        SEGB_Invoke();
        int pred2 = Softmax(SEGB_OutputLogits(), probs);
        float conf2 = probs[pred2];

        TfLiteTensor* bf2 = SEGB_OutputFeatures();
        memcpy(SEGC_Input()->data.int8, bf2->data.int8, bf2->bytes);
        SEGC_Invoke();
        int pred3 = Softmax(SEGC_OutputLogits(), probs);
        float conf3 = probs[pred3];

        PRINTF("R,%d,%d,%d,%d,%d,%d\r\n",
               pred1, (int)(conf1 * 1000000.0f), pred2, (int)(conf2 * 1000000.0f),
               pred3, (int)(conf3 * 1000000.0f));
    }

    for (;;) {}
}
