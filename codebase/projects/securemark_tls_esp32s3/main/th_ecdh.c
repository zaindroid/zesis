/*
 * SecureMark-TLS th_ecdh implementation for FRDM-MCXN947
 * Backed by mbedTLS 3.6 (public API only: ecp_point_read/write_binary).
 */
#include "ee_ecdh.h"
#include "mbedtls/ecdh.h"
#include "mbedtls/ecp.h"
#include "mbedtls/bignum.h"
#include "mbedtls/platform.h"
extern int mbedtls_rng_for_ecp(void *ctx, unsigned char *buf, size_t len);
#include <stdlib.h>
#include <string.h>

typedef struct {
    mbedtls_ecp_group grp;
    mbedtls_mpi d;              /* our private scalar */
    mbedtls_ecp_point Qp;       /* peer public point  */
} ecdh_ctx_t;

ee_status_t
th_ecdh_create(void **p_context)
{
    ecdh_ctx_t *c = (ecdh_ctx_t *)malloc(sizeof(ecdh_ctx_t));
    if (!c) return EE_STATUS_ERROR;
    mbedtls_ecp_group_init(&c->grp);
    mbedtls_mpi_init(&c->d);
    mbedtls_ecp_point_init(&c->Qp);
    *p_context = c;
    return EE_STATUS_OK;
}

ee_status_t
th_ecdh_init(void *p_context, ecdh_group_t group,
             unsigned char *p_private, unsigned int prilen,
             unsigned char *p_public, unsigned int publen)
{
    (void)group;
    ecdh_ctx_t *c = (ecdh_ctx_t *)p_context;
    int ret;

    ret = mbedtls_ecp_group_load(&c->grp, MBEDTLS_ECP_DP_SECP256R1);
    if (ret != 0) return EE_STATUS_ERROR;

    ret = mbedtls_mpi_read_binary(&c->d, p_private, prilen);
    if (ret != 0) return EE_STATUS_ERROR;

    /* Peer public point: EEMBC gives raw X || Y (64 bytes, no 0x04 prefix).
     * mbedTLS needs the SEC1 format (0x04 || X || Y, 65 bytes). */
    unsigned char pt_buf[65];
    pt_buf[0] = 0x04;
    memcpy(&pt_buf[1], p_public, publen);
    ret = mbedtls_ecp_point_read_binary(&c->grp, &c->Qp,
                                        pt_buf, publen + 1);
    if (ret != 0) return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

ee_status_t
th_ecdh_calc_secret(void *p_context, unsigned char *p_secret, unsigned int slen)
{
    ecdh_ctx_t *c = (ecdh_ctx_t *)p_context;
    mbedtls_mpi z;
    int ret;

    mbedtls_mpi_init(&z);
    ret = mbedtls_ecdh_compute_shared(&c->grp, &z, &c->Qp, &c->d,
                                      mbedtls_rng_for_ecp, NULL);
    if (ret != 0) { mbedtls_mpi_free(&z); return EE_STATUS_ERROR; }

    ret = mbedtls_mpi_write_binary(&z, p_secret, slen);
    mbedtls_mpi_free(&z);
    if (ret != 0) return EE_STATUS_ERROR;
    return EE_STATUS_OK;
}

void
th_ecdh_destroy(void *p_context)
{
    if (p_context) {
        ecdh_ctx_t *c = (ecdh_ctx_t *)p_context;
        mbedtls_ecp_group_free(&c->grp);
        mbedtls_mpi_free(&c->d);
        mbedtls_ecp_point_free(&c->Qp);
        free(c);
    }
}
