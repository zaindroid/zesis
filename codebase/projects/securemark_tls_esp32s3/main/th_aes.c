/*
 * SecureMark-TLS th_aes implementation for FRDM-MCXN947
 * Backed by mbedTLS (AES-128 ECB + CCM).
 */
#include "ee_aes.h"
#include "mbedtls/aes.h"
#include "mbedtls/ccm.h"
#include <stdlib.h>
#include <string.h>

typedef struct {
    mbedtls_aes_context aes;
    aes_cipher_mode_t mode;
} aes_ctx_t;

typedef struct {
    mbedtls_ccm_context ccm;
    aes_cipher_mode_t mode;
} ccm_ctx_t;

ee_status_t
th_aes128_create(void **p_context, aes_cipher_mode_t mode)
{
    if (mode == AES_ECB) {
        aes_ctx_t *c = (aes_ctx_t *)malloc(sizeof(aes_ctx_t));
        if (!c) return EE_STATUS_ERROR;
        mbedtls_aes_init(&c->aes);
        c->mode = mode;
        *p_context = c;
    } else {
        ccm_ctx_t *c = (ccm_ctx_t *)malloc(sizeof(ccm_ctx_t));
        if (!c) return EE_STATUS_ERROR;
        mbedtls_ccm_init(&c->ccm);
        c->mode = mode;
        *p_context = c;
    }
    return EE_STATUS_OK;
}

ee_status_t
th_aes128_init(void *p_context, const unsigned char *p_key,
               unsigned int keylen, unsigned int rounds,
               aes_function_t func, aes_cipher_mode_t mode)
{
    (void)rounds; (void)func;
    if (mode == AES_ECB) {
        aes_ctx_t *c = (aes_ctx_t *)p_context;
        if (mbedtls_aes_setkey_enc(&c->aes, p_key, keylen * 8) != 0)
            return EE_STATUS_ERROR;
    } else {
        ccm_ctx_t *c = (ccm_ctx_t *)p_context;
        if (mbedtls_ccm_setkey(&c->ccm, MBEDTLS_CIPHER_ID_AES,
                               p_key, keylen * 8) != 0)
            return EE_STATUS_ERROR;
    }
    return EE_STATUS_OK;
}

void
th_aes128_deinit(void *context, aes_cipher_mode_t mode)
{
    if (mode == AES_ECB) {
        aes_ctx_t *c = (aes_ctx_t *)context;
        mbedtls_aes_free(&c->aes);
    } else {
        ccm_ctx_t *c = (ccm_ctx_t *)context;
        mbedtls_ccm_free(&c->ccm);
    }
}

ee_status_t
th_aes128_ecb_encrypt(void *p_context, const unsigned char *p_pt,
                      unsigned char *p_ct)
{
    aes_ctx_t *c = (aes_ctx_t *)p_context;
    if (mbedtls_aes_crypt_ecb(&c->aes, MBEDTLS_AES_ENCRYPT,
                              p_pt, p_ct) != 0)
        return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

ee_status_t
th_aes128_ecb_decrypt(void *p_context, const unsigned char *p_ct,
                      unsigned char *p_pt)
{
    aes_ctx_t *c = (aes_ctx_t *)p_context;
    if (mbedtls_aes_crypt_ecb(&c->aes, MBEDTLS_AES_DECRYPT,
                              p_ct, p_pt) != 0)
        return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

ee_status_t
th_aes128_ccm_encrypt(void *p_context, const unsigned char *p_pt,
                      unsigned int ptlen, unsigned char *p_ct,
                      unsigned char *p_tag, unsigned int taglen,
                      unsigned char *p_iv, unsigned int ivlen)
{
    ccm_ctx_t *c = (ccm_ctx_t *)p_context;
    if (mbedtls_ccm_encrypt_and_tag(&c->ccm, ptlen,
                                    p_iv, ivlen, NULL, 0,
                                    p_pt, p_ct, p_tag, taglen) != 0)
        return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

ee_status_t
th_aes128_ccm_decrypt(void *p_context, const unsigned char *p_ct,
                      unsigned int ctlen, unsigned char *p_pt,
                      unsigned char *p_tag, unsigned int taglen,
                      unsigned char *p_iv, unsigned int ivlen)
{
    ccm_ctx_t *c = (ccm_ctx_t *)p_context;
    int r = mbedtls_ccm_auth_decrypt(&c->ccm, ctlen,
                                     p_iv, ivlen, NULL, 0,
                                     p_ct, p_pt, p_tag, taglen);
    if (r != 0)
        return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

void
th_aes128_destroy(void *p_context, aes_cipher_mode_t mode)
{
    if (p_context) {
        th_aes128_deinit(p_context, mode);
        free(p_context);
    }
}
