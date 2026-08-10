/*
 * ML-DSA (Dilithium, FIPS 204) non-deterministic signing latency benchmark
 * on ESP32-S3 (Xtensa LX7, CPU-only). Cross-platform counterpart to the NXP
 * ML-DSA measurement; methodology kept identical so the two are comparable.
 *
 * Design (per the brief):
 *  - Timing: CPU cycle counter (esp_cpu_get_cycle_count = CCOUNT on LX7),
 *    converted to us at the recorded CPU frequency (240 MHz).
 *  - keypair / verify: near-deterministic -> 100 reps, mean + spread.
 *  - SIGN (the fat-tailed op): >= 2000 reps per level, DIFFERENT message every
 *    iteration (counter incremented into the message buffer) AND fresh
 *    randomness each call (the randombytes stub advances its PRNG state per
 *    call). Every sign is immediately verified; failures are counted.
 *  - Per-call rejection-retry count from the instrumented sign.c.
 *  - Task pinned to one core; no other tasks/logging during the timed loop;
 *    results buffered in RAM and dumped only AFTER the timed run.
 *  - Peak stack per op via uxTaskGetStackHighWaterMark.
 *
 * Three security levels (ML-DSA-44/65/87) selected by compile-time
 * MLDSA_LEVEL (44/65/87); one build per level, like the NXP variant swap.
 */
#include <cstdio>
#include <cstring>
#include <cstdint>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_cpu.h"
#include "esp_rom_sys.h"
#include "mldsa_bench.h"

/* Per-level API wiring. */
#if MLDSA_LEVEL == 44
#include "ml-dsa-44/api.h"
#define PREFIX PQCLEAN_MLDSA44_CLEAN
#define BENCH_RESET PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections
#define BENCH_GET PQCLEAN_MLDSA44_CLEAN_bench_get_rejections
#define SKBYTES PQCLEAN_MLDSA44_CLEAN_CRYPTO_SECRETKEYBYTES
#define PKBYTES PQCLEAN_MLDSA44_CLEAN_CRYPTO_PUBLICKEYBYTES
#define SGBYTES PQCLEAN_MLDSA44_CLEAN_CRYPTO_BYTES
#define KEYGEN PQCLEAN_MLDSA44_CLEAN_crypto_sign_keypair
#define SIGN PQCLEAN_MLDSA44_CLEAN_crypto_sign_signature
#define VERIFY PQCLEAN_MLDSA44_CLEAN_crypto_sign_verify_ctx
#elif MLDSA_LEVEL == 65
#include "ml-dsa-65/api.h"
#define PREFIX PQCLEAN_MLDSA65_CLEAN
#define BENCH_RESET PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections
#define BENCH_GET PQCLEAN_MLDSA65_CLEAN_bench_get_rejections
#define SKBYTES PQCLEAN_MLDSA65_CLEAN_CRYPTO_SECRETKEYBYTES
#define PKBYTES PQCLEAN_MLDSA65_CLEAN_CRYPTO_PUBLICKEYBYTES
#define SGBYTES PQCLEAN_MLDSA65_CLEAN_CRYPTO_BYTES
#define KEYGEN PQCLEAN_MLDSA65_CLEAN_crypto_sign_keypair
#define SIGN PQCLEAN_MLDSA65_CLEAN_crypto_sign_signature
#define VERIFY PQCLEAN_MLDSA65_CLEAN_crypto_sign_verify_ctx
#elif MLDSA_LEVEL == 87
#include "ml-dsa-87/api.h"
#define PREFIX PQCLEAN_MLDSA87_CLEAN
#define BENCH_RESET PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections
#define BENCH_GET PQCLEAN_MLDSA87_CLEAN_bench_get_rejections
#define SKBYTES PQCLEAN_MLDSA87_CLEAN_CRYPTO_SECRETKEYBYTES
#define PKBYTES PQCLEAN_MLDSA87_CLEAN_CRYPTO_PUBLICKEYBYTES
#define SGBYTES PQCLEAN_MLDSA87_CLEAN_CRYPTO_BYTES
#define KEYGEN PQCLEAN_MLDSA87_CLEAN_crypto_sign_keypair
#define SIGN PQCLEAN_MLDSA87_CLEAN_crypto_sign_signature
#define VERIFY PQCLEAN_MLDSA87_CLEAN_crypto_sign_verify_ctx
#else
#error "MLDSA_LEVEL must be 44, 65, or 87"
#endif

#define N_SIGN 2000
#define N_DET 100          /* keypair/verify reps */

#define MSG_LEN 32

/* Result buffers in RAM (dumped only after the timed loop). 2000 x (1
 * uint32 cycles + 1 uint32 retries) = 16 KB per buffer. */
static uint32_t s_sign_cycles[N_SIGN];
static uint32_t s_sign_retries[N_SIGN];
static uint8_t s_sign_fail[N_SIGN];
static uint32_t s_kp_cycles[N_DET];
static uint32_t s_vf_cycles[N_DET];

static uint8_t s_pk[PKBYTES];
static uint8_t s_sk[SKBYTES];
static uint8_t s_sig[SGBYTES];
static uint8_t s_msg[MSG_LEN];

static uint32_t s_cpu_freq_hz = 0;

static uint32_t now_cycles(void)
{
    return (uint32_t)esp_cpu_get_cycle_count();
}

/* Stack high-water marks (words remaining). */
static uint32_t s_hwm_keypair, s_hwm_sign, s_hwm_verify;

static void run_bench(void*)
{
    /* Record CPU frequency (the CCOUNT ticks at core clock). */
    s_cpu_freq_hz = CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ * 1000000u;
    printf("MLDSA_LEVEL=%d cpu_freq_hz=%lu\r\n", MLDSA_LEVEL, s_cpu_freq_hz);
    printf("sig=%d pk=%d sk=%d\r\n", SGBYTES, PKBYTES, SKBYTES);

    /* --- keypair: 100 reps --- */
    for (int i = 0; i < N_DET; i++)
    {
        uint32_t t0 = now_cycles();
        KEYGEN(s_pk, s_sk);
        uint32_t t1 = now_cycles();
        s_kp_cycles[i] = t1 - t0;
    }
    s_hwm_keypair = uxTaskGetStackHighWaterMark(nullptr);

    /* --- sign + verify: N_SIGN reps, fresh msg+randomness each --- */
    uint32_t fail = 0;
    uint64_t retry_sum = 0;
    uint32_t retry_max = 0;
    for (int i = 0; i < N_SIGN; i++)
    {
        /* Different message every iteration. */
        for (int j = 0; j < MSG_LEN; j++) { s_msg[j] = (uint8_t)(i + j * 7 + 1); }
        size_t siglen = SGBYTES;
        BENCH_RESET();
        uint32_t t0 = now_cycles();
        int r = SIGN(s_sig, &siglen, s_msg, MSG_LEN, s_sk);
        uint32_t t1 = now_cycles();
        s_sign_cycles[i] = t1 - t0;
        s_sign_retries[i] = BENCH_GET();
        retry_sum += s_sign_retries[i];
        if (s_sign_retries[i] > retry_max) { retry_max = s_sign_retries[i]; }
        if (r != 0)
        {
            s_sign_fail[i] = 1;
            fail++;
            continue;
        }
        /* Verify every signature; count failures. */
        int vr = VERIFY(s_sig, siglen, s_msg, MSG_LEN, nullptr, 0, s_pk);
        s_sign_fail[i] = (vr != 0) ? 2 : 0;
        if (vr != 0) { fail++; }
    }
    s_hwm_sign = uxTaskGetStackHighWaterMark(nullptr);

    /* --- verify: 100 reps (uses last signature) --- */
    for (int i = 0; i < N_DET; i++)
    {
        uint32_t t0 = now_cycles();
        VERIFY(s_sig, SGBYTES, s_msg, MSG_LEN, nullptr, 0, s_pk);
        uint32_t t1 = now_cycles();
        s_vf_cycles[i] = t1 - t0;
    }
    s_hwm_verify = uxTaskGetStackHighWaterMark(nullptr);

    printf("BENCH_DONE fails=%lu retry_max=%lu retry_avg=%lu\r\n",
           fail, retry_max, (uint32_t)(retry_sum / N_SIGN));
    printf("HWM keypair=%lu sign=%lu verify=%lu\r\n",
           s_hwm_keypair, s_hwm_sign, s_hwm_verify);

    /* Dump raw per-call data AFTER the timed loop. */
    printf("KP_BEGIN\r\n");
    for (int i = 0; i < N_DET; i++) { printf("%lu\r\n", s_kp_cycles[i]); }
    printf("KP_END\r\n");
    printf("SIGN_BEGIN\r\n");
    for (int i = 0; i < N_SIGN; i++)
    {
        printf("%lu,%lu,%u\r\n", s_sign_cycles[i], s_sign_retries[i], (unsigned)s_sign_fail[i]);
    }
    printf("SIGN_END\r\n");
    printf("VF_BEGIN\r\n");
    for (int i = 0; i < N_DET; i++) { printf("%lu\r\n", s_vf_cycles[i]); }
    printf("VF_END\r\n");
    printf("BENCH_COMPLETE\r\n");

    vTaskDelete(nullptr);
}

extern "C" void app_main(void)
{
    printf("mldsa_bench_esp32s3\r\n");
    /* Pin the benchmark to core 0; the FreeRTOS main task already runs there.
     * Disable logging noise during the timed loop by buffering. */
    xTaskCreatePinnedToCore(run_bench, "mldsa", 131072, nullptr, 5, nullptr, 0);
}
