/*
 * ML-DSA (Dilithium, FIPS 204) signing-latency DISTRIBUTION benchmark.
 *
 * The point of this firmware is NOT a mean signing time -- it's the
 * run-to-run VARIANCE caused by ML-DSA's rejection-sampling signing loop
 * (see pqclean/sign.c's `rej:` label). keypair and verify are
 * near-deterministic single-pass operations; sign can retry an unbounded
 * (in principle) number of times depending on the message + fresh
 * per-call randomness, so its latency has a fat right tail that a mean
 * alone would hide. Every individual sign call's cycle count, stack
 * high-water-mark, and rejection-retry count is logged RAW -- no
 * on-device averaging for sign -- so the full distribution (including the
 * worst observed tail) can be reconstructed and independently verified
 * from the dumped CSV on the host.
 *
 * Algorithm variant is swapped via H:\z_thesis\swap_dilithium.py <44|65|87>
 * (mirrors mlkem_bench's swap.ps1 pattern; see that script's docstring
 * for the retry-count instrumentation it patches into sign.c, since
 * PQClean's public API doesn't otherwise expose the internal rejection
 * count).
 *
 * Measurement discipline (same lab rules as mlkem_bench, see
 * BENCHMARK_METHODOLOGY.md there):
 *   - DWT->CYCCNT for cycle-accurate timing.
 *   - Free-running: flash, then run completely undebugged (no debugger
 *     attached) with the serial terminal DISCONNECTED during the actual
 *     measurement loop -- both perturb timing on this setup. ALL results
 *     are buffered in RAM and printed only once, after every measurement
 *     loop has fully completed; nothing is printed mid-loop. This matters
 *     more here than for ML-KEM's tight-variance ops: this experiment IS
 *     the variance, so any UART-TX-induced jitter mid-loop would
 *     contaminate the exact thing being measured.
 *   - Stack high-water-mark via the same "paint then scan" technique as
 *     mlkem_bench (see that project's hello_world.c for the technique's
 *     rationale) -- painted and scanned around EVERY individual sign
 *     call, not just once, so a per-call stack figure is available (the
 *     spec asks whether stack depth itself varies with retry count; the
 *     `rej:` loop is a goto within one stack frame, not recursion, so we
 *     expect it NOT to vary, but let's actually observe it rather than
 *     assume).
 *
 * A different message is signed on every iteration (loop counter written
 * into the message buffer) using fresh internal randomness each call
 * (PQClean's own `randombytes()` call inside crypto_sign_signature_ctx,
 * backed by this project's deterministic-but-stateful xorshift stub --
 * same convention as mlkem_bench, advances every call so it's never the
 * same draw twice). Signing the SAME fixed message repeatedly was
 * explicitly avoided per the task spec: rejection-sampling variance
 * depends on both the message and the randomness draw, and a fixed
 * message risks collapsing the observed distribution and hiding the
 * tail.
 */
#include "board.h"
#include "app.h"
#include "fsl_debug_console.h"
#include "dwt.h"
#include "api.h"
#include <string.h>

#define KEYPAIR_VERIFY_REPS 100
#define N_SIGN 2048

static uint8_t pk[PQCLEAN_MLDSA87_CLEAN_CRYPTO_PUBLICKEYBYTES];
static uint8_t sk[PQCLEAN_MLDSA87_CLEAN_CRYPTO_SECRETKEYBYTES];
static uint8_t sig[PQCLEAN_MLDSA87_CLEAN_CRYPTO_BYTES];
static size_t siglen;

/* Rejection-retry counter exposed by swap_dilithium.py's sign.c patch
 * (see that script's docstring). Declared extern here rather than
 * pulled from a header since it's benchmark-only instrumentation, not
 * part of PQClean's real API surface. */
extern uint32_t PQCLEAN_MLDSA87_CLEAN_last_sign_attempts;

/* Message buffer: first 4 bytes carry the iteration counter (guarantees
 * a distinct message every call), remainder is fixed filler. 64 bytes
 * total -- arbitrary but representative of a short signed payload
 * (larger than a bare hash digest, far smaller than needing chunked
 * absorption). */
#define MSG_BYTES 64
static uint8_t msg[MSG_BYTES];

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

/* Raw per-call sign data -- buffered, never pre-averaged. N_SIGN * 4
 * uint32_t arrays = 32 KiB for N_SIGN=2048; comfortably fits alongside
 * the stack region and everything else in this chip's RAM. */
static uint32_t s_signCycles[N_SIGN];
static uint32_t s_signStackHwm[N_SIGN];
static uint32_t s_signAttempts[N_SIGN]; /* 1 = no rejection, N = N-1 rejections */
static uint8_t  s_signVerifyOk[N_SIGN]; /* 1 = sign->verify round-trip passed */

int main(void)
{
    uint32_t c;
    uint32_t cyc[KEYPAIR_VERIFY_REPS];

    BOARD_InitHardware();
    dwt_init();

    dwt_reset();
    for (volatile int i = 0; i < 1000; i++) { }
    PRINTF("dwt_sanity,%d\r\n", (int)dwt_get());

    PRINTF("alg,%s\r\n", "ML-DSA (" PQCLEAN_MLDSA87_CLEAN_CRYPTO_ALGNAME ")");
    PRINTF("stack_region_bytes,%d\r\n",
           (int)((uint8_t *)__StackTop - (uint8_t *)__StackLimit));
    PRINTF("pk_bytes,%d\r\n", (int)PQCLEAN_MLDSA87_CLEAN_CRYPTO_PUBLICKEYBYTES);
    PRINTF("sk_bytes,%d\r\n", (int)PQCLEAN_MLDSA87_CLEAN_CRYPTO_SECRETKEYBYTES);
    PRINTF("sig_bytes,%d\r\n", (int)PQCLEAN_MLDSA87_CLEAN_CRYPTO_BYTES);
    PRINTF("n_sign_reps,%d\r\n", (int)N_SIGN);

    /* --- keypair: near-deterministic, 100 reps, on-device mean+spread is
     * fine (host-side analysis still gets the per-call array too, so
     * this isn't the only source of truth). --- */
    for (int i = 0; i < KEYPAIR_VERIFY_REPS; i++)
    {
        StackPaint();
        dwt_reset();
        PQCLEAN_MLDSA87_CLEAN_crypto_sign_keypair(pk, sk);
        cyc[i] = dwt_get();
    }
    {
        uint32_t sum = 0, mn = 0xFFFFFFFFu, mx = 0;
        for (int i = 0; i < KEYPAIR_VERIFY_REPS; i++)
        {
            sum += cyc[i];
            if (cyc[i] < mn) mn = cyc[i];
            if (cyc[i] > mx) mx = cyc[i];
        }
        PRINTF("keypair_mean_cycles,%d\r\n", (int)(sum / KEYPAIR_VERIFY_REPS));
        PRINTF("keypair_min_cycles,%d\r\n", (int)mn);
        PRINTF("keypair_max_cycles,%d\r\n", (int)mx);
        PRINTF("keypair_stack_hwm_bytes,%d\r\n", (int)StackHighWaterMarkBytes());
    }

    /* Fixed keypair used for the verify-timing loop below and as the
     * starting sk for the sign loop -- verify's timing is structurally
     * fixed-work regardless of which valid signature it's checking, so
     * reusing one signature here (unlike sign, which must see a fresh
     * message+signature every call) doesn't compromise anything. */
    memset(msg, 0, sizeof(msg));
    PQCLEAN_MLDSA87_CLEAN_crypto_sign_signature(sig, &siglen, msg, sizeof(msg), sk);

    /* --- verify: near-deterministic, 100 reps. --- */
    for (int i = 0; i < KEYPAIR_VERIFY_REPS; i++)
    {
        StackPaint();
        dwt_reset();
        PQCLEAN_MLDSA87_CLEAN_crypto_sign_verify(sig, siglen, msg, sizeof(msg), pk);
        cyc[i] = dwt_get();
    }
    {
        uint32_t sum = 0, mn = 0xFFFFFFFFu, mx = 0;
        for (int i = 0; i < KEYPAIR_VERIFY_REPS; i++)
        {
            sum += cyc[i];
            if (cyc[i] < mn) mn = cyc[i];
            if (cyc[i] > mx) mx = cyc[i];
        }
        PRINTF("verify_mean_cycles,%d\r\n", (int)(sum / KEYPAIR_VERIFY_REPS));
        PRINTF("verify_min_cycles,%d\r\n", (int)mn);
        PRINTF("verify_max_cycles,%d\r\n", (int)mx);
        PRINTF("verify_stack_hwm_bytes,%d\r\n", (int)StackHighWaterMarkBytes());
    }

    /* --- SIGN: the actual experiment. >=2000 reps, different message
     * every call, full per-call raw log, sign->verify checked every
     * time. Nothing printed until the whole loop is done. --- */
    int verifyFailCount = 0;
    for (int i = 0; i < N_SIGN; i++)
    {
        memset(msg, 0, sizeof(msg));
        msg[0] = (uint8_t)(i);
        msg[1] = (uint8_t)(i >> 8);
        msg[2] = (uint8_t)(i >> 16);
        msg[3] = (uint8_t)(i >> 24);

        StackPaint();
        dwt_reset();
        PQCLEAN_MLDSA87_CLEAN_crypto_sign_signature(sig, &siglen, msg, sizeof(msg), sk);
        c = dwt_get();

        s_signCycles[i] = c;
        s_signStackHwm[i] = StackHighWaterMarkBytes();
        s_signAttempts[i] = PQCLEAN_MLDSA87_CLEAN_last_sign_attempts;

        int vr = PQCLEAN_MLDSA87_CLEAN_crypto_sign_verify(sig, siglen, msg, sizeof(msg), pk);
        s_signVerifyOk[i] = (vr == 0) ? 1 : 0;
        if (vr != 0) { verifyFailCount++; }
    }

    /* Everything below only runs after the timed loop above is fully
     * complete -- safe to print now. */
    PRINTF("sign_verify_fail_count,%d\r\n", verifyFailCount);
    PRINTF("sign_op,cycles,stack_hwm_bytes,attempts,verify_ok\r\n");
    for (int i = 0; i < N_SIGN; i++)
    {
        PRINTF("sign,%d,%d,%d,%d\r\n",
               (int)s_signCycles[i], (int)s_signStackHwm[i],
               (int)s_signAttempts[i], (int)s_signVerifyOk[i]);
    }

    PRINTF("done\r\n");
    while (1) { }
}
