/* wolfSSL configuration for ESP32-S3 (Xtensa LX7).
 *
 * Only what the ML-KEM benchmark needs. No TLS layer, no filesystem, no threads,
 * portable C only (no Xtensa asm), deterministic RNG so runs are repeatable.
 */
#ifndef WOLFSSL_USER_SETTINGS_H
#define WOLFSSL_USER_SETTINGS_H

#ifdef __cplusplus
extern "C" {
#endif

#define WOLFCRYPT_ONLY
#define WOLFSSL_NO_ASM
#define WOLFSSL_SMALL_STACK

#define NO_FILESYSTEM
#define NO_WRITEV
#define WOLFSSL_NO_SOCK
#define SINGLE_THREADED
#define WOLFSSL_IGNORE_FILE_WARN

/* SHA-3 family: ML-KEM samples through SHAKE128/256 and hashes with SHA3. */
#define WOLFSSL_SHA3
#define WOLFSSL_SHAKE128
#define WOLFSSL_SHAKE256

/* The primitive under test. */
#define WOLFSSL_HAVE_MLKEM

/* ESP-IDF provides a heap; no static-pool override here. */
#include <stdlib.h>
#define XMALLOC(s, h, t)     malloc((s))
#define XFREE(p, h, t)       free((p))
#define XREALLOC(p, n, h, t) realloc((p), (n))

/* Deterministic RNG so every run sees the same keys and ciphertexts. */
#define CUSTOM_RAND_GENERATE_BLOCK custom_rand_block
int custom_rand_block(unsigned char *out, unsigned int sz);

#ifdef __cplusplus
}
#endif

#endif /* WOLFSSL_USER_SETTINGS_H */
