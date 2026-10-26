/*
 * main_task3a.c — Task 3A: secure-boot firmware signature verification.
 *
 * Verifies a 128 KB firmware payload under four schemes on the FRDM-MCXN947,
 * bare metal, DWT cycle counter, -O2:
 *
 *   ECDSA P-256        classical baseline (hash-and-sign, SHA-256)
 *   ML-DSA-44   pure   the payload must be addressable in full
 *   ML-DSA-65   pure
 *   HashML-DSA-65      pre-hashed (SHA-512), payload can be streamed
 *
 * Reported per scheme: verification time, signature size, and the peak RAM the
 * verifier needs. The distinction that matters is buffering: pure ML-DSA hands
 * the whole payload to the API, so a device receiving it over a link must hold
 * all 128 KB; ECDSA and HashML-DSA verify a digest and can stream the payload
 * through the hash in fixed-size chunks.
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
#include <wolfssl/wolfcrypt/ecc.h>
#include <wolfssl/wolfcrypt/sha256.h>
#include <wolfssl/wolfcrypt/sha512.h>
#include <wolfssl/wolfcrypt/wc_mldsa.h>
#include <wolfssl/wolfcrypt/error-crypt.h>

#define CPU_HZ       150000000u
#define FW_BYTES     (128u * 1024u)   /* firmware payload */
#define CHUNK_BYTES  4096u            /* streaming chunk */
#define ECC_KEY_BITS 256
#define N_REPS       20      /* per-scheme repeats: signing is rejection sampled */

/* The payload arrives over a link; this is the RAM a device must hold for the
   schemes that cannot stream it. */
static uint8_t fw[FW_BYTES] __attribute__((aligned(16)));
static uint8_t chunk[CHUNK_BYTES];

static uint8_t sig[5120];             /* ML-DSA-87 sig = 4627 */
static uint8_t digest[64];

/* ---- static-pool allocator for wolfSSL (XMALLOC_OVERRIDE) ---- */
#define POOL_SIZE (96u * 1024u)
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
        if (h->free && h->next && h->next->free &&
            (unsigned char *)h + sizeof(pool_hdr_t) + h->size == (unsigned char *)h->next) {
            h->size += sizeof(pool_hdr_t) + h->next->size;
            h->next = h->next->next;
        } else h = h->next;
    }
}

void *wolf_pqc_realloc(void *p, size_t n)
{
    pool_hdr_t *h; void *np;
    if (p == NULL) return wolf_pqc_malloc(n);
    h = (pool_hdr_t *)((unsigned char *)p - sizeof(pool_hdr_t));
    if (h->size >= n) return p;
    np = wolf_pqc_malloc(n);
    if (np) { memcpy(np, p, h->size); wolf_pqc_free(p); }
    return np;
}

void *wolf_pqc_calloc(size_t n, size_t sz)
{
    size_t total = n * sz;
    void *p = wolf_pqc_malloc(total);
    if (p) memset(p, 0, total);
    return p;
}

/* deterministic block RNG for wolfSSL (CUSTOM_RAND_GENERATE_BLOCK) */
static uint32_t g_rand_state = 0x2468ACE0u;
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

/* ---- helpers ---- */
static uint32_t ms_from_cycles(uint32_t c)
{
    return (uint32_t)(((uint64_t)c * 1000000ull) / CPU_HZ);
}

static void fill_fw(void)
{
    uint32_t i;
    for (i = 0; i < FW_BYTES; i++) fw[i] = (uint8_t)((i * 31u + 7u) & 0xFF);
}

/* Hash the payload in fixed chunks, never holding more than CHUNK_BYTES.
   This is the streaming path ECDSA and HashML-DSA can use. */
static void hash_stream_sha256(uint8_t *out32)
{
    wc_Sha256 h;
    uint32_t off;
    wc_InitSha256(&h);
    for (off = 0; off < FW_BYTES; off += CHUNK_BYTES) {
        uint32_t n = (FW_BYTES - off) < CHUNK_BYTES ? (FW_BYTES - off) : CHUNK_BYTES;
        memcpy(chunk, fw + off, n);          /* stand-in for a link read */
        wc_Sha256Update(&h, chunk, n);
    }
    wc_Sha256Final(&h, out32);
}

static void hash_stream_sha512(uint8_t *out64)
{
    wc_Sha512 h;
    uint32_t off;
    wc_InitSha512(&h);
    for (off = 0; off < FW_BYTES; off += CHUNK_BYTES) {
        uint32_t n = (FW_BYTES - off) < CHUNK_BYTES ? (FW_BYTES - off) : CHUNK_BYTES;
        memcpy(chunk, fw + off, n);
        wc_Sha512Update(&h, chunk, n);
    }
    wc_Sha512Final(&h, out64);
}

/* ---- ECDSA P-256 ---- */
static void run_ecdsa(WC_RNG *rng)
{
    ecc_key key;
    int     ret;
    uint32_t siglen = sizeof(sig);
    uint32_t t0, c_sign, c_vf, c_hash = 0;
    uint32_t c_sign_lo=0,c_sign_hi=0,c_vf_lo=0,c_vf_hi=0;
    int     res = 0;

    dwt_reset(); t0 = dwt_get();
    hash_stream_sha256(digest);            /* SHA-256 over 128 KB, streamed */
    c_hash = dwt_get() - t0;

    wc_ecc_init(&key);
    if (wc_ecc_make_key_ex(rng, ECC_KEY_BITS / 8, &key, ECC_SECP256R1) != 0) {
        PRINTF("ECDSA P-256 FAILED\r\n"); return;
    }
    (void)wc_ecc_set_rng(&key, rng);

    {
        uint32_t r, d, sum = 0, lo = 0xFFFFFFFFu, hi = 0;
        for (r = 0; r < N_REPS; r++) {
            siglen = sizeof(sig);
            dwt_reset(); t0 = dwt_get();
            ret = wc_ecc_sign_hash(digest, 32, sig, &siglen, rng, &key);
            d = dwt_get() - t0;
            if (ret != 0) { PRINTF("ECDSA sign error %d\r\n", ret); return; }
            sum += d; if (d < lo) lo = d; if (d > hi) hi = d;
        }
        c_sign = sum / N_REPS; c_sign_lo = lo; c_sign_hi = hi;
    }
    {
        uint32_t r, d, sum = 0, lo = 0xFFFFFFFFu, hi = 0;
        for (r = 0; r < N_REPS; r++) {
            dwt_reset(); t0 = dwt_get();
            (void)wc_ecc_verify_hash(sig, siglen, digest, 32, &res, &key);
            d = dwt_get() - t0;
            sum += d; if (d < lo) lo = d; if (d > hi) hi = d;
        }
        c_vf = sum / N_REPS; c_vf_lo = lo; c_vf_hi = hi;
    }

    PRINTF("ECDSA-P256 prehash,sign,verify ms=%u,%u,%u  sig_bytes=%u  verify_result=%s\r\n",
           (unsigned)ms_from_cycles(c_hash), (unsigned)ms_from_cycles(c_sign),
           (unsigned)ms_from_cycles(c_vf), (unsigned)siglen, res ? "PASS" : "FAIL");
    PRINTF("ECDSA-P256 sign_ms mean/min/max=%u/%u/%u  verify_ms mean/min/max=%u/%u/%u  n=%u\r\n",
           (unsigned)ms_from_cycles(c_sign), (unsigned)ms_from_cycles(c_sign_lo),
           (unsigned)ms_from_cycles(c_sign_hi), (unsigned)ms_from_cycles(c_vf),
           (unsigned)ms_from_cycles(c_vf_lo), (unsigned)ms_from_cycles(c_vf_hi),
           (unsigned)N_REPS);
    PRINTF("ECDSA-P256 end_to_end_ms=%u\r\n",
           (unsigned)(ms_from_cycles(c_hash) + ms_from_cycles(c_vf)));
    PRINTF("ECDSA-P256 RAM: buffered=0 (streamed in %u B chunks) + digest 32 B + sig %u B\r\n",
           (unsigned)CHUNK_BYTES, (unsigned)siglen);
    wc_ecc_free(&key);
}

/* ---- ML-DSA (pure and pre-hash) ---- */
static void run_mldsa(int level, const char *name, int prehash, WC_RNG *rng)
{
    wc_MlDsaKey key;
    int     ret, res = 0;
    uint32_t siglen, pubLen = 0;
    uint32_t t0, c_sign, c_vf, c_pk, c_hash = 0;
    uint32_t c_sign_lo=0,c_sign_hi=0,c_vf_lo=0,c_vf_hi=0;
    int     rc;

    wc_MlDsaKey_Init(&key, NULL, INVALID_DEVID);
    rc = wc_MlDsaKey_SetParams(&key, (byte)level);
    if (rc != 0) { PRINTF("%s SetParams error %d\r\n", name, rc); return; }

    dwt_reset(); t0 = dwt_get();
    (void)wc_MlDsaKey_MakeKey(&key, rng);
    c_pk = dwt_get() - t0;

    (void)wc_MlDsaKey_GetSigLen(&key, (int *)&siglen);
    { int pl = 0; wc_MlDsaKey_GetPubLen(&key, &pl); pubLen = (uint32_t)pl; }

    if (prehash) {
        dwt_reset(); t0 = dwt_get();
        hash_stream_sha512(digest);
        c_hash = dwt_get() - t0;
        uint32_t r, d, sum, lo, hi;
        sum = 0; lo = 0xFFFFFFFFu; hi = 0;
        for (r = 0; r < N_REPS; r++) {
            siglen = sizeof(sig);
            dwt_reset(); t0 = dwt_get();
            ret = wc_MlDsaKey_SignCtxHash(&key, NULL, 0, sig, &siglen, digest, 64,
                                          WC_HASH_TYPE_SHA512, rng);
            d = dwt_get() - t0;
            if (ret != 0) { PRINTF("%s sign error %d\r\n", name, ret); return; }
            sum += d; if (d < lo) lo = d; if (d > hi) hi = d;
        }
        c_sign = sum / N_REPS; c_sign_lo = lo; c_sign_hi = hi;
        sum = 0; lo = 0xFFFFFFFFu; hi = 0;
        for (r = 0; r < N_REPS; r++) {
            dwt_reset(); t0 = dwt_get();
            (void)wc_MlDsaKey_VerifyCtxHash(&key, sig, siglen, NULL, 0, digest, 64,
                                            WC_HASH_TYPE_SHA512, &res);
            d = dwt_get() - t0;
            sum += d; if (d < lo) lo = d; if (d > hi) hi = d;
        }
        c_vf = sum / N_REPS; c_vf_lo = lo; c_vf_hi = hi;
    } else {
        uint32_t r, d, sum, lo, hi;
        sum = 0; lo = 0xFFFFFFFFu; hi = 0;
        for (r = 0; r < N_REPS; r++) {
            siglen = sizeof(sig);
            dwt_reset(); t0 = dwt_get();
            ret = wc_MlDsaKey_SignCtx(&key, NULL, 0, sig, &siglen, fw, FW_BYTES, rng);
            d = dwt_get() - t0;
            if (ret != 0) { PRINTF("%s sign error %d\r\n", name, ret); return; }
            sum += d; if (d < lo) lo = d; if (d > hi) hi = d;
        }
        c_sign = sum / N_REPS; c_sign_lo = lo; c_sign_hi = hi;
        sum = 0; lo = 0xFFFFFFFFu; hi = 0;
        for (r = 0; r < N_REPS; r++) {
            dwt_reset(); t0 = dwt_get();
            (void)wc_MlDsaKey_VerifyCtx(&key, sig, siglen, NULL, 0, fw, FW_BYTES, &res);
            d = dwt_get() - t0;
            sum += d; if (d < lo) lo = d; if (d > hi) hi = d;
        }
        c_vf = sum / N_REPS; c_vf_lo = lo; c_vf_hi = hi;
    }

    PRINTF("%s keygen,sign,prehash,verify ms=%u,%u,%u,%u  sig_bytes=%u  pk_bytes=%u  verify_result=%s\r\n",
           name, (unsigned)ms_from_cycles(c_pk), (unsigned)ms_from_cycles(c_sign),
           (unsigned)ms_from_cycles(c_hash), (unsigned)ms_from_cycles(c_vf),
           (unsigned)siglen, (unsigned)pubLen, res ? "PASS" : "FAIL");
    PRINTF("%s sign_ms mean/min/max=%u/%u/%u  verify_ms mean/min/max=%u/%u/%u  n=%u\r\n",
           name, (unsigned)ms_from_cycles(c_sign), (unsigned)ms_from_cycles(c_sign_lo),
           (unsigned)ms_from_cycles(c_sign_hi), (unsigned)ms_from_cycles(c_vf),
           (unsigned)ms_from_cycles(c_vf_lo), (unsigned)ms_from_cycles(c_vf_hi),
           (unsigned)N_REPS);
    PRINTF("%s end_to_end_ms=%u\r\n", name,
           (unsigned)(ms_from_cycles(c_hash) + ms_from_cycles(c_vf)));
    if (prehash)
        PRINTF("%s RAM: buffered=0 (streamed in %u B chunks) + digest 64 B + sig %u B + pk %u B\r\n",
               name, (unsigned)CHUNK_BYTES, (unsigned)siglen, (unsigned)pubLen);
    else
        PRINTF("%s RAM: buffered=%u B (whole payload addressable) + sig %u B + pk %u B\r\n",
               name, (unsigned)FW_BYTES, (unsigned)siglen, (unsigned)pubLen);
    wc_MlDsaKey_Free(&key);
}

int main(void)
{
    WC_RNG rng;
    int    rc;

    BOARD_InitHardware();
    dwt_init();

    PRINTF("\r\n=== Task 3A: 128 KB firmware signature verification ===\r\n");
    PRINTF("plat,mcxn947,cpu_hz=%u,fw_bytes=%u\r\n", (unsigned)CPU_HZ, (unsigned)FW_BYTES);

    rc = wc_InitRng(&rng);
    PRINTF("wc_InitRng rc=%d\r\n", rc);

    fill_fw();

    /* Streaming path RAM: the hash contexts, measured not estimated. */
    PRINTF("streaming ctx bytes: SHA-256=%u SHA-512=%u chunk=%u\r\n",
           (unsigned)sizeof(wc_Sha256), (unsigned)sizeof(wc_Sha512),
           (unsigned)CHUNK_BYTES);

    run_ecdsa(&rng);
    run_mldsa(2, "ML-DSA-44-pure",  0, &rng);
    run_mldsa(3, "ML-DSA-65-pure",  0, &rng);
    run_mldsa(3, "HashML-DSA-65",   1, &rng);

    PRINTF("BENCH_COMPLETE\r\n");
    for (;;) { }
}
