/*
 * seg_timing.cpp - per-exit on-device perception cost, ESP32-S3.
 *
 * The host-driven policy capture cannot give this number: its frame_us is
 * dominated by the 6912-byte UART transfer, not by inference. This mode runs
 * the same three INT8 segments from on-chip memory and times each exit
 * boundary with esp_timer.
 *
 *   exit1 = segA
 *   exit2 = segA + handoff + segB
 *   exit3 = segA + handoff + segB + handoff + segC
 *
 * Prints progress every iteration so a capture attaching at any point still
 * sees numbers.
 */
#include <cmath>
#include <cstdint>
#include <cstdio>

#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "segments.h"

#define N_ITER 30

static void HandoffFeatures(const TfLiteTensor* src, TfLiteTensor* dst)
{
    const float sScale = src->params.scale;
    const int32_t sZp = src->params.zero_point;
    const float dScale = dst->params.scale;
    const int32_t dZp = dst->params.zero_point;
    const int n = src->bytes;
    for (int i = 0; i < n; i++) {
        float real = ((float)src->data.int8[i] - (float)sZp) * sScale;
        float q = real / dScale + (float)dZp;
        int v = (int)lrintf(q);
        if (v < -128) v = -128;
        if (v > 127) v = 127;
        dst->data.int8[i] = (int8_t)v;
    }
}

extern "C" void app_main(void)
{
    printf("\n### BOOT seg_timing ###\n");
    fflush(stdout);

    vTaskDelay(pdMS_TO_TICKS(1500));

    printf("plat,esp32s3,n_iter=%d\n", N_ITER);
    fflush(stdout);

    bool ok = SEGA_Init() && SEGB_Init() && SEGC_Init();
    printf("init_ok=%d\n", ok ? 1 : 0);
    fflush(stdout);

    {
        TfLiteTensor* in = SEGA_Input();
        if (in && in->data.int8) {
            for (int i = 0; i < (int)in->bytes; i++)
                in->data.int8[i] = (int8_t)((i * 37 + 11) & 0xFF);
        }
    }

    uint64_t s1 = 0, s2 = 0, s3 = 0;

    for (int i = 0; i < N_ITER; i++) {
        int64_t t0 = esp_timer_get_time();
        SEGA_Invoke();
        int64_t t1 = esp_timer_get_time();
        HandoffFeatures(SEGA_OutputFeatures(), SEGB_Input());
        SEGB_Invoke();
        int64_t t2 = esp_timer_get_time();
        HandoffFeatures(SEGB_OutputFeatures(), SEGC_Input());
        SEGC_Invoke();
        int64_t t3 = esp_timer_get_time();

        uint32_t e1 = (uint32_t)(t1 - t0);
        uint32_t e2 = (uint32_t)(t2 - t0);
        uint32_t e3 = (uint32_t)(t3 - t0);
        s1 += e1; s2 += e2; s3 += e3;

        printf("ITER %d exit1=%u exit2=%u exit3=%u\n",
               i, (unsigned)e1, (unsigned)e2, (unsigned)e3);
        fflush(stdout);
    }

    printf("RESULT exit1_us=%u exit2_us=%u exit3_us=%u\n",
           (unsigned)(s1 / N_ITER), (unsigned)(s2 / N_ITER), (unsigned)(s3 / N_ITER));
    printf("RESULT exit1_ms=%.3f exit2_ms=%.3f exit3_ms=%.3f\n",
           (float)(s1 / N_ITER) / 1000.0f,
           (float)(s2 / N_ITER) / 1000.0f,
           (float)(s3 / N_ITER) / 1000.0f);
    printf("RESULT exit3_minus_exit1_ms=%.3f\n",
           ((float)(s3 / N_ITER) - (float)(s1 / N_ITER)) / 1000.0f);
    printf("BENCH_COMPLETE\n");
    fflush(stdout);

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(2000));
        printf("REPEAT exit1_us=%u exit2_us=%u exit3_us=%u\n",
               (unsigned)(s1 / N_ITER), (unsigned)(s2 / N_ITER), (unsigned)(s3 / N_ITER));
        fflush(stdout);
    }
}
