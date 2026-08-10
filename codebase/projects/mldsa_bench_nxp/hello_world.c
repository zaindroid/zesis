/*
 * ML-DSA (Dilithium, FIPS 204) non-deterministic signing latency benchmark
 * on NXP FRDM-MCXN947 (dual Cortex-M33 @ 150 MHz, single core). Cross-platform
 * counterpart to the ESP32-S3 ML-DSA measurement; methodology kept identical
 * so the two are directly comparable (see MLDSA_SIGNING_LATENCY_REPORT.md in
 * the ESP32 project and BENCHMARK_METHODOLOGY.md here).
 *
 * Design (per the brief):
 *  - Timing: DWT->CYCCNT (cycle-accurate hardware counter), converted to us at
 *    the recorded 150 MHz core clock.
 *  - keypair / verify: near-deterministic -> 100 reps, mean + spread.
 *  - SIGN (the fat-tailed op): >= 2000 reps per level, DIFFERENT message every
 *    iteration (counter incremented into the message buffer) AND fresh
 *    randomness each call (the randombytes stub advances its PRNG state per
 *    call). Every sign is immediately verified; failures are counted.
 *  - Per-call rejection-retry count from the instrumented sign.c.
 *  - Free-running rule: flash -> reset -> let it run undebugged -> capture
 *    serial. Results buffered in RAM and dumped only AFTER the timed loop.
 *  - Peak stack per op via the stack-painting high-water-mark technique
 *    (same as the ML-KEM bench here).
 *
 * The security level (44/65/87) is selected by -DMLDSA_LEVEL=<n> at build time
 * (one build per level, like the ML-KEM variant swap).
 */
#include "board.h"
#include "app.h"
#include "fsl_debug_console.h"
#include "dwt.h"

#if MLDSA_LEVEL == 44
#include "ml-dsa-44/api.h"
#elif MLDSA_LEVEL == 65
#include "ml-dsa-65/api.h"
#elif MLDSA_LEVEL == 87
#include "ml-dsa-87/api.h"
#endif
#include "mldsa_bench.h"

#if MLDSA_LEVEL == 44
#define SKBYTES PQCLEAN_MLDSA44_CLEAN_CRYPTO_SECRETKEYBYTES
#define PKBYTES PQCLEAN_MLDSA44_CLEAN_CRYPTO_PUBLICKEYBYTES
#define SGBYTES PQCLEAN_MLDSA44_CLEAN_CRYPTO_BYTES
#define ALGNAME PQCLEAN_MLDSA44_CLEAN_CRYPTO_ALGNAME
#define KEYGEN PQCLEAN_MLDSA44_CLEAN_crypto_sign_keypair
#define SIGN PQCLEAN_MLDSA44_CLEAN_crypto_sign_signature
#define VERIFY PQCLEAN_MLDSA44_CLEAN_crypto_sign_verify_ctx
#define BENCH_RESET PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections
#define BENCH_GET PQCLEAN_MLDSA44_CLEAN_bench_get_rejections
#elif MLDSA_LEVEL == 65
#define SKBYTES PQCLEAN_MLDSA65_CLEAN_CRYPTO_SECRETKEYBYTES
#define PKBYTES PQCLEAN_MLDSA65_CLEAN_CRYPTO_PUBLICKEYBYTES
#define SGBYTES PQCLEAN_MLDSA65_CLEAN_CRYPTO_BYTES
#define ALGNAME PQCLEAN_MLDSA65_CLEAN_CRYPTO_ALGNAME
#define KEYGEN PQCLEAN_MLDSA65_CLEAN_crypto_sign_keypair
#define SIGN PQCLEAN_MLDSA65_CLEAN_crypto_sign_signature
#define VERIFY PQCLEAN_MLDSA65_CLEAN_crypto_sign_verify_ctx
#define BENCH_RESET PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections
#define BENCH_GET PQCLEAN_MLDSA65_CLEAN_bench_get_rejections
#elif MLDSA_LEVEL == 87
#define SKBYTES PQCLEAN_MLDSA87_CLEAN_CRYPTO_SECRETKEYBYTES
#define PKBYTES PQCLEAN_MLDSA87_CLEAN_CRYPTO_PUBLICKEYBYTES
#define SGBYTES PQCLEAN_MLDSA87_CLEAN_CRYPTO_BYTES
#define ALGNAME PQCLEAN_MLDSA87_CLEAN_CRYPTO_ALGNAME
#define KEYGEN PQCLEAN_MLDSA87_CLEAN_crypto_sign_keypair
#define SIGN PQCLEAN_MLDSA87_CLEAN_crypto_sign_signature
#define VERIFY PQCLEAN_MLDSA87_CLEAN_crypto_sign_verify_ctx
#define BENCH_RESET PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections
#define BENCH_GET PQCLEAN_MLDSA87_CLEAN_bench_get_rejections
#else
#error "MLDSA_LEVEL must be 44, 65, or 87"
#endif

#define N_SIGN 2000
#define N_DET 100
#define MSG_LEN 32

/* Result buffers in RAM (dumped only after the timed loop). */
static uint32_t s_sign_cycles[N_SIGN];
static uint32_t s_sign_retries[N_SIGN];
static uint8_t s_sign_fail[N_SIGN];
static uint32_t s_kp_cycles[N_DET];
static uint32_t s_vf_cycles[N_DET];
static uint32_t s_kp_stack[N_DET];
static uint32_t s_vf_stack[N_DET];

static uint8_t s_pk[PKBYTES];
static uint8_t s_sk[SKBYTES];
static uint8_t s_sig[SGBYTES];
static uint8_t s_msg[MSG_LEN];

/* Linker-provided stack bounds for stack painting. */
extern uint32_t __StackLimit[];
extern uint32_t __StackTop[];

#define STACK_PATTERN 0xAAAAAAAAu
#define STACK_PAINT_MARGIN_BYTES 128

static void StackPaint(void)
{
    uint32_t currentSp;
    __asm volatile ("mov %0, sp" : "=r" (currentSp));
    uint32_t *end = (uint32_t *)(currentSp - STACK_PAINT_MARGIN_BYTES);
    uint32_t *p = __StackLimit;
    while (p < end)
    {
        *p++ = STACK_PATTERN;
    }
}

static uint32_t StackHighWaterMarkBytes(void)
{
    uint32_t *p = __StackLimit;
    while (p < __StackTop && *p == STACK_PATTERN)
    {
        p++;
    }
    return (uint32_t)((uint8_t *)__StackTop - (uint8_t *)p);
}

int main(void)
{
    uint32_t c;

    BOARD_InitHardware();
    dwt_init();

    dwt_reset();
    for (volatile int i = 0; i < 1000; i++) { }
    PRINTF("dwt_sanity,%d\r\n", (int)dwt_get());

    PRINTF("MLDSA_LEVEL=%d alg=%s\r\n", MLDSA_LEVEL, ALGNAME);
    PRINTF("cpu_freq_hz=%d\r\n", (int)150000000u);
    PRINTF("sig=%d pk=%d sk=%d\r\n", (int)SGBYTES, (int)PKBYTES, (int)SKBYTES);
    PRINTF("stack_region_bytes,%d\r\n",
           (int)((uint8_t *)__StackTop - (uint8_t *)__StackLimit));

    /* --- keypair: 100 reps (near-deterministic) --- */
    for (int i = 0; i < N_DET; i++)
    {
        StackPaint();
        dwt_reset();
        KEYGEN(s_pk, s_sk);
        c = dwt_get();
        s_kp_cycles[i] = c;
        s_kp_stack[i] = StackHighWaterMarkBytes();
    }

    /* --- sign + verify: N_SIGN reps, fresh msg+randomness each --- */
    uint32_t fail = 0;
    uint32_t retry_max = 0;
    for (int i = 0; i < N_SIGN; i++)
    {
        /* Different message every iteration. */
        for (int j = 0; j < MSG_LEN; j++) { s_msg[j] = (uint8_t)(i + j * 7 + 1); }
        size_t siglen = SGBYTES;
        BENCH_RESET();
        dwt_reset();
        int r = SIGN(s_sig, &siglen, s_msg, MSG_LEN, s_sk);
        c = dwt_get();
        s_sign_cycles[i] = c;
        s_sign_retries[i] = BENCH_GET();
        if (s_sign_retries[i] > retry_max) { retry_max = s_sign_retries[i]; }
        if (r != 0)
        {
            s_sign_fail[i] = 1;
            fail++;
            continue;
        }
        int vr = VERIFY(s_sig, siglen, s_msg, MSG_LEN, NULL, 0, s_pk);
        s_sign_fail[i] = (vr != 0) ? 2 : 0;
        if (vr != 0) { fail++; }
    }

    /* --- verify: 100 reps (uses last signature) --- */
    for (int i = 0; i < N_DET; i++)
    {
        StackPaint();
        dwt_reset();
        VERIFY(s_sig, SGBYTES, s_msg, MSG_LEN, NULL, 0, s_pk);
        c = dwt_get();
        s_vf_cycles[i] = c;
        s_vf_stack[i] = StackHighWaterMarkBytes();
    }

    PRINTF("BENCH_DONE fails=%d retry_max=%d\r\n", (int)fail, (int)retry_max);

    /* Dump raw per-call data AFTER the timed loop. */
    PRINTF("KP_BEGIN\r\n");
    for (int i = 0; i < N_DET; i++) { PRINTF("%u,%u\r\n", (unsigned)s_kp_cycles[i], (unsigned)s_kp_stack[i]); }
    PRINTF("KP_END\r\n");
    PRINTF("SIGN_BEGIN\r\n");
    for (int i = 0; i < N_SIGN; i++)
    {
        PRINTF("%u,%u,%u\r\n", (unsigned)s_sign_cycles[i], (unsigned)s_sign_retries[i], (unsigned)s_sign_fail[i]);
    }
    PRINTF("SIGN_END\r\n");
    PRINTF("VF_BEGIN\r\n");
    for (int i = 0; i < N_DET; i++) { PRINTF("%u,%u\r\n", (unsigned)s_vf_cycles[i], (unsigned)s_vf_stack[i]); }
    PRINTF("VF_END\r\n");
    PRINTF("BENCH_COMPLETE\r\n");

    while (1) { }
}
