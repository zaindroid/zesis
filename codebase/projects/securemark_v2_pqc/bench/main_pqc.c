/*
 * main_pqc.c — standalone PQC bench: native wolfSSL ML-KEM and ML-DSA on the
 * FRDM-MCXN947 (Cortex-M33 @150 MHz, bare metal, no RTOS, no debugger).
 *
 * This is the vehicle that produces the numbers the SecureMark-V2 ee_* PQC
 * suites will consume: DWT cycle counts per primitive, peak stack, and a
 * synthesized regression CRC over the deterministic output buffers.
 *
 * Reporting follows the dual scheme:
 *   SELF-CHECK: PASS   the functional round-trip held (KEM: ss_enc == ss_dec,
 *                      DSA: verify returned valid)
 *   PQC-CRC: 0x....    CRC-32 over the deterministic output buffers; this is a
 *                      regression checksum, NOT an EEMBC golden value (no
 *                      upstream PQC reference exists)
 *
 * Only the primitive call sits inside the measured window. Buffer copies and
 * the round-trip comparison are outside it.
 */
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "app.h"
#include "fsl_debug_console.h"
#include "dwt.h"

#include <wolfssl/wolfcrypt/random.h>
#include <wolfssl/wolfcrypt/wc_mlkem.h>
#include <wolfssl/wolfcrypt/wc_mldsa.h>

#include "th_pqc.h"

#define CPU_HZ      150000000u
#define KEM_ITERS   20u
#define DSA_ITERS   20u

/* ---- deterministic block RNG for wolfSSL (CUSTOM_RAND_GENERATE_BLOCK) ---- */
static uint32_t g_rand_state = 0x12345678u;
int custom_rand_block(unsigned char *out, unsigned int sz);
int custom_rand_block(unsigned char *out, unsigned int sz)
{
    unsigned int i;
    for (i = 0; i < sz; i++) {
        g_rand_state = g_rand_state * 1664525u + 1013904223u;
        out[i] = (unsigned char)(g_rand_state >> 24);
    }
    return 0;
}

/* ---- static-pool allocator for wolfSSL (XMALLOC_OVERRIDE) ----
 * First-fit free list over a fixed pool. 16-byte header keeps payloads
 * 8/16-byte aligned, which the ML-DSA/ML-KEM NTT needs. Replaces the heap
 * that was failing with MEMORY_E (-125) on bare metal. */
#define POOL_SIZE (160u * 1024u)
static unsigned char g_pool[POOL_SIZE] __attribute__((aligned(16)));

typedef struct pool_hdr {
    size_t            size;
    struct pool_hdr  *next;
    size_t            free;
    size_t            pad;
} pool_hdr_t;

static pool_hdr_t *g_head;

static void pool_init(void)
{
    g_head = (pool_hdr_t *)g_pool;
    g_head->size = POOL_SIZE - sizeof(pool_hdr_t);
    g_head->next = NULL;
    g_head->free = 1;
}

void *wolf_pqc_malloc(size_t n)
{
    pool_hdr_t *h;
    size_t need = (n + 15u) & ~(size_t)15u;

    if (g_head == NULL) pool_init();
    for (h = g_head; h != NULL; h = h->next) {
        if (h->free && h->size >= need) {
            if (h->size >= need + sizeof(pool_hdr_t) + 16u) {
                pool_hdr_t *sp = (pool_hdr_t *)((unsigned char *)h + sizeof(pool_hdr_t) + need);
                sp->size = h->size - need - sizeof(pool_hdr_t);
                sp->free = 1;
                sp->next = h->next;
                h->size = need;
                h->next = sp;
            }
            h->free = 0;
            return (void *)((unsigned char *)h + sizeof(pool_hdr_t));
        }
    }
    return NULL;
}

void wolf_pqc_free(void *p)
{
    pool_hdr_t *h;
    if (p == NULL) return;
    h = (pool_hdr_t *)((unsigned char *)p - sizeof(pool_hdr_t));
    h->free = 1;
    for (h = g_head; h != NULL; ) {
        if (h->free && h->next != NULL && h->next->free &&
            (unsigned char *)h + sizeof(pool_hdr_t) + h->size == (unsigned char *)h->next) {
            h->size += sizeof(pool_hdr_t) + h->next->size;
            h->next = h->next->next;
        } else {
            h = h->next;
        }
    }
}

void *wolf_pqc_realloc(void *p, size_t n)
{
    pool_hdr_t *h;
    void *np;
    if (p == NULL) return wolf_pqc_malloc(n);
    h = (pool_hdr_t *)((unsigned char *)p - sizeof(pool_hdr_t));
    if (h->size >= n) return p;
    np = wolf_pqc_malloc(n);
    if (np != NULL) {
        memcpy(np, p, h->size);
        wolf_pqc_free(p);
    }
    return np;
}

/* ---- static workspace (no heap on bare metal) ---- */
static unsigned char g_ws[8 * 1024];
static size_t        g_ws_used;

void *th_malloc(size_t size)
{
    size_t aligned = (size + 7u) & ~(size_t)7u;
    if (g_ws_used + aligned > sizeof(g_ws)) return NULL;
    void *p = &g_ws[g_ws_used];
    g_ws_used += aligned;
    return p;
}
void th_free(void *p) { (void)p; }

int th_printf(const char *fmt, ...)
{
    static char buf[256];
    va_list ap;
    int n;
    va_start(ap, fmt);
    n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    DbgConsole_Printf("%s", buf);
    return n;
}

/* ---- CRC-32 (IEEE 802.3, reflected, poly 0xEDB88320) ---- */
static uint32_t crc32(const uint8_t *d, uint32_t n)
{
    uint32_t crc = 0xFFFFFFFFu, i, j;
    for (i = 0; i < n; i++) {
        crc ^= d[i];
        for (j = 0; j < 8; j++)
            crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)(-(int32_t)(crc & 1u)));
    }
    return ~crc;
}

/* ---- buffers sized for the largest parameter sets ---- */
static uint8_t buf_pk[1600];      /* ML-KEM-1024 pk = 1568 */
static uint8_t buf_sk[3200];      /* ML-KEM-1024 sk = 3168 */
static uint8_t buf_ct[1600];
static uint8_t buf_ss1[64], buf_ss2[64];

static uint8_t d_pk[2624];        /* ML-DSA-87 pk = 2592 */
static uint8_t d_sk[4928];        /* ML-DSA-87 sk = 4896 */
static uint8_t d_sig[4700];       /* ML-DSA-87 sig = 4627 */
static uint8_t d_msg[256];        /* D2I telemetry frame */
static uint8_t d_hash[64];        /* SHA-512 digest for HashML-DSA */

static uint32_t dsa_crc;

/* ---- per-operation peak stack -------------------------------------------
 * Paint the still-unused part of the stack with a magic word before an
 * operation, then scan back after it: the lowest address that lost the magic
 * is the deepest the op reached, so HWM = __StackTop - that address.
 * Additive instrumentation: it does not touch the measured output buffers, so
 * the regression CRCs are unaffected.
 */
extern uint32_t __StackLimit[];
extern uint32_t __StackTop[];
#define STACK_MAGIC 0xEEEEEEEEu
static uint32_t *g_paint_lo;

static void stack_paint(void)
{
    uint32_t sp;
    __asm volatile ("mov %0, sp" : "=r"(sp));
    uint32_t *p = (uint32_t *)((sp - 512u) & ~0x7u);   /* below our own frame */
    g_paint_lo = p;
    while (p > __StackLimit) { *p = STACK_MAGIC; p--; }
}

static uint32_t stack_hwm(void)
{
    uint32_t *p = g_paint_lo;
    while (p > __StackLimit && *p == STACK_MAGIC) p--;
    return (uint32_t)((uint8_t *)__StackTop - (uint8_t *)p);
}

static void run_mlkem(ee_mlkem_size_t lvl, const char *name, WC_RNG *rng)
{
    void *ctx = NULL;
    uint32_t pklen = 0, sklen = 0, ctlen = 0, ss1len = 0, ss2len = 0;
    uint32_t c_kp, c_enc, c_dec;
    uint32_t s_kp, s_enc, s_dec;
    int same;
    uint8_t crcbuf[1600 + 64];
    uint32_t crclen;

    g_rand_state = 0x12345678u;          /* reset for reproducible CRC */
    g_ws_used = 0;

    if (th_mlkem_create(&ctx, lvl) != EE_STATUS_OK) { PRINTF("%s create FAIL\r\n", name); return; }
    th_mlkem_init(ctx);

    stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
        th_mlkem_keypair(ctx, rng, buf_pk, &pklen, buf_sk, &sklen);
        c_kp = dwt_get() - t0; } s_kp = stack_hwm();

    stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
        th_mlkem_encapsulate(ctx, rng, buf_ct, &ctlen, buf_ss1, &ss1len);
        c_enc = dwt_get() - t0; } s_enc = stack_hwm();

    stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
        th_mlkem_decapsulate(ctx, buf_ss2, &ss2len, buf_ct, ctlen);
        c_dec = dwt_get() - t0; } s_dec = stack_hwm();

    /* round-trip check outside the measured windows */
    same = (ss1len == ss2len) && (memcmp(buf_ss1, buf_ss2, ss1len) == 0);

    memcpy(crcbuf, buf_ct, ctlen);
    memcpy(crcbuf + ctlen, buf_ss1, ss1len);
    crclen = ctlen + ss1len;

    PRINTF("%s KEM keypair,enc,dec cycles=%u,%u,%u us=%u,%u,%u\r\n", name,
           (unsigned)c_kp, (unsigned)c_enc, (unsigned)c_dec,
           (unsigned)(c_kp / (CPU_HZ / 1000000u)),
           (unsigned)(c_enc / (CPU_HZ / 1000000u)),
           (unsigned)(c_dec / (CPU_HZ / 1000000u)));
    PRINTF("%s STACK hwm_bytes kp,enc,dec=%u,%u,%u\r\n", name,
           (unsigned)s_kp, (unsigned)s_enc, (unsigned)s_dec);
    PRINTF("%s SELF-CHECK: %s  (ct=%u ss=%u)\r\n", name, same ? "PASS" : "FAIL",
           (unsigned)ctlen, (unsigned)ss1len);
    PRINTF("%s PQC-CRC: 0x%08X  [synthesized regression checksum over ct||ss; no EEMBC upstream reference]\r\n",
           name, (unsigned)crc32(crcbuf, crclen));

    th_mlkem_destroy(ctx);
}

static void run_mldsa(ee_mldsa_size_t lvl, const char *name, WC_RNG *rng, int do_hash)
{
    void *ctx = NULL;
    uint32_t pklen = 0, sklen = 0, siglen = 0;
    uint32_t c_kp, c_sign, c_vf;
    uint32_t s_kp, s_sign, s_vf;
    int res = 0;
    int i;

    g_rand_state = 0x9ABCDEF0u;          /* reset for reproducible CRC */
    g_ws_used = 0;

    for (i = 0; i < (int)sizeof(d_msg); i++) d_msg[i] = (uint8_t)(i + 1);
    for (i = 0; i < (int)sizeof(d_hash); i++) d_hash[i] = (uint8_t)(0xA5 ^ i);

    if (th_mldsa_create(&ctx, lvl) != EE_STATUS_OK) { PRINTF("%s create FAIL\r\n", name); return; }
    th_mldsa_init(ctx);

    stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
        th_mldsa_keypair(ctx, rng, d_pk, &pklen, d_sk, &sklen);
        c_kp = dwt_get() - t0; } s_kp = stack_hwm();

    if (do_hash) {
        stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
            th_mldsa_sign_hash(ctx, rng, NULL, 0, d_hash, sizeof(d_hash), d_sig, &siglen);
            c_sign = dwt_get() - t0; } s_sign = stack_hwm();
        stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
            th_mldsa_verify_hash(ctx, NULL, 0, d_hash, sizeof(d_hash), d_sig, siglen, &res);
            c_vf = dwt_get() - t0; } s_vf = stack_hwm();
    } else {
        stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
            th_mldsa_sign(ctx, rng, NULL, 0, d_msg, sizeof(d_msg), d_sig, &siglen);
            c_sign = dwt_get() - t0; } s_sign = stack_hwm();
        stack_paint(); dwt_reset(); { uint32_t t0 = dwt_get();
            th_mldsa_verify(ctx, NULL, 0, d_msg, sizeof(d_msg), d_sig, siglen, &res);
            c_vf = dwt_get() - t0; } s_vf = stack_hwm();
    }

    PRINTF("%s keypair,sign,verify cycles=%u,%u,%u us=%u,%u,%u\r\n", name,
           (unsigned)c_kp, (unsigned)c_sign, (unsigned)c_vf,
           (unsigned)(c_kp / (CPU_HZ / 1000000u)),
           (unsigned)(c_sign / (CPU_HZ / 1000000u)),
           (unsigned)(c_vf / (CPU_HZ / 1000000u)));
    PRINTF("%s STACK hwm_bytes kp,sign,verify=%u,%u,%u\r\n", name,
           (unsigned)s_kp, (unsigned)s_sign, (unsigned)s_vf);
    PRINTF("%s SELF-CHECK: %s  (sig=%u)\r\n", name, res ? "PASS" : "FAIL", (unsigned)siglen);
    PRINTF("%s PQC-CRC: 0x%08X  [synthesized regression checksum over sig; no EEMBC upstream reference]\r\n",
           name, (unsigned)crc32(d_sig, siglen));

    dsa_crc = crc32(d_sig, siglen);
    th_mldsa_destroy(ctx);
}

int main(void)
{
    WC_RNG rng;
    int rc;

    BOARD_InitHardware();
    dwt_init();

    PRINTF("\r\n=== standalone PQC bench (wolfSSL native) ===\r\n");
    PRINTF("plat,mcxn947,cpu_hz=%u\r\n", (unsigned)CPU_HZ);

    rc = wc_InitRng(&rng);
    PRINTF("wc_InitRng rc=%d (deterministic CUSTOM_RAND_GENERATE_BLOCK)\r\n", rc);

    run_mlkem(EE_MLKEM_512,  "ML-KEM-512",  &rng);
    run_mlkem(EE_MLKEM_768,  "ML-KEM-768",  &rng);
    run_mlkem(EE_MLKEM_1024, "ML-KEM-1024", &rng);

    run_mldsa(EE_MLDSA_44, "ML-DSA-44", &rng, 0);
    run_mldsa(EE_MLDSA_65, "ML-DSA-65", &rng, 0);
    run_mldsa(EE_MLDSA_87, "ML-DSA-87", &rng, 0);
    run_mldsa(EE_MLDSA_65, "HashML-DSA-65", &rng, 1);

    PRINTF("BENCH_COMPLETE\r\n");
    for (;;) { }
}
