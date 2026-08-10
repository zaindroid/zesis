/*
 * Compact AES-128-GCM for the SPLIT_INFERENCE privacy-layer overhead
 * measurement. Self-contained (no SDK crypto dependency), table-free
 * (small code), adequate for measuring the latency/energy profile of the
 * hybrid PQC privacy layer on the MCXN947.
 *
 * This is NOT a production AES-GCM: it is a compact reference used to
 * measure the *cost* of the privacy layer (the exact cipher matters less
 * than the latency/energy profile, which is what Option B measures).
 * AES-128: 10 rounds, T-table-free (S-box lookup), GCM via GF(2^128) mul.
 *
 * API: aes_gcm_encrypt(key, iv12, aad, aad_len, pt, pt_len, ct, tag)
 *      aes_gcm_decrypt(key, iv12, aad, aad_len, ct, ct_len, pt, tag)
 * Returns 0 on success (tag matches).
 */
#ifndef SPLIT_AES_GCM_H
#define SPLIT_AES_GCM_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int aes_gcm_encrypt(const uint8_t key[16], const uint8_t iv[12],
                    const uint8_t *aad, size_t aad_len,
                    const uint8_t *pt, size_t pt_len,
                    uint8_t *ct, uint8_t tag[16]);

int aes_gcm_decrypt(const uint8_t key[16], const uint8_t iv[12],
                    const uint8_t *aad, size_t aad_len,
                    const uint8_t *ct, size_t ct_len,
                    uint8_t *pt, const uint8_t tag[16]);

#ifdef __cplusplus
}
#endif

#endif
