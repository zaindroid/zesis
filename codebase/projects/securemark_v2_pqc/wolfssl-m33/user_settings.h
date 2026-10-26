/* user_settings.h — wolfSSL for Cortex-M33 bare metal (MCXN947), crypto-only.
 *
 * Native ML-KEM (512/768/1024) and ML-DSA (44/65/87) for the SecureMark-V2
 * self-hosted harness (wolfssl_th_api). Crypto only: no TLS stack, no
 * filesystem, no threads.
 *
 * PQC gates per wolfssl/wolfcrypt/settings.h:
 *   WOLFSSL_HAVE_MLKEM  -> wc_mlkem.c / wc_mlkem_poly.c
 *   WOLFSSL_HAVE_MLDSA  -> wc_mldsa.c (legacy spelling HAVE_DILITHIUM)
 *   WOLFSSL_SHAKE256    -> Keccak sampling
 */
#ifndef WOLFSSL_USER_SETTINGS_H
#define WOLFSSL_USER_SETTINGS_H

/* ---- platform ---- */
#define NO_FILESYSTEM
#define NO_THREADS
/* Assembly/SP variant: NOT available on this target. wolfSSL gates its
   Cortex-M SP assembly on WOLFSSL_ARM_ARCH_7M (from __ARM_ARCH_7M__); the
   MCXN947 is ARMv8-M (Cortex-M33), so the gate is closed and there is no
   ARMv8-M path. Verified: enabling asm yields a byte-identical library. */
#define WOLFSSL_NO_ASM
#define WOLFSSL_SMALL_STACK
#define WOLFSSL_NO_SOCK
#define WOLFCRYPT_ONLY   /* crypto-only build (correct spelling; disables TLS layer) */
#define NO_WRITEV          /* ssl.h otherwise includes <sys/uio.h> */
#define NO_ASN_TIME
#define WOLFSSL_NO_TLS12

/* ---- symmetric: SecureMark-V2 uses AES-ECB/CCM and ChaCha20-Poly1305 ---- */
#define WOLFSSL_AES
#define WOLFSSL_AES_DIRECT
#define WOLFSSL_AES_COUNTER
#define HAVE_AESCCM
#define HAVE_AESGCM
#define HAVE_CHACHA
#define HAVE_POLY1305

#define WOLFSSL_ECDSA_DETERMINISTIC_K
#define HAVE_AES_ECB
#define HAVE_AES_DECRYPT
#define HAVE_CURVE25519
#define HAVE_ED25519
#define HAVE_ECC_SECPR2
#define HAVE_ECC_SECPR3

/* ---- hashes: SHA-2 family and SHA-3/Keccak for the PQC samplers ---- */
#define WOLFSSL_SHA224
#define WOLFSSL_SHA256
#define WOLFSSL_SHA384
#define WOLFSSL_SHA512
#define WOLFSSL_SHA3
#define WOLFSSL_SHAKE128
#define WOLFSSL_SHAKE256

/* ---- classical public key, for the portable th_ecdh / th_ecdsa / th_rsa ---- */
#define HAVE_ECC
#define ECC_TIMING_RESISTANT
#define HAVE_ECC384
#define HAVE_ECC521
#define WOLFSSL_SP_MATH_ALL
#define WOLFSSL_SP_4096   /* raise SP_INT_BITS so RSA_MAX_SIZE covers 4096-bit */
#define SP_INT_BITS 4096  /* RSA_MAX_SIZE = WC_BITS_FULL_BYTES(SP_INT_BITS) */
#define WOLFSSL_HAVE_SP_ECC
#define WOLFSSL_KEY_GEN

/* ---- post-quantum (the Task 1 / Task 2 target) ---- */
/* Static-pool allocator: no heap on bare metal. wolfSSL routes every
   XMALLOC/XFREE/XREALLOC through the bench driver's pool (see main_pqc.c).
   This is what turns MEMORY_E (-125) into a working allocation. */
#include <stddef.h>
#define XMALLOC_OVERRIDE
void *wolf_pqc_malloc(size_t n);
void  wolf_pqc_free(void *p);
void *wolf_pqc_realloc(void *p, size_t n);
#define XMALLOC(s, h, t)     wolf_pqc_malloc((s))
#define XFREE(p, h, t)       wolf_pqc_free((p))
#define XREALLOC(p, n, h, t) wolf_pqc_realloc((p), (n))

/* deterministic block RNG, implemented by the bench driver */
int custom_rand_block(unsigned char* out, unsigned int sz);

/* deterministic block RNG supplied by the bench driver (stable regression CRCs) */
#define CUSTOM_RAND_GENERATE_BLOCK  custom_rand_block

#define WOLFSSL_HAVE_MLKEM
#define WOLFSSL_HAVE_MLDSA

#endif /* WOLFSSL_USER_SETTINGS_H */
