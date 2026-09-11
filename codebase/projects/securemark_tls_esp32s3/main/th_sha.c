/*
 * SecureMark-TLS th_sha implementation for FRDM-MCXN947
 * Backed by mbedTLS (SHA-256).
 */
#include "ee_sha.h"
#include "mbedtls/sha256.h"
#include <stdlib.h>

typedef struct {
    mbedtls_sha256_context ctx;
} sha_ctx_t;

ee_status_t
th_sha256_create(void **p_context)
{
    sha_ctx_t *c = (sha_ctx_t *)malloc(sizeof(sha_ctx_t));
    if (!c) return EE_STATUS_ERROR;
    mbedtls_sha256_init(&c->ctx);
    *p_context = c;
    return EE_STATUS_OK;
}

ee_status_t
th_sha256_init(void *p_context)
{
    sha_ctx_t *c = (sha_ctx_t *)p_context;
    if (mbedtls_sha256_starts(&c->ctx, 0) != 0) /* 0 = SHA-256, not SHA-224 */
        return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

ee_status_t
th_sha256_process(void *p_context, const unsigned char *p_in, unsigned int len)
{
    sha_ctx_t *c = (sha_ctx_t *)p_context;
    if (mbedtls_sha256_update(&c->ctx, p_in, len) != 0)
        return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

ee_status_t
th_sha256_done(void *p_context, unsigned char *p_result)
{
    sha_ctx_t *c = (sha_ctx_t *)p_context;
    if (mbedtls_sha256_finish(&c->ctx, p_result) != 0)
        return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

void
th_sha256_destroy(void *p_context)
{
    if (p_context) {
        sha_ctx_t *c = (sha_ctx_t *)p_context;
        mbedtls_sha256_free(&c->ctx);
        free(c);
    }
}
