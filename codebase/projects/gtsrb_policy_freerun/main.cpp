/*
 * Copyright 2026 NXP
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * FREE-RUNNING interleaved crypto + certified-anytime perception experiment.
 *
 * This is the measurement build that fixes the protocol violation of the
 * earlier host-driven run: NO host UART involvement during the workload.
 * On reset the board runs the full 1200-frame + 40-handshake workload
 * autonomously, reading the workload blob from the external W25Q64 QSPI
 * flash (burned once beforehand via FREERUN_PROGRAM mode), buffering every
 * per-frame result in RAM, and only emitting the buffered results over UART
 * AFTER the workload completes (serial is reconnected after the PPK2 energy
 * window closes).
 *
 * Workload (frozen definition, see results/interleaved_freerun/):
 *   - 1200 frames: images 0..1199 from QSPI flash, offset i*6912
 *   - crypto: every CRYPTO_STEP_PERIOD=10 frames, one ML-KEM-768 step
 *     (keypair -> encap -> decap, rotating) -> 120 steps = 40 handshakes
 *   - identical across the three policy builds (only the perception-side
 *     exit policy differs)
 *
 * Three policies (compile-time POLICY, one build each):
 *   NAIVE:    always run the full 3-exit chain, ignore confidence.
 *   STATIC:   certified-menu alpha=0.05 tier ONLY. exit1 tau=0.858 (certified),
 *             exit2 tau=0.815 (NOT certified at alpha=0.05: 5.17% > 5.00%,
 *             frozen single touch) -> structurally disabled, never taken;
 *             exit3 always accepted (certified 4.50% <= 5%).
 *   ADAPTIVE: certified menu; alpha=0.05 normally (exit1 tau=0.858, exit3,
 *             exit2 disabled); shifts to the certified alpha=0.10 tier for
 *             the 4 frames around each crypto step (exit1 tau=0.723, exit2
 *             tau=0.402 -- exit2 IS certified at 0.10 (9.85%<=10%), exit3).
 *
 * Certified-menu enforcement is structural, not just a threshold value:
 * exit2's stop decision is additionally gated by whether the ACTIVE tier has
 * it certified (see exit2CertifiedAtTier in ProcessFrame) -- an uncertified
 * exit can never be taken, regardless of confidence.
 */
#include "board_init.h"
#include "board.h"
#include "fsl_debug_console.h"
#include "fsl_gpio.h"
#include "fsl_port.h"
#include "timer.h"
#include "segments.h"
#include "qspi.h"
#include "embedded_images.h"

extern "C" {
#include "api.h"
}

/* Compute-current isolation trigger. Originally P0_29 (Arduino D2), but
 * that pin was confirmed NOT toggling on this specific board even with a
 * slow, unmistakable 1Hz blink test on a scope/LA, while the SAME test
 * driving the on-board LED (GPIO0 pin 10, also PORT-muxed only via reset
 * default, not explicit pin_mux.c config) worked correctly -- ruling out
 * a general GPIO/mux bug and pointing at a P0_29-specific hardware fault
 * on this unit (bad trace/solder, or a package difference), not
 * something fixable in firmware. Switched to P0_31 (Arduino D7, same
 * header J1, per the board's own pinout table) -- verify THIS pin
 * toggles with the same blink test before trusting the gated-energy
 * number. Not reusing the on-board LED itself: its own current draw
 * would contaminate the PPK2 trace during exactly the compute-active
 * periods being isolated. */
#define TRIGGER_GPIO GPIO0
#define TRIGGER_PIN  31U

static void TriggerInit(void)
{
    CLOCK_EnableClock(kCLOCK_Port0);
    const port_pin_config_t muxCfg = {
        .pullSelect = kPORT_PullDisable,
        .pullValueSelect = kPORT_LowPullResistor,
        .slewRate = kPORT_FastSlewRate,
        .passiveFilterEnable = kPORT_PassiveFilterDisable,
        .openDrainEnable = kPORT_OpenDrainDisable,
        .driveStrength = kPORT_LowDriveStrength,
        .mux = kPORT_MuxAsGpio,
        .inputBuffer = kPORT_InputBufferEnable,
        .invertInput = kPORT_InputNormal,
        .lockRegister = kPORT_UnlockRegister};
    PORT_SetPinConfig(PORT0, TRIGGER_PIN, &muxCfg);

    gpio_pin_config_t cfg = {kGPIO_DigitalOutput, 0};
    GPIO_PinInit(TRIGGER_GPIO, TRIGGER_PIN, &cfg);
}
static inline void TriggerHigh(void) { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 1); }
static inline void TriggerLow(void)  { GPIO_PinWrite(TRIGGER_GPIO, TRIGGER_PIN, 0); }

#include <string.h>
#include <math.h>

#define NUM_CLASSES 43
#define IMAGE_BYTES 6912

#define POLICY_NAIVE 0
#define POLICY_STATIC 1
#define POLICY_ADAPTIVE 2
#define POLICY_LEARNED 3

#ifndef POLICY
#define POLICY POLICY_NAIVE
#endif

#ifndef FREERUN_PROGRAM
#define FREERUN_PROGRAM 0
#endif

/* Final certified tau thresholds -- BRIEF3_FINAL_certified_menu.csv, frozen
 * four-way protocol, test.csv touched exactly once. Values match that file
 * exactly (verified by direct diff):
 *   exit1 alpha=0.05: tau=0.858  n=2928  achieved_miss=0.0447  PASS
 *   exit1 alpha=0.10: tau=0.723  n=4303  achieved_miss=0.0904  PASS
 *   exit2 alpha=0.05: tau=0.815  n=7530  achieved_miss=0.0517  FAIL <- not certified, see exit2CertifiedAtTier
 *   exit2 alpha=0.10: tau=0.402  n=8399  achieved_miss=0.0985  PASS
 * exit3 is the final fallback, certified at all alphas in the menu. */
#define TAU1_A05 0.858f
#define TAU2_A05 0.815f /* NOT certified at alpha=0.05 -- never used to accept an exit */
#define TAU1_A10 0.723f
#define TAU2_A10 0.402f

/* Learned exit policy thresholds (LEARNED_POLICY_REPORT.md): per-exit
 * isotonic risk curves trained on calibration + margin_val, choosing the
 * shallowest exit whose learned risk <= 0.05. Both exits certified at
 * alpha=0.05 on accepted SC samples: exit1 3.37% (tau where risk<=0.05:
 * conf1>=0.90), exit2 3.99% (conf2>=0.95). Unlike the hand-tuned menu,
 * exit2 IS a legal stop here (the learned curve discovered it is safe). */
#define TAU1_LEARNED 0.90f
#define TAU2_LEARNED 0.95f

#define CRYPTO_STEP_PERIOD 10
/* External QSPI flash erase is unresolved on this board (immediate,
 * deterministic FLEXSPI_TransferBlocking failure on the very first status
 * read, despite every config parameter matching NXP's own working
 * reference exactly -- see chat history). Falling back to a smaller
 * subset of the natural-frequency-corrected workload embedded directly in
 * on-chip flash (m_flash1, 1MB, previously unused) -- see
 * embedded_images.h and gen_embedded_images.py. This still achieves the
 * actual goal (no host UART during the measurement window) at reduced
 * sample size (140 vs 1200 frames). */
#define N_FRAMES EMBEDDED_N_FRAMES
#define N_CRYPTO_STEPS (N_FRAMES / CRYPTO_STEP_PERIOD)
#define N_HANDSHAKES (N_CRYPTO_STEPS / 3)

/* Results buffer (RAM): one entry per frame. 1200 * 40B = 48KB. */
struct FrameResult
{
    uint32_t cryptoUs;
    uint32_t frameUs;
    uint32_t imgReadUs;
    int exitTaken;
    int tierUsed;
    int pred1, pred2, pred3;
    float conf1, conf2, conf3;
};
static FrameResult s_results[N_FRAMES];

static uint8_t s_pk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t s_sk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t s_ct[PQCLEAN_MLKEM768_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t s_ssEnc[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static uint8_t s_ssDec[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static int s_cryptoStepState = 0; /* 0=keypair, 1=encap, 2=decap */
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
    TriggerHigh();
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
    TriggerLow();
    return t1 - t0;
}

static void ProcessFrame(int frameIdx, bool cryptoImminent, FrameResult* r)
{
    r->pred2 = -1;
    r->pred3 = -1;
    r->conf2 = 0.0f;
    r->conf3 = 0.0f;
    float probs[NUM_CLASSES];

    uint32_t t0 = TIMER_GetTimeInUS();
    memcpy(SEGA_Input()->data.int8, embedded_images[frameIdx], IMAGE_BYTES);
    uint32_t tImg = TIMER_GetTimeInUS();
    r->imgReadUs = tImg - t0;

    /* Gate the trigger around NPU compute only -- QSPI_Read above is timed
     * separately as imgReadUs, so keeping it outside the gate lets the
     * gated integral answer "how much energy did inference actually cost"
     * without conflating it with flash-read time. */
    TriggerHigh();
    SEGA_Invoke();
    r->pred1 = Softmax(SEGA_OutputLogits(), probs);
    r->conf1 = probs[r->pred1];

#if POLICY == POLICY_NAIVE
    r->tierUsed = 0;
    TfLiteTensor* bf1 = SEGA_OutputFeatures();
    memcpy(SEGB_Input()->data.int8, bf1->data.int8, bf1->bytes);
    SEGB_Invoke();
    r->pred2 = Softmax(SEGB_OutputLogits(), probs);
    r->conf2 = probs[r->pred2];

    TfLiteTensor* bf2 = SEGB_OutputFeatures();
    memcpy(SEGC_Input()->data.int8, bf2->data.int8, bf2->bytes);
    SEGC_Invoke();
    r->pred3 = Softmax(SEGC_OutputLogits(), probs);
    r->conf3 = probs[r->pred3];
    r->exitTaken = 3;
#else
    float tau1 = TAU1_A05;
    float tau2 = TAU2_A05;
    /* Structural certified-menu gate: exit2 is only a legal stop point
     * when the ACTIVE tier has it certified. At alpha=0.05 it is FAIL
     * (frozen single touch: 5.17% > 5.00%), so it is disabled here
     * regardless of confidence -- not a threshold tweak, "this exit cannot
     * be taken at this tier, full stop." */
    bool exit2CertifiedAtTier = false;
    r->tierUsed = 5;
#if POLICY == POLICY_ADAPTIVE
    if (cryptoImminent)
    {
        tau1 = TAU1_A10;
        tau2 = TAU2_A10;
        exit2CertifiedAtTier = true; /* exit2 alpha=0.10: PASS (9.85%<=10%) */
        r->tierUsed = 10;
    }
#elif POLICY == POLICY_LEARNED
    /* Learned policy: per-exit isotonic risk curves trained on calibration
     * + margin_val. exit2 is a LEGAL stop (learned curve certifies it at
     * alpha=0.05: 3.99% miss on accepted SC), and the thresholds are the
     * learned tau values, not the hand-tuned menu's. */
    tau1 = TAU1_LEARNED;
    tau2 = TAU2_LEARNED;
    exit2CertifiedAtTier = true;
    r->tierUsed = 5; /* learned tier: alpha=0.05 on both exits */
#else
    (void)cryptoImminent;
#endif

    if (r->conf1 >= tau1)
    {
        r->exitTaken = 1;
    }
    else
    {
        /* SEGB must run regardless of whether exit2 is a legal stop this
         * tier -- SEGC's input is SEGB's output features, so the backbone
         * cascade cannot be skipped, only the exit-2 STOP decision can. */
        TfLiteTensor* bf1 = SEGA_OutputFeatures();
        memcpy(SEGB_Input()->data.int8, bf1->data.int8, bf1->bytes);
        SEGB_Invoke();
        r->pred2 = Softmax(SEGB_OutputLogits(), probs);
        r->conf2 = probs[r->pred2];

        if (exit2CertifiedAtTier && r->conf2 >= tau2)
        {
            r->exitTaken = 2;
        }
        else
        {
            TfLiteTensor* bf2 = SEGB_OutputFeatures();
            memcpy(SEGC_Input()->data.int8, bf2->data.int8, bf2->bytes);
            SEGC_Invoke();
            r->pred3 = Softmax(SEGC_OutputLogits(), probs);
            r->conf3 = probs[r->pred3];
            r->exitTaken = 3;
        }
    }
#endif

    TriggerLow();
    uint32_t t1 = TIMER_GetTimeInUS();
    r->frameUs = t1 - tImg;
}

#if FREERUN_PROGRAM
/* ------------------------------------------------------------------ */
/* One-time burn mode: receive the 1200-image blob over UART, erase+program
 * each 4096-byte sector of the W25Q64, verify, ACK per sector.
 * Protocol (host side: tools/burn_freerun_workload.py):
 *   host -> 'B' start; board -> 'R' ready
 *   loop sectors 0..2024:
 *     host -> 4-byte LE sector idx + 4096 bytes
 *     board erases, programs 16 pages of 256B, verifies
 *     board -> 'K' ok / 'N' fail (host retries up to 3)
 *   host -> 'E'; board -> 'D' + 4-byte LE total + BURN_DONE
 */
static void BurnWorkload(void)
{
    const uint32_t nSectors = (uint32_t)(N_FRAMES * IMAGE_BYTES) / 4096u; /* 2025 */
    PRINTF("BURN_READY\r\n");
    while (GETCHAR() != 'B') {}
    PRINTF("R\r\n");
    for (uint32_t s = 0; s < nSectors; s++)
    {
        uint32_t idx = 0;
        for (int b = 0; b < 4; b++)
        {
            int c = GETCHAR();
            while (c == -1) { c = GETCHAR(); }
            idx |= ((uint32_t)c) << (8 * b);
        }
        /* 4-byte aligned: FlexSPI AHB write to an unaligned buffer in device
         * memory region triggers a bus fault (see SDK flexspi_nor example). */
        SDK_ALIGN(static uint8_t buf[4096], 4);
        for (uint32_t i = 0; i < 4096; i++)
        {
            int c = GETCHAR();
            while (c == -1) { c = GETCHAR(); }
            buf[i] = (uint8_t)c;
        }
        bool ok = false;
        uint8_t failStage = 0; /* 0=erase 1=program 2=verify -- last stage attempted */
        for (int attempt = 0; attempt < 3 && !ok; attempt++)
        {
            ok = QSPI_EraseSector(idx * 4096);
            if (!ok) { failStage = 0; }
            for (uint32_t p = 0; ok && p < 4096; p += 256)
            {
                ok = QSPI_PageProgram(idx * 4096 + p, buf + p, 256);
                if (!ok) { failStage = 1; }
            }
            if (ok)
            {
                ok = QSPI_Verify(idx * 4096, buf, 4096);
                if (!ok) { failStage = 2; }
            }
        }
        if (ok)
        {
            PRINTF("%c", 'K');
        }
        else
        {
            PRINTF("%c%c", 'N', (char)failStage);
        }
    }
    while (GETCHAR() != 'E') {}
    PRINTF("D%c%c%c%c", (char)(N_FRAMES * IMAGE_BYTES & 0xFF),
           (char)((N_FRAMES * IMAGE_BYTES >> 8) & 0xFF),
           (char)((N_FRAMES * IMAGE_BYTES >> 16) & 0xFF),
           (char)((N_FRAMES * IMAGE_BYTES >> 24) & 0xFF));
    PRINTF("\r\nBURN_DONE\r\n");
}
#endif

int main(void)
{
    BOARD_Init();
    TIMER_Init();
#if FREERUN_PROGRAM
    if (!QSPI_Init())
    {
        PRINTF("QSPI init failed\r\n");
        for (;;) {}
    }
    BurnWorkload();
    for (;;) {}
#endif
    TriggerInit();
    TriggerLow();

    bool ok = true;
    ok = SEGA_Init() && ok;
    ok = SEGB_Init() && ok;
    ok = SEGC_Init() && ok;
    if (!ok)
    {
        PRINTF("Segment init failed\r\n");
        for (;;) {}
    }

#if POLICY == POLICY_NAIVE
    PRINTF("FREERUN: NAIVE\r\n");
    PRINTF("Allowed stops: exit1=NO exit2=NO exit3=ALWAYS (full chain, confidence ignored)\r\n");
#elif POLICY == POLICY_STATIC
    PRINTF("FREERUN: STATIC (certified menu alpha=0.05 fixed tier)\r\n");
    PRINTF("  exit1: tau=%d/1000  CERTIFIED (0.0447<=0.05) YES\r\n", (int)(TAU1_A05 * 1000));
    PRINTF("  exit2: tau=%d/1000  NOT CERTIFIED at 0.05 (0.0517>0.05) -- disabled, never taken\r\n", (int)(TAU2_A05 * 1000));
    PRINTF("  exit3: always accepted, CERTIFIED at alpha=0.05 (0.0450<=0.05) YES\r\n");
    PRINTF("Allowed stops: exit1=YES exit2=NO exit3=YES\r\n");
#elif POLICY == POLICY_ADAPTIVE
    PRINTF("FREERUN: ADAPTIVE (certified menu 0.05 normal / 0.10 near crypto)\r\n");
    PRINTF("  tier 0.05: exit1 tau=%d/1000 YES | exit2 NO (uncertified) | exit3 YES\r\n", (int)(TAU1_A05 * 1000));
    PRINTF("  tier 0.10: exit1 tau=%d/1000 YES | exit2 tau=%d/1000 YES (0.0985<=0.10) | exit3 YES\r\n",
           (int)(TAU1_A10 * 1000), (int)(TAU2_A10 * 1000));
    PRINTF("Allowed stops (normal): exit1=YES exit2=NO exit3=YES\r\n");
    PRINTF("Allowed stops (crypto-imminent): exit1=YES exit2=YES exit3=YES\r\n");
#elif POLICY == POLICY_LEARNED
    PRINTF("FREERUN: LEARNED (isotonic risk curves, calibration+margin_val)\r\n");
    PRINTF("  exit1: tau=%d/1000  LEARNED CERTIFIED at 0.05 (3.37%%<=5%%) YES\r\n", (int)(TAU1_LEARNED * 1000));
    PRINTF("  exit2: tau=%d/1000  LEARNED CERTIFIED at 0.05 (3.99%%<=5%%) YES\r\n", (int)(TAU2_LEARNED * 1000));
    PRINTF("  exit3: always accepted (final fallback)\r\n");
    PRINTF("Allowed stops: exit1=YES exit2=YES exit3=YES (all learned-certified at alpha=0.05)\r\n");
#endif
    PRINTF("WORKLOAD_START\r\n");

    for (int i = 0; i < N_FRAMES; i++)
    {
        int posInCycle = i % CRYPTO_STEP_PERIOD;
        uint32_t cryptoUs = 0;
        if (posInCycle == 0)
        {
            cryptoUs = RunCryptoStep();
        }
        bool cryptoImminent = (posInCycle <= 1) || (posInCycle >= CRYPTO_STEP_PERIOD - 2);

        FrameResult* r = &s_results[i];
        r->cryptoUs = cryptoUs;
        ProcessFrame(i, cryptoImminent, r);
    }

    PRINTF("WORKLOAD_DONE handshakes=%d\r\n", s_handshakesCompleted);

    /* Dump buffered results (serial reconnected after the PPK2 window). */
    PRINTF("RESULTS_BEGIN\r\n");
    for (int i = 0; i < N_FRAMES; i++)
    {
        const FrameResult* r = &s_results[i];
        /* idx,crypto_us,frame_us,img_read_us,exit,tier,pred1,conf1,pred2,conf2,pred3,conf3 */
        PRINTF("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\r\n",
               i, (int)r->cryptoUs, (int)r->frameUs, (int)r->imgReadUs,
               r->exitTaken, r->tierUsed,
               r->pred1, (int)(r->conf1 * 1000000.0f),
               r->pred2, (int)(r->conf2 * 1000000.0f),
               r->pred3, (int)(r->conf3 * 1000000.0f));
    }
    PRINTF("RESULTS_END\r\n");
    for (;;) {}
}
