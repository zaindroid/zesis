/*
 * th_pqc.h — interface for the post-quantum primitive shims (ML-KEM, ML-DSA).
 *
 * Mirrors the naming of the other EEMBC th_* hooks so the PQC suites can be
 * registered the same way. Kept separate from the classical th_*.h files.
 *
 * The RNG is passed in from the driver (deterministic seeding for CRC-stable
 * regression runs) rather than created per-primitive.
 */
#ifndef __TH_PQC_H
#define __TH_PQC_H

#include <stdint.h>

#include <wolfssl/wolfcrypt/random.h>

#include "th_util.h"      /* ee_status_t, th_malloc/th_free/th_printf via harness */

typedef enum {
    EE_MLKEM_512  = 512,
    EE_MLKEM_768  = 768,
    EE_MLKEM_1024 = 1024
} ee_mlkem_size_t;

typedef enum {
    EE_MLDSA_44 = 44,
    EE_MLDSA_65 = 65,
    EE_MLDSA_87 = 87
} ee_mldsa_size_t;

/* ML-KEM */
ee_status_t th_mlkem_create(void **pp_context, ee_mlkem_size_t size);
ee_status_t th_mlkem_init(void *p_context);
ee_status_t th_mlkem_keypair(void *p_context, WC_RNG *rng,
                             uint8_t *pk, uint32_t *pklen,
                             uint8_t *sk, uint32_t *sklen);
ee_status_t th_mlkem_encapsulate(void *p_context, WC_RNG *rng,
                                 uint8_t *ct, uint32_t *ctlen,
                                 uint8_t *ss, uint32_t *sslen);
ee_status_t th_mlkem_decapsulate(void *p_context,
                                 uint8_t *ss, uint32_t *sslen,
                                 const uint8_t *ct, uint32_t ctlen);
ee_status_t th_mlkem_destroy(void *p_context);

/* ML-DSA (pure and pre-hash share one context; the caller picks the entry) */
ee_status_t th_mldsa_create(void **pp_context, ee_mldsa_size_t size);
ee_status_t th_mldsa_init(void *p_context);
ee_status_t th_mldsa_keypair(void *p_context, WC_RNG *rng,
                             uint8_t *pk, uint32_t *pklen,
                             uint8_t *sk, uint32_t *sklen);

/* pure ML-DSA, FIPS 204 section 5.2: ctx = NULL, ctxLen = 0 by default */
ee_status_t th_mldsa_sign(void *p_context, WC_RNG *rng,
                          const uint8_t *ctx, uint8_t ctxLen,
                          const uint8_t *msg, uint32_t msgLen,
                          uint8_t *sig, uint32_t *siglen);
ee_status_t th_mldsa_verify(void *p_context,
                            const uint8_t *ctx, uint8_t ctxLen,
                            const uint8_t *msg, uint32_t msgLen,
                            const uint8_t *sig, uint32_t siglen,
                            int *result);

/* HashML-DSA (pre-hash path): the caller supplies the message digest */
ee_status_t th_mldsa_sign_hash(void *p_context, WC_RNG *rng,
                               const uint8_t *ctx, uint8_t ctxLen,
                               const uint8_t *hash, uint32_t hashLen,
                               uint8_t *sig, uint32_t *siglen);
ee_status_t th_mldsa_verify_hash(void *p_context,
                                 const uint8_t *ctx, uint8_t ctxLen,
                                 const uint8_t *hash, uint32_t hashLen,
                                 const uint8_t *sig, uint32_t siglen,
                                 int *result);
ee_status_t th_mldsa_destroy(void *p_context);

#endif /* __TH_PQC_H */
