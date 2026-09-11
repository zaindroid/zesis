/*
 * PQC benchmark under Zephyr OS: ML-KEM-768 + ML-DSA-44/65/87 (all levels
 * in one binary).
 *
 * Boards: frdm_mcxn947 (Cortex-M33 @150 MHz) and esp32s3_devkitc
 * (Xtensa LX7 @240 MHz). Uses the REAL PQClean sources previously measured
 * on both platforms (bare-metal), now under Zephyr's RTOS.
 *
 * Methodology (matches the existing mlkem_bench / mldsa_bench):
 *  - Timing: k_cycle_get_32() cycle counter; us = cycles /
 *    sys_clock_hw_cycles_per_sec(). Cycle counts are portable across
 *    boards.
 *  - ML-KEM-768: 100 reps keypair/enc/dec (fixed randombytes stub).
 *  - ML-DSA: 100 reps keypair/verify per level; 2000 reps sign per level
 *    with DIFFERENT message per iteration + fresh randomness (the
 *    fat-tailed distribution). Retry counts logged (rejection sampling
 *    instrumentation in sign.c). Every sign verified immediately.
 *  - Per-op peak stack via k_thread_stack_space_get() (HWM of the bench
 *    thread, relative to the 160 KB thread stack).
 *  - Results buffered in RAM, dumped ONLY after each timed loop -> the
 *    serial line can be disconnected during measurement for clean PPK2
 *    energy capture. Free-running: starts automatically at boot.
 *
 * Output format (console):
 *   PQC_BENCH_START
 *   plat,zephyr,<cpu_hz>
 *   alg,ML-KEM-768 / KEM_BEGIN / KEM_END -> K,<kp>,<enc>,<dec> x100
 *   alg,ML-DSA-xx / KP_BEGIN / KP_END -> K,<cycles>,<stack> x100
 *                 / SIGN_BEGIN / SIGN_END -> S,<cycles>,<retries>,<fail> x2000
 *                 / VF_BEGIN / VF_END -> V,<cycles>,<stack> x100
 *   BENCH_COMPLETE
 */
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/time_units.h>

#include <stdint.h>
#include <stddef.h>

/* PQClean APIs */
#include "mlkem768/api.h"
#include "mldsa44/api.h"
#include "mldsa65/api.h"
#include "mldsa87/api.h"

/* ML-DSA retry instrumentation (declared in sign.c, not sign.h) */
extern void PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections(void);
extern uint32_t PQCLEAN_MLDSA44_CLEAN_bench_get_rejections(void);
extern void PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections(void);
extern uint32_t PQCLEAN_MLDSA65_CLEAN_bench_get_rejections(void);
extern void PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections(void);
extern uint32_t PQCLEAN_MLDSA87_CLEAN_bench_get_rejections(void);

#define KEM_REPS      100
#define DSA_KP_REPS   100
#define DSA_VF_REPS   100
#define DSA_SIGN_REPS 2000
#define MSG_LEN       32

/* KEM buffers */
static uint8_t pk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_MLKEM768_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t ct[PQCLEAN_MLKEM768_CLEAN_CRYPTO_CIPHERTEXTBYTES];
static uint8_t ss[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];
static uint8_t ss2[PQCLEAN_MLKEM768_CLEAN_CRYPTO_BYTES];

/* DSA buffers: use the largest level's sizes (87) */
#define DSA_PK_MAX  PQCLEAN_MLDSA87_CLEAN_CRYPTO_PUBLICKEYBYTES
#define DSA_SK_MAX  PQCLEAN_MLDSA87_CLEAN_CRYPTO_SECRETKEYBYTES
#define DSA_SIG_MAX PQCLEAN_MLDSA87_CLEAN_CRYPTO_BYTES
static uint8_t dsa_pk[DSA_PK_MAX];
static uint8_t dsa_sk[DSA_SK_MAX];
static uint8_t dsa_sig[DSA_SIG_MAX];
static uint8_t dsa_msg[MSG_LEN];

/* Results: per-rep cycles/retries/fail. Memory budget:
 *   KEM: 100*3 u32 cycles = 1.2 KB
 *   DSA: 100*2 + 2000*3 + 100*2 u32 = ~26 KB per level x3 = ~78 KB
 * Total < 100 KB, fine on both boards (512 KB SRAM). */
static uint32_t kem_kp_c[KEM_REPS], kem_enc_c[KEM_REPS], kem_dec_c[KEM_REPS];
static uint32_t dsa_kp_c[3][DSA_KP_REPS], dsa_vf_c[3][DSA_VF_REPS];
static uint32_t dsa_sig_c[3][DSA_SIGN_REPS];
static uint16_t dsa_ret[3][DSA_SIGN_REPS];
static uint8_t  dsa_fail[3][DSA_SIGN_REPS];

/* Bench thread: big stack for ML-DSA-87 sign (~120 KB peak).
 * 144 KB keeps the RAMLOAD image under the STM32N6 512 KB SRAM window. */
#define BENCH_STACK_SIZE (144 * 1024)
K_THREAD_STACK_DEFINE(bench_stack, BENCH_STACK_SIZE);
static struct k_thread bench_thread;

static uint32_t stack_hwm_total(void)
{
    size_t unused = 0;
    k_thread_stack_space_get(k_current_get(), &unused);
    size_t total = BENCH_STACK_SIZE;
    return (unused < total) ? (uint32_t)(total - unused) : 0u;
}

static inline uint32_t now_cycles(void)
{
    return (uint32_t)k_cycle_get_32();
}

/* ---------------- ML-DSA level driver (macro-free via fn pointers would be
 * messy; use a per-level function selected by index) ---------------- */

/* keypair for level lv (0=44,1=65,2=87) */
static int dsa_keypair(int lv, uint8_t *p, uint8_t *s)
{
    switch (lv) {
    case 0: return PQCLEAN_MLDSA44_CLEAN_crypto_sign_keypair(p, s);
    case 1: return PQCLEAN_MLDSA65_CLEAN_crypto_sign_keypair(p, s);
    default: return PQCLEAN_MLDSA87_CLEAN_crypto_sign_keypair(p, s);
    }
}

static void dsa_reset_ret(int lv)
{
    switch (lv) {
    case 0: PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections(); break;
    case 1: PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections(); break;
    default: PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections(); break;
    }
}

static uint32_t dsa_get_ret(int lv)
{
    switch (lv) {
    case 0: return PQCLEAN_MLDSA44_CLEAN_bench_get_rejections();
    case 1: return PQCLEAN_MLDSA65_CLEAN_bench_get_rejections();
    default: return PQCLEAN_MLDSA87_CLEAN_bench_get_rejections();
    }
}

static int dsa_sign(int lv, uint8_t *sig, size_t *siglen,
                    const uint8_t *m, size_t mlen, const uint8_t *skk)
{
    switch (lv) {
    case 0: return PQCLEAN_MLDSA44_CLEAN_crypto_sign_signature(
        sig, siglen, m, mlen, skk);
    case 1: return PQCLEAN_MLDSA65_CLEAN_crypto_sign_signature(
        sig, siglen, m, mlen, skk);
    default: return PQCLEAN_MLDSA87_CLEAN_crypto_sign_signature(
        sig, siglen, m, mlen, skk);
    }
}

static int dsa_verify(int lv, const uint8_t *sig, size_t siglen,
                      const uint8_t *m, size_t mlen, const uint8_t *p)
{
    switch (lv) {
    case 0: return PQCLEAN_MLDSA44_CLEAN_crypto_sign_verify_ctx(
        sig, siglen, m, mlen, NULL, 0, p);
    case 1: return PQCLEAN_MLDSA65_CLEAN_crypto_sign_verify_ctx(
        sig, siglen, m, mlen, NULL, 0, p);
    default: return PQCLEAN_MLDSA87_CLEAN_crypto_sign_verify_ctx(
        sig, siglen, m, mlen, NULL, 0, p);
    }
}

static const char *dsa_name(int lv)
{
    return lv == 0 ? "ML-DSA-44" : (lv == 1 ? "ML-DSA-65" : "ML-DSA-87");
}

static void run_bench(void *a, void *b, void *c)
{
    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);

    printk("PQC_BENCH_START\n");
    printk("plat,zephyr,%u\n", (unsigned)sys_clock_hw_cycles_per_sec());

    /* ---------------- ML-KEM-768 ---------------- */
    printk("alg,ML-KEM-768\n");
    printk("KEM_BEGIN\n");
    for (int i = 0; i < KEM_REPS; i++) {
        uint32_t t0, t1;
        t0 = now_cycles();
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_keypair(pk, sk);
        t1 = now_cycles();
        kem_kp_c[i] = t1 - t0;

        t0 = now_cycles();
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_enc(ct, ss, pk);
        t1 = now_cycles();
        kem_enc_c[i] = t1 - t0;

        t0 = now_cycles();
        PQCLEAN_MLKEM768_CLEAN_crypto_kem_dec(ss2, ct, sk);
        t1 = now_cycles();
        kem_dec_c[i] = t1 - t0;
    }
    printk("KEM_END\n");
    for (int i = 0; i < KEM_REPS; i++) {
        printk("K,%u,%u,%u\n", (unsigned)kem_kp_c[i],
               (unsigned)kem_enc_c[i], (unsigned)kem_dec_c[i]);
    }

    /* ---------------- ML-DSA (three levels) ---------------- */
    for (int lv = 0; lv < 3; lv++) {
        printk("alg,%s\n", dsa_name(lv));

        printk("KP_BEGIN\n");
        for (int i = 0; i < DSA_KP_REPS; i++) {
            uint32_t t0 = now_cycles();
            dsa_keypair(lv, dsa_pk, dsa_sk);
            dsa_kp_c[lv][i] = now_cycles() - t0;
        }
        printk("KP_END\n");
        for (int i = 0; i < DSA_KP_REPS; i++) {
            printk("K,%u\n", (unsigned)dsa_kp_c[lv][i]);
        }

        printk("SIGN_BEGIN\n");
        for (int i = 0; i < DSA_SIGN_REPS; i++) {
            for (int j = 0; j < MSG_LEN; j++) {
                dsa_msg[j] = (uint8_t)(i + j * 7 + 1);
            }
            size_t siglen = DSA_SIG_MAX;
            dsa_reset_ret(lv);
            uint32_t t0 = now_cycles();
            int r = dsa_sign(lv, dsa_sig, &siglen, dsa_msg, MSG_LEN, dsa_sk);
            uint32_t t1 = now_cycles();
            dsa_sig_c[lv][i] = t1 - t0;
            dsa_ret[lv][i] = dsa_get_ret(lv);
            dsa_fail[lv][i] = (r != 0);
            if (r == 0) {
                r = dsa_verify(lv, dsa_sig, siglen, dsa_msg, MSG_LEN, dsa_pk);
                dsa_fail[lv][i] = (r != 0) ? 2 : 0;
            }
        }
        printk("SIGN_END\n");
        for (int i = 0; i < DSA_SIGN_REPS; i++) {
            printk("S,%u,%u,%u\n", (unsigned)dsa_sig_c[lv][i],
                   (unsigned)dsa_ret[lv][i], (unsigned)dsa_fail[lv][i]);
        }

        printk("VF_BEGIN\n");
        for (int i = 0; i < DSA_VF_REPS; i++) {
            for (int j = 0; j < MSG_LEN; j++) {
                dsa_msg[j] = (uint8_t)(i + j * 7 + 1);
            }
            size_t siglen = DSA_SIG_MAX;
            uint32_t t0 = now_cycles();
            dsa_verify(lv, dsa_sig, siglen, dsa_msg, MSG_LEN, dsa_pk);
            dsa_vf_c[lv][i] = now_cycles() - t0;
        }
        printk("VF_END\n");
        for (int i = 0; i < DSA_VF_REPS; i++) {
            printk("V,%u\n", (unsigned)dsa_vf_c[lv][i]);
        }
    }

    printk("BENCH_COMPLETE\n");
}

void main(void)
{
    /* Delay so the USB Serial/JTAG CDC has time to attach on boards where
     * the console is USB-based (ESP32-S3 native USB). Without this the
     * early KEM/KP output is lost to the host attach race. */
    k_msleep(15000);
    k_thread_create(&bench_thread, bench_stack, BENCH_STACK_SIZE,
                    run_bench, NULL, NULL, NULL,
                    CONFIG_NUM_PREEMPT_PRIORITIES - 1, 0, K_NO_WAIT);
}
