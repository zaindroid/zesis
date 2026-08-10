/* INSECURE STUB - BENCHMARKING ONLY. Not cryptographically secure.
   Replace with hardware TRNG before making any security claim. */

#include <stdint.h>
#include <stddef.h>
#include "randombytes.h"

static  uint32_t s = 0x12345678u;

int randombytes(uint8_t *buf, size_t n){
    for (size_t i = 0; i < n; i++) {
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        buf[i] = (uint8_t)(s & 0xFF);
    }

    return 0;

}