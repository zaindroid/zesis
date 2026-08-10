/*
 * ESP32-S3 port of the certified-anytime multi-exit benchmark.
 *
 * Runs the SAME INT8 TFLite segment models and certified-menu policy logic as
 * the NXP FRDM-MCXN947 port, but on the ESP32-S3 CPU via TFLite Micro (no
 * NPU). Because TFLite Micro preserves the INT8 arithmetic, the certified
 * tau thresholds from the frozen four-way protocol transfer: the per-exit
 * conformal risk bounds hold on this platform as well, which is the
 * cross-platform claim this port exists to test.
 *
 * Protocol (host-driven, same framing as gtsrb_multiexit):
 *   host -> 'I' + 6912 raw INT8 bytes (48x48x3)
 *   board -> "R,crypto_us,frame_us,exit_taken,tier_used,pred1,conf1,"
 *            "pred2,conf2,pred3,conf3\r\n"
 *   host -> 'Q' ends the batch.
 *
 * Policies (compile-time POLICY, one build each):
 *   NAIVE:    full 3-exit chain, confidence ignored.
 *   STATIC:   certified menu alpha=0.05 only. exit1 tau=0.858 (certified);
 *             exit2 tau=0.815 NOT certified at 0.05 (5.17%>5%) -> disabled;
 *             exit3 always (certified 4.50%<=5%).
 *   ADAPTIVE: alpha=0.05 normal (exit1 0.858 / exit3 / exit2 disabled);
 *             shifts to certified alpha=0.10 tier for the 4 frames around
 *             each crypto step (exit1 0.723 / exit2 0.402 certified / exit3).
 */
#include <cstdio>
#include <cstring>
#include <cmath>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_log.h"

#include "segments.h"

extern "C" {
#include "api.h"
}

#define NUM_CLASSES 43
#define IMAGE_BYTES 6912

#define POLICY_NAIVE 0
#define POLICY_STATIC 1
#define POLICY_ADAPTIVE 2

#ifndef POLICY
#define POLICY POLICY_NAIVE
#endif

/* Frozen certified tau thresholds (BRIEF3_FINAL_certified_menu.csv). */
#define TAU1_A05 0.858f
#define TAU2_A05 0.815f /* NOT certified at alpha=0.05 -- never used to accept an exit */
#define TAU1_A10 0.723f
#define TAU2_A10 0.402f

#define CRYPTO_STEP_PERIOD 10

static const char* TAG = "gtsrb";

static uint8_t s_pk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t s_sk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t s_ct[PQCLEAN_MLKEM768_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t s_ssEnc[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static uint8_t s_ssDec[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static int s_cryptoStepState = 0;
static int s_handshakesCompleted = 0;

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

static uint32_t RunCryptoStep(void)
{
    uint32_t t0 = (uint32_t)esp_timer_get_time(); /* us */
    if (s_cryptoStepState == 0)
    {
        (void)PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(s_pk, s_sk);
    }
    else if (s_cryptoStepState == 1)
    {
        (void)PQCLEAN_MLKEM768_CLEAN_crypto_kem_enc(s_ct, s_ssEnc, s_pk);
    }
    else
    {
        (void)PQCLEAN_MLKEM768_CLEAN_crypto_kem_dec(s_ssDec, s_ct, s_sk);
        s_handshakesCompleted++;
    }
    s_cryptoStepState = (s_cryptoStepState + 1) % 3;
    uint32_t t1 = (uint32_t)esp_timer_get_time();
    return t1 - t0;
}

/* Hand off feature maps between standalone segments. Each segment is a
 * separately-quantized TFLite model, so the int8 bytes cannot be copied
 * verbatim: dequantize the source and requantize into the target's
 * scale/zero_point. (On the NXP port this re-quantization was fused inside
 * the NPU graph; on ESP32 TFLite Micro the segments are independent.) */
static void HandoffFeatures(const TfLiteTensor* src, TfLiteTensor* dst)
{
    const float sScale = src->params.scale;
    const int32_t sZp = src->params.zero_point;
    const float dScale = dst->params.scale;
    const int32_t dZp = dst->params.zero_point;
    const int n = src->bytes;
    for (int i = 0; i < n; i++)
    {
        float real = ((float)src->data.int8[i] - (float)sZp) * sScale;
        float q = real / dScale + (float)dZp;
        int v = (int)lrintf(q);
        if (v < -128) { v = -128; }
        if (v > 127) { v = 127; }
        dst->data.int8[i] = (int8_t)v;
    }
}

struct FrameResult
{
    int pred1, pred2, pred3;
    float conf1, conf2, conf3;
    int exitTaken;
    int tierUsed;
    uint32_t frameUs;
};

static FrameResult ProcessFrame(bool cryptoImminent)
{
    FrameResult r;
    r.pred2 = -1;
    r.pred3 = -1;
    r.conf2 = 0.0f;
    r.conf3 = 0.0f;
    float probs[NUM_CLASSES];

    uint32_t t0 = (uint32_t)esp_timer_get_time();

    SEGA_Invoke();
    r.pred1 = Softmax(SEGA_OutputLogits(), probs);
    r.conf1 = probs[r.pred1];

#if POLICY == POLICY_NAIVE
    r.tierUsed = 0;
    HandoffFeatures(SEGA_OutputFeatures(), SEGB_Input());
    SEGB_Invoke();
    r.pred2 = Softmax(SEGB_OutputLogits(), probs);
    r.conf2 = probs[r.pred2];

    HandoffFeatures(SEGB_OutputFeatures(), SEGC_Input());
    SEGC_Invoke();
    r.pred3 = Softmax(SEGC_OutputLogits(), probs);
    r.conf3 = probs[r.pred3];
    r.exitTaken = 3;
#else
    float tau1 = TAU1_A05;
    float tau2 = TAU2_A05;
    bool exit2CertifiedAtTier = false;
    r.tierUsed = 5;
#if POLICY == POLICY_ADAPTIVE
    if (cryptoImminent)
    {
        tau1 = TAU1_A10;
        tau2 = TAU2_A10;
        exit2CertifiedAtTier = true;
        r.tierUsed = 10;
    }
#else
    (void)cryptoImminent;
#endif

    if (r.conf1 >= tau1)
    {
        r.exitTaken = 1;
    }
    else
    {
        HandoffFeatures(SEGA_OutputFeatures(), SEGB_Input());
        SEGB_Invoke();
        r.pred2 = Softmax(SEGB_OutputLogits(), probs);
        r.conf2 = probs[r.pred2];

        if (exit2CertifiedAtTier && r.conf2 >= tau2)
        {
            r.exitTaken = 2;
        }
        else
        {
            HandoffFeatures(SEGB_OutputFeatures(), SEGC_Input());
            SEGC_Invoke();
            r.pred3 = Softmax(SEGC_OutputLogits(), probs);
            r.conf3 = probs[r.pred3];
            r.exitTaken = 3;
        }
    }
#endif

    uint32_t t1 = (uint32_t)esp_timer_get_time();
    r.frameUs = t1 - t0;
    return r;
}

/* Host-driven batch loop. Reads 'I' + 6912 bytes per frame from stdin
 * (USB serial/JTAG console), runs the policy, prints the result row. */
static void RunBatch(void)
{
    int frameIdx = 0;
    while (true)
    {
        int cmd = getchar();
        while (cmd == -1) { cmd = getchar(); }
        if (cmd == 'Q')
        {
            printf("BATCH_DONE handshakes=%d\r\n", s_handshakesCompleted);
            break;
        }
        if (cmd != 'I') { continue; }

        uint8_t* dst = (uint8_t*)SEGA_Input()->data.int8;
        for (uint32_t i = 0; i < IMAGE_BYTES; i++)
        {
            int b = -1;
            while (b == -1) { b = getchar(); }
            dst[i] = (uint8_t)b;
        }

        int posInCycle = frameIdx % CRYPTO_STEP_PERIOD;
        uint32_t cryptoUs = 0;
        if (posInCycle == 0)
        {
            cryptoUs = RunCryptoStep();
        }
        bool cryptoImminent = (posInCycle <= 1) || (posInCycle >= CRYPTO_STEP_PERIOD - 2);

        FrameResult r = ProcessFrame(cryptoImminent);

        printf("R,%u,%u,%d,%d,%d,%d,%d,%d,%d,%d\r\n",
               (unsigned int)cryptoUs, (unsigned int)r.frameUs, r.exitTaken, r.tierUsed,
               r.pred1, (int)(r.conf1 * 1000000.0f),
               r.pred2, (int)(r.conf2 * 1000000.0f),
               r.pred3, (int)(r.conf3 * 1000000.0f));

        frameIdx++;
    }
}

extern "C" void app_main(void)
{
#ifdef MLDSA_BENCH_MAIN
    extern void mldsa_bench_main(void);
    mldsa_bench_main();
    return;
#endif
    printf("gtsrb_multiexit_esp32s3\r\n");
#if POLICY == POLICY_NAIVE
    printf("POLICY: NAIVE\r\n");
#elif POLICY == POLICY_STATIC
    printf("POLICY: STATIC (alpha=0.05 fixed tier)\r\n");
    printf("  exit1 tau=0.858 CERTIFIED YES | exit2 NOT CERTIFIED at 0.05, disabled | exit3 YES\r\n");
#elif POLICY == POLICY_ADAPTIVE
    printf("POLICY: ADAPTIVE (0.05 normal / 0.10 near crypto)\r\n");
    printf("  tier 0.05: exit1 0.858 YES | exit2 NO | exit3 YES\r\n");
    printf("  tier 0.10: exit1 0.723 YES | exit2 0.402 YES | exit3 YES\r\n");
#endif

    bool ok = true;
    ok = SEGA_Init() && ok;
    ok = SEGB_Init() && ok;
    ok = SEGC_Init() && ok;
    if (!ok)
    {
        printf("SEGMENT INIT FAILED\r\n");
        for (;;) { vTaskDelay(pdMS_TO_TICKS(1000)); }
    }

    printf("BATCH_READY\r\n");
    RunBatch();
    for (;;) { vTaskDelay(pdMS_TO_TICKS(1000)); }
}
