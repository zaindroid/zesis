/*
 * SecureMark-TLS th_ecdsa implementation for FRDM-MCXN947
 * Backed by mbedTLS 3.6 (ECDSA P-256, deterministic RFC 6979).
 */
#include "ee_ecdsa.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/ecp.h"
#include "mbedtls/bignum.h"
extern int mbedtls_rng_for_ecp(void *ctx, unsigned char *buf, size_t len);
#include "mbedtls/md.h"
#include "mbedtls/ctr_drbg.h"
#include <stdlib.h>

typedef struct {
    mbedtls_ecp_group grp;
    mbedtls_mpi d;       /* private scalar (32 bytes) */
    mbedtls_ecp_point Q; /* public point, derived */
    int have_Q;
} ecdsa_ctx_t;

ee_status_t
th_ecdsa_create(void **p_context)
{
    ecdsa_ctx_t *c = (ecdsa_ctx_t *)malloc(sizeof(ecdsa_ctx_t));
    if (!c) return EE_STATUS_ERROR;
    mbedtls_ecp_group_init(&c->grp);
    mbedtls_mpi_init(&c->d);
    mbedtls_ecp_point_init(&c->Q);
    c->have_Q = 0;
    *p_context = c;
    return EE_STATUS_OK;
}

ee_status_t
th_ecdsa_init(void *p_context, ecdh_group_t group,
              unsigned char *p_private, size_t plen)
{
    (void)group;
    ecdsa_ctx_t *c = (ecdsa_ctx_t *)p_context;
    int ret;

    ret = mbedtls_ecp_group_load(&c->grp, MBEDTLS_ECP_DP_SECP256R1);
    if (ret != 0) return EE_STATUS_ERROR;

    ret = mbedtls_mpi_read_binary(&c->d, p_private, plen);
    if (ret != 0) return EE_STATUS_ERROR;

    ret = mbedtls_ecp_mul(&c->grp, &c->Q, &c->d, &c->grp.G,
                          mbedtls_rng_for_ecp, NULL);
    if (ret != 0) return EE_STATUS_ERROR;
    c->have_Q = 1;
    return EE_STATUS_OK;
}

ee_status_t
th_ecdsa_sign(void *p_context, unsigned char *p_hash, unsigned int hlen,
              unsigned char *p_sig, unsigned int *p_slen)
{
    ecdsa_ctx_t *c = (ecdsa_ctx_t *)p_context;
    mbedtls_mpi r, s;
    int ret;

    mbedtls_mpi_init(&r); mbedtls_mpi_init(&s);

    ret = mbedtls_ecdsa_sign_det_ext(&c->grp, &r, &s,
                                     &c->d, p_hash, hlen,
                                     MBEDTLS_MD_SHA256,
                                     mbedtls_rng_for_ecp, NULL); /* blinding; sig stays RFC 6979 deterministic */
    if (ret != 0) { mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); return EE_STATUS_ERROR; }

    /* EEMBC expects the signature ASN.1 DER-encoded (70-72 bytes), not raw
     * r||s (64 bytes) -- the reference CRC is over the DER bytes. */
    {
        unsigned char rb[32], sb[32], rbe[33], sbe[33];
        size_t rlen, slen_;
        mbedtls_mpi_write_binary(&r, rb, 32);
        mbedtls_mpi_write_binary(&s, sb, 32);
        /* strip leading zeros, keep at least 1 byte */
        rlen = 32; while (rlen > 1 && rb[32 - rlen] == 0) rlen--;
        slen_ = 32; while (slen_ > 1 && sb[32 - slen_] == 0) slen_--;
        /* prepend 0x00 if high bit set (keep positive INTEGER) */
        if (rb[32 - rlen] & 0x80) { rbe[0] = 0; memcpy(rbe + 1, rb + 32 - rlen, rlen); rlen++; }
        else memcpy(rbe, rb + 32 - rlen, rlen);
        if (sb[32 - slen_] & 0x80) { sbe[0] = 0; memcpy(sbe + 1, sb + 32 - slen_, slen_); slen_++; }
        else memcpy(sbe, sb + 32 - slen_, slen_);
        /* DER: SEQUENCE { INTEGER r, INTEGER s } */
        p_sig[0] = 0x30;
        p_sig[1] = (unsigned char)(2 + rlen + 2 + slen_);
        p_sig[2] = 0x02; p_sig[3] = (unsigned char)rlen;
        memcpy(p_sig + 4, rbe, rlen);
        p_sig[4 + rlen] = 0x02; p_sig[5 + rlen] = (unsigned char)slen_;
        memcpy(p_sig + 6 + rlen, sbe, slen_);
        *p_slen = 6 + rlen + slen_;
    }

    mbedtls_mpi_free(&r); mbedtls_mpi_free(&s);
    return EE_STATUS_OK;
}

ee_status_t
th_ecdsa_verify(void *p_context, unsigned char *p_hash, unsigned int hlen,
                unsigned char *p_sig, unsigned int slen)
{
    ecdsa_ctx_t *c = (ecdsa_ctx_t *)p_context;
    mbedtls_mpi r, s;
    int ret;

    if (!c->have_Q) return EE_STATUS_ERROR;

    mbedtls_mpi_init(&r); mbedtls_mpi_init(&s);
    /* Parse ASN.1 DER: SEQUENCE { INTEGER r, INTEGER s } */
    if (slen < 8 || p_sig[0] != 0x30) {
        mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); return EE_STATUS_ERROR;
    }
    {
        size_t off = 2;
        if (p_sig[1] != (slen - 2)) {
            mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); return EE_STATUS_ERROR;
        }
        if (p_sig[off] != 0x02) { mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); return EE_STATUS_ERROR; }
        size_t rl = p_sig[off + 1]; off += 2;
        if (off + rl > slen) { mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); return EE_STATUS_ERROR; }
        mbedtls_mpi_read_binary(&r, p_sig + off, rl); off += rl;
        if (off + 2 > slen || p_sig[off] != 0x02) { mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); return EE_STATUS_ERROR; }
        size_t sl2 = p_sig[off + 1]; off += 2;
        if (off + sl2 > slen) { mbedtls_mpi_free(&r); mbedtls_mpi_free(&s); return EE_STATUS_ERROR; }
        mbedtls_mpi_read_binary(&s, p_sig + off, sl2);
    }

    ret = mbedtls_ecdsa_verify(&c->grp, p_hash, hlen, &c->Q, &r, &s);
    mbedtls_mpi_free(&r); mbedtls_mpi_free(&s);
    if (ret != 0) return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

void
th_ecdsa_destroy(void *p_context)
{
    if (p_context) {
        ecdsa_ctx_t *c = (ecdsa_ctx_t *)p_context;
        mbedtls_ecp_group_free(&c->grp);
        mbedtls_mpi_free(&c->d);
        mbedtls_ecp_point_free(&c->Q);
        free(c);
    }
}
