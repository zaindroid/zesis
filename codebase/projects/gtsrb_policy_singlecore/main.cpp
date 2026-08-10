/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Single-core interleaved crypto + certified-anytime perception experiment.
 * Unlike gtsrb_multiexit/npu_dc_gtsrb (crypto and NPU on separate cores,
 * confirmed architecturally isolated -- zero measurable contention), this
 * puts BOTH ML-KEM-768 crypto and the GTSRB multi-exit chain on ONE core,
 * cooperatively interleaved: every CRYPTO_STEP_PERIOD frames, one crypto
 * sub-operation (keypair/encap/decap, rotating) runs before the frame is
 * processed. This creates genuine, unavoidable scheduling contention (the
 * crypto step blocks the core for tens of ms, during which nothing else
 * can run) -- the scenario a "contention-aware" exit policy actually has
 * something to react to.
 *
 * Three policies (compile-time selected via POLICY, one build/flash each):
 *   NAIVE:    always run the full 3-exit chain, ignore confidence entirely.
 *   STATIC:   fixed alpha=0.05 tau thresholds (tau1=0.858), regardless of
 *             crypto load. exit2 is NOT certified at alpha=0.05 (frozen
 *             single-touch coverage validation: 5.17% achieved miss vs a
 *             5.00% target -- FAIL, see training/results/
 *             BRIEF3_FINAL_certified_menu.csv), so STATIC only ever stops
 *             at exit1 or exit3.
 *   ADAPTIVE: alpha=0.05 tau thresholds normally (exit1 or exit3 only,
 *             same restriction as STATIC); shifts to the looser -- but
 *             still conformally certified -- alpha=0.10 tier for the few
 *             frames immediately before/after a crypto step, where exit2
 *             IS certified (tau2=0.402), so ADAPTIVE alone may stop at
 *             exit1, exit2, or exit3 depending on tier.
 *
 * Certified-menu enforcement is structural, not just a threshold value:
 * exit2's stop decision is additionally gated by whether the ACTIVE tier
 * has exit2 certified (see EXIT2_CERTIFIED_AT_TIER in ProcessFrame) --
 * an uncertified exit can never be taken, regardless of confidence.
 *
 * Crypto scheduling (which frames trigger a step) is IDENTICAL across all
 * three policies -- only how perception frames are processed differs --
 * so total handshake throughput is a controlled constant and any
 * difference in total wall-clock time to finish a fixed workload is
 * attributable to the perception-side exit policy alone.
 *
 * UART batch protocol (same framing as gtsrb_multiexit/tools/hw_validate):
 * host sends 'I' + 6912 raw INT8 bytes per frame; board replies
 * "R,crypto_us,frame_us,exit_taken,tier_used,pred1,conf1,pred2,conf2,
 * pred3,conf3" (conf scaled by 1e6; pred2/conf2/pred3/conf3 are -1/0 when
 * that exit wasn't computed). 'Q' ends the batch.
 */
#include "board_init.h"
#include "fsl_debug_console.h"
#include "timer.h"
#include "segments.h"

extern "C" {
#include "api.h"
}

#include <string.h>
#include <math.h>

#define NUM_CLASSES 43
#define IMAGE_BYTES 6912

#define POLICY_NAIVE 0
#define POLICY_STATIC 1
#define POLICY_ADAPTIVE 2

#ifndef POLICY
#define POLICY POLICY_NAIVE
#endif

/* Final certified tau thresholds -- training/results/BRIEF3_FINAL_certified_menu.csv,
 * frozen four-way protocol, test.csv touched exactly once. Values below match
 * that file exactly (verified by direct diff, not retyped from memory):
 *   exit1 alpha=0.05: tau=0.858  n=2928  achieved_miss=0.0447  PASS
 *   exit1 alpha=0.10: tau=0.723  n=4303  achieved_miss=0.0904  PASS
 *   exit2 alpha=0.05: tau=0.815  n=7530  achieved_miss=0.0517  FAIL <- not certified, see EXIT2_CERTIFIED_AT_TIER
 *   exit2 alpha=0.10: tau=0.402  n=8399  achieved_miss=0.0985  PASS
 * exit3 has no tau (always the final fallback) and is certified at all
 * three alphas in the menu, including alpha=0.01 -- not used by this
 * firmware since only the 0.05/0.10 tiers are exercised here. */
#define TAU1_A05 0.858f
#define TAU2_A05 0.815f /* NOT certified at alpha=0.05 -- kept for logging only, never used to accept an exit; see EXIT2_CERTIFIED_AT_TIER */
#define TAU1_A10 0.723f
#define TAU2_A10 0.402f

/* One crypto sub-operation (keypair/encap/decap, rotating) every this many
 * frames -- over the 1230-image sample, gives 123 steps = 41 full
 * handshakes. Identical across all three policies (see file header). */
#define CRYPTO_STEP_PERIOD 10

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

static uint8_t s_pk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t s_sk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t s_ct[PQCLEAN_MLKEM768_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t s_ssEnc[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static uint8_t s_ssDec[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static int s_cryptoStepState = 0; /* 0=keypair, 1=encap, 2=decap */
static int s_handshakesCompleted = 0;

static uint32_t RunCryptoStep(void)
{
    uint32_t t0 = TIMER_GetTimeInUS();
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
    uint32_t t1 = TIMER_GetTimeInUS();
    return t1 - t0;
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

    uint32_t t0 = TIMER_GetTimeInUS();

    SEGA_Invoke();
    r.pred1 = Softmax(SEGA_OutputLogits(), probs);
    r.conf1 = probs[r.pred1];

#if POLICY == POLICY_NAIVE
    r.tierUsed = 0;
    TfLiteTensor* bf1 = SEGA_OutputFeatures();
    memcpy(SEGB_Input()->data.int8, bf1->data.int8, bf1->bytes);
    SEGB_Invoke();
    r.pred2 = Softmax(SEGB_OutputLogits(), probs);
    r.conf2 = probs[r.pred2];

    TfLiteTensor* bf2 = SEGB_OutputFeatures();
    memcpy(SEGC_Input()->data.int8, bf2->data.int8, bf2->bytes);
    SEGC_Invoke();
    r.pred3 = Softmax(SEGC_OutputLogits(), probs);
    r.conf3 = probs[r.pred3];
    r.exitTaken = 3;
#else
    float tau1 = TAU1_A05;
    float tau2 = TAU2_A05;
    /* Structural certified-menu gate: exit2 is only a legal stop point
     * when the ACTIVE tier has it certified. At alpha=0.05 it is FAIL
     * (see BRIEF3_FINAL_certified_menu.csv), so it is disabled here
     * regardless of confidence -- this is not a threshold tweak, it is
     * "this exit cannot be taken at this tier, full stop." */
    bool exit2CertifiedAtTier = false;
    r.tierUsed = 5;
#if POLICY == POLICY_ADAPTIVE
    if (cryptoImminent)
    {
        tau1 = TAU1_A10;
        tau2 = TAU2_A10;
        exit2CertifiedAtTier = true; /* exit2 alpha=0.10: PASS */
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
        /* SEGB must run regardless of whether exit2 is a legal stop this
         * tier -- SEGC's input is SEGB's output features, so the backbone
         * cascade cannot be skipped, only the exit-2 STOP decision can. */
        TfLiteTensor* bf1 = SEGA_OutputFeatures();
        memcpy(SEGB_Input()->data.int8, bf1->data.int8, bf1->bytes);
        SEGB_Invoke();
        r.pred2 = Softmax(SEGB_OutputLogits(), probs);
        r.conf2 = probs[r.pred2];

        if (exit2CertifiedAtTier && r.conf2 >= tau2)
        {
            r.exitTaken = 2;
        }
        else
        {
            TfLiteTensor* bf2 = SEGB_OutputFeatures();
            memcpy(SEGC_Input()->data.int8, bf2->data.int8, bf2->bytes);
            SEGC_Invoke();
            r.pred3 = Softmax(SEGC_OutputLogits(), probs);
            r.conf3 = probs[r.pred3];
            r.exitTaken = 3;
        }
    }
#endif

    uint32_t t1 = TIMER_GetTimeInUS();
    r.frameUs = t1 - t0;
    return r;
}

int main(void)
{
    BOARD_Init();
    TIMER_Init();

#if POLICY == POLICY_NAIVE
    PRINTF("Policy experiment: NAIVE\r\n");
    PRINTF("Allowed stops: exit1=NO exit2=NO exit3=ALWAYS (full chain, confidence ignored)\r\n");
#elif POLICY == POLICY_STATIC
    PRINTF("Policy experiment: STATIC (alpha=0.05 fixed tier)\r\n");
    PRINTF("Certified menu (BRIEF3_FINAL_certified_menu.csv), tier alpha=0.05:\r\n");
    PRINTF("  exit1: tau=%d/1000  CERTIFIED  (achieved_miss=0.0447 <= 0.05)\r\n", (int)(TAU1_A05 * 1000));
    PRINTF("  exit2: tau=%d/1000  NOT CERTIFIED (achieved_miss=0.0517 > 0.05) -- disabled, never taken\r\n", (int)(TAU2_A05 * 1000));
    PRINTF("  exit3: always accepted, CERTIFIED at alpha=0.05 (achieved_miss=0.0450 <= 0.05)\r\n");
    PRINTF("Allowed stops: exit1=YES exit2=NO exit3=YES\r\n");
#elif POLICY == POLICY_ADAPTIVE
    PRINTF("Policy experiment: ADAPTIVE (alpha=0.05 normal / alpha=0.10 near crypto)\r\n");
    PRINTF("Certified menu (BRIEF3_FINAL_certified_menu.csv):\r\n");
    PRINTF("  tier alpha=0.05: exit1 tau=%d/1000 YES | exit2 tau=%d/1000 NO (uncertified) | exit3 YES\r\n",
           (int)(TAU1_A05 * 1000), (int)(TAU2_A05 * 1000));
    PRINTF("  tier alpha=0.10: exit1 tau=%d/1000 YES | exit2 tau=%d/1000 YES (achieved_miss=0.0985<=0.10) | exit3 YES\r\n",
           (int)(TAU1_A10 * 1000), (int)(TAU2_A10 * 1000));
    PRINTF("Allowed stops (normal tier): exit1=YES exit2=NO exit3=YES\r\n");
    PRINTF("Allowed stops (crypto-imminent tier): exit1=YES exit2=YES exit3=YES\r\n");
#endif

    bool ok = true;
    ok = SEGA_Init() && ok;
    ok = SEGB_Init() && ok;
    ok = SEGC_Init() && ok;
    if (!ok)
    {
        PRINTF("Segment init failed\r\n");
        for (;;) {}
    }

    PRINTF("BATCH_READY\r\n");

    int frameIdx = 0;
    for (;;)
    {
        int cmd = -1;
        while (cmd == -1) { cmd = GETCHAR(); }
        if (cmd == 'Q') { PRINTF("BATCH_DONE handshakes=%d\r\n", s_handshakesCompleted); break; }
        if (cmd != 'I') { continue; }

        uint8_t* dst = (uint8_t*)SEGA_Input()->data.int8;
        for (uint32_t i = 0; i < IMAGE_BYTES; i++)
        {
            int b = -1;
            while (b == -1) { b = GETCHAR(); }
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

        PRINTF("R,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\r\n",
               (int)cryptoUs, (int)r.frameUs, r.exitTaken, r.tierUsed,
               r.pred1, (int)(r.conf1 * 1000000.0f),
               r.pred2, (int)(r.conf2 * 1000000.0f),
               r.pred3, (int)(r.conf3 * 1000000.0f));

        frameIdx++;
    }

    for (;;) {}
}
