/*
 * X25519 (Curve25519 Diffie-Hellman), backed by curve25519-donna
 * (BSD-3-Clause, Copyright 2008 Google Inc.) -- a portable, 32-bit-
 * friendly reference implementation using standard radix-25.5/26
 * field arithmetic, representative of typical X25519 performance
 * (unlike TweetNaCl's deliberately size-optimized, non-representative
 * scalarmult, tried first and rejected for this reason). See x25519.c
 * for the source and rationale.
 */
#ifndef X25519_H
#define X25519_H

#define X25519_BYTES 32

/* Computes the public key q = scalarmult(n, base point). n is a
 * 32-byte private scalar. */
int crypto_scalarmult_base(unsigned char *q, const unsigned char *n);

/* Computes the shared secret q = scalarmult(n, p), where n is your own
 * 32-byte private scalar and p is the peer's 32-byte public key. */
int crypto_scalarmult(unsigned char *q, const unsigned char *n, const unsigned char *p);

#endif
