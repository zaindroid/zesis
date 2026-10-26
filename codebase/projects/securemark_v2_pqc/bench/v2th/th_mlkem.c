/*
 * th_mlkem.c — ML-KEM primitive shim for the SecureMark-V2 self-hosted harness,
 * backed by native wolfSSL (wc_mlkem.c) on bare-metal Cortex-M33.
 *
 * Status reporting follows the dual scheme agreed for the PQC suites:
 *   - functional self-check: Decapsulate(Encapsulate(pk)) recovers ss exactly
 *   - synthesized regression CRC over the deterministic output buffers
 * There is no EEMBC golden CRC for a PQC profile, so this shim never claims
 * one. Only the primitive calls are inside the measured window; buffer copies
 * and the round-trip comparison sit outside it.
 */
#include <wolfssl/wolfcrypt/wc_mlkem.h>
#include <wolfssl/wolfcrypt/random.h>
#include <wolfssl/wolfcrypt/error-crypt.h>

#include "th_pqc.h"

#define HEAP_HINT   NULL
#define DEVID       INVALID_DEVID

typedef struct {
    MlKemKey key;
    int      type;
    word32   pkLen, skLen, ctLen, ssLen;
} mlkem_ctx_t;

ee_status_t
th_mlkem_create(void **pp_context, ee_mlkem_size_t size)
{
    mlkem_ctx_t *ctx;
    int rc;

    ctx = (mlkem_ctx_t *)th_malloc(sizeof(mlkem_ctx_t));
    if (ctx == NULL) {
        th_printf("e-[th_mlkem_create malloc]\r\n");
        return EE_STATUS_ERROR;
    }

    switch (size) {
        case EE_MLKEM_512:  ctx->type = WC_ML_KEM_512;  break;
        case EE_MLKEM_768:  ctx->type = WC_ML_KEM_768;  break;
        case EE_MLKEM_1024: ctx->type = WC_ML_KEM_1024; break;
        default:
            th_printf("e-[th_mlkem_create size]\r\n");
            th_free(ctx);
            return EE_STATUS_ERROR;
    }

    rc = wc_MlKemKey_Init(&ctx->key, ctx->type, HEAP_HINT, DEVID);
    if (rc != 0) { th_printf("e-[wc_MlKemKey_Init %d]\r\n", rc); th_free(ctx); return EE_STATUS_ERROR; }

    wc_MlKemKey_PublicKeySize(&ctx->key, &ctx->pkLen);
    wc_MlKemKey_PrivateKeySize(&ctx->key, &ctx->skLen);
    wc_MlKemKey_CipherTextSize(&ctx->key, &ctx->ctLen);
    wc_MlKemKey_SharedSecretSize(&ctx->key, &ctx->ssLen);

    *pp_context = (void *)ctx;
    return EE_STATUS_OK;
}

ee_status_t
th_mlkem_init(void *p_context)
{
    (void)p_context;
    return EE_STATUS_OK;   /* key generated per-iteration in keypair() */
}

ee_status_t
th_mlkem_keypair(void *p_context, WC_RNG *rng,
                 uint8_t *pk, uint32_t *pklen,
                 uint8_t *sk, uint32_t *sklen)
{
    mlkem_ctx_t *ctx = (mlkem_ctx_t *)p_context;
    int rc;

    rc = wc_MlKemKey_MakeKey(&ctx->key, rng);
    if (rc != 0) { th_printf("e-[MakeKey %d]\r\n", rc); return EE_STATUS_ERROR; }

    rc = wc_MlKemKey_EncodePublicKey(&ctx->key, pk, ctx->pkLen);
    if (rc != 0) return EE_STATUS_ERROR;
    rc = wc_MlKemKey_EncodePrivateKey(&ctx->key, sk, ctx->skLen);
    if (rc != 0) return EE_STATUS_ERROR;

    *pklen = ctx->pkLen;
    *sklen = ctx->skLen;
    return EE_STATUS_OK;
}

ee_status_t
th_mlkem_encapsulate(void *p_context, WC_RNG *rng,
                     uint8_t *ct, uint32_t *ctlen,
                     uint8_t *ss, uint32_t *sslen)
{
    mlkem_ctx_t *ctx = (mlkem_ctx_t *)p_context;
    int rc;

    rc = wc_MlKemKey_Encapsulate(&ctx->key, ct, ss, rng);
    if (rc != 0) { th_printf("e-[Encapsulate %d]\r\n", rc); return EE_STATUS_ERROR; }

    *ctlen = ctx->ctLen;
    *sslen = ctx->ssLen;
    return EE_STATUS_OK;
}

ee_status_t
th_mlkem_decapsulate(void *p_context,
                     uint8_t *ss, uint32_t *sslen,
                     const uint8_t *ct, uint32_t ctlen)
{
    mlkem_ctx_t *ctx = (mlkem_ctx_t *)p_context;
    int rc;

    rc = wc_MlKemKey_Decapsulate(&ctx->key, ss, ct, ctlen);
    if (rc != 0) { th_printf("e-[Decapsulate %d]\r\n", rc); return EE_STATUS_ERROR; }

    *sslen = ctx->ssLen;
    return EE_STATUS_OK;
}

ee_status_t
th_mlkem_destroy(void *p_context)
{
    mlkem_ctx_t *ctx = (mlkem_ctx_t *)p_context;

    if (ctx == NULL) return EE_STATUS_ERROR;
    wc_MlKemKey_Free(&ctx->key);
    th_free(ctx);
    return EE_STATUS_OK;
}
