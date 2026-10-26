/*
 * th_mldsa.c — ML-DSA primitive shim for the SecureMark-V2 self-hosted harness,
 * backed by native wolfSSL (wc_mldsa.c) on bare-metal Cortex-M33.
 *
 * Two entry paths are kept explicit and separate:
 *   - th_mldsa_sign / th_mldsa_verify          : pure ML-DSA, ctx passed
 *                                                through (NULL/0 == FIPS 204
 *                                                section 5.2 default)
 *   - th_mldsa_sign_hash / _verify_hash        : HashML-DSA pre-hash path, the
 *                                                caller supplies the digest
 *
 * Only the primitive call is inside the measured window; buffer handling and
 * the round-trip verification sit outside it.
 */
#include <wolfssl/wolfcrypt/wc_mldsa.h>
#include <wolfssl/wolfcrypt/random.h>
#include <wolfssl/wolfcrypt/error-crypt.h>
#include <wolfssl/wolfcrypt/hash.h>

#include "th_pqc.h"

#define HEAP_HINT   NULL
#define DEVID       INVALID_DEVID

typedef struct {
    wc_MlDsaKey key;
    byte        level;
    int         pkLen, skLen, sigLen;
} mldsa_ctx_t;

ee_status_t
th_mldsa_create(void **pp_context, ee_mldsa_size_t size)
{
    mldsa_ctx_t *ctx;
    int rc;

    ctx = (mldsa_ctx_t *)th_malloc(sizeof(mldsa_ctx_t));
    if (ctx == NULL) {
        th_printf("e-[th_mldsa_create malloc]\r\n");
        return EE_STATUS_ERROR;
    }

    switch (size) {
        case EE_MLDSA_44: ctx->level = WC_ML_DSA_44; break;
        case EE_MLDSA_65: ctx->level = WC_ML_DSA_65; break;
        case EE_MLDSA_87: ctx->level = WC_ML_DSA_87; break;
        default:
            th_printf("e-[th_mldsa_create size]\r\n");
            th_free(ctx);
            return EE_STATUS_ERROR;
    }

    rc = wc_MlDsaKey_Init(&ctx->key, HEAP_HINT, DEVID);
    if (rc != 0) { th_printf("e-[wc_MlDsaKey_Init %d]\r\n", rc); th_free(ctx); return EE_STATUS_ERROR; }

    rc = wc_MlDsaKey_SetParams(&ctx->key, ctx->level);
    if (rc != 0) { th_printf("e-[SetParams %d]\r\n", rc); wc_MlDsaKey_Free(&ctx->key); th_free(ctx); return EE_STATUS_ERROR; }

    wc_MlDsaKey_GetPubLen(&ctx->key, &ctx->pkLen);
    wc_MlDsaKey_GetPrivLen(&ctx->key, &ctx->skLen);
    wc_MlDsaKey_GetSigLen(&ctx->key, &ctx->sigLen);

    *pp_context = (void *)ctx;
    return EE_STATUS_OK;
}

ee_status_t
th_mldsa_init(void *p_context)
{
    (void)p_context;
    return EE_STATUS_OK;
}

ee_status_t
th_mldsa_keypair(void *p_context, WC_RNG *rng,
                 uint8_t *pk, uint32_t *pklen,
                 uint8_t *sk, uint32_t *sklen)
{
    mldsa_ctx_t *ctx = (mldsa_ctx_t *)p_context;
    int rc;

    rc = wc_MlDsaKey_MakeKey(&ctx->key, rng);
    if (rc != 0) { th_printf("e-[MlDsaKey_MakeKey %d]\r\n", rc); return EE_STATUS_ERROR; }

    {   /* Export*Raw takes word32*; Get*Len takes int* (see wc_mldsa.h) */
        word32 olen = (word32)ctx->pkLen;
        rc = wc_MlDsaKey_ExportPubRaw(&ctx->key, pk, &olen);
        if (rc != 0) return EE_STATUS_ERROR;
        ctx->pkLen = (int)olen;
    }
    {
        word32 olen = (word32)ctx->skLen;
        rc = wc_MlDsaKey_ExportPrivRaw(&ctx->key, sk, &olen);
        if (rc != 0) return EE_STATUS_ERROR;
        ctx->skLen = (int)olen;
    }

    *pklen = (uint32_t)ctx->pkLen;
    *sklen = (uint32_t)ctx->skLen;
    return EE_STATUS_OK;
}

ee_status_t
th_mldsa_sign(void *p_context, WC_RNG *rng,
              const uint8_t *ctx, uint8_t ctxLen,
              const uint8_t *msg, uint32_t msgLen,
              uint8_t *sig, uint32_t *siglen)
{
    mldsa_ctx_t *c = (mldsa_ctx_t *)p_context;
    word32 sl = (word32)c->sigLen;
    int rc;

    rc = wc_MlDsaKey_SignCtx(&c->key, ctx, ctxLen, sig, &sl, msg, msgLen, rng);
    if (rc != 0) { th_printf("e-[SignCtx %d]\r\n", rc); return EE_STATUS_ERROR; }

    *siglen = sl;
    return EE_STATUS_OK;
}

ee_status_t
th_mldsa_verify(void *p_context,
                const uint8_t *ctx, uint8_t ctxLen,
                const uint8_t *msg, uint32_t msgLen,
                const uint8_t *sig, uint32_t siglen,
                int *result)
{
    mldsa_ctx_t *c = (mldsa_ctx_t *)p_context;
    int res = 0;
    int rc;

    rc = wc_MlDsaKey_VerifyCtx(&c->key, sig, siglen, ctx, ctxLen, msg, msgLen, &res);
    if (rc != 0) { th_printf("e-[VerifyCtx %d]\r\n", rc); return EE_STATUS_ERROR; }

    *result = res;   /* 1 == valid */
    return EE_STATUS_OK;
}

ee_status_t
th_mldsa_sign_hash(void *p_context, WC_RNG *rng,
                   const uint8_t *ctx, uint8_t ctxLen,
                   const uint8_t *hash, uint32_t hashLen,
                   uint8_t *sig, uint32_t *siglen)
{
    mldsa_ctx_t *c = (mldsa_ctx_t *)p_context;
    word32 sl = (word32)c->sigLen;
    int rc;

    rc = wc_MlDsaKey_SignCtxHash(&c->key, ctx, ctxLen, sig, &sl, hash, hashLen,
                                 WC_HASH_TYPE_SHA512, rng);
    if (rc != 0) { th_printf("e-[SignCtxHash %d]\r\n", rc); return EE_STATUS_ERROR; }

    *siglen = sl;
    return EE_STATUS_OK;
}

ee_status_t
th_mldsa_verify_hash(void *p_context,
                     const uint8_t *ctx, uint8_t ctxLen,
                     const uint8_t *hash, uint32_t hashLen,
                     const uint8_t *sig, uint32_t siglen,
                     int *result)
{
    mldsa_ctx_t *c = (mldsa_ctx_t *)p_context;
    int res = 0;
    int rc;

    rc = wc_MlDsaKey_VerifyCtxHash(&c->key, sig, siglen, ctx, ctxLen,
                                   hash, hashLen, WC_HASH_TYPE_SHA512, &res);
    if (rc != 0) { th_printf("e-[VerifyCtxHash %d]\r\n", rc); return EE_STATUS_ERROR; }

    *result = res;
    return EE_STATUS_OK;
}

ee_status_t
th_mldsa_destroy(void *p_context)
{
    mldsa_ctx_t *ctx = (mldsa_ctx_t *)p_context;

    if (ctx == NULL) return EE_STATUS_ERROR;
    wc_MlDsaKey_Free(&ctx->key);
    th_free(ctx);
    return EE_STATUS_OK;
}
