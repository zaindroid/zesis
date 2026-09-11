/*
 * SecureMark-TLS th_util implementation for FRDM-MCXN947
 * - th_timestamp: DWT cycle counter -> microseconds
 * - th_printf / th_vprintf: UART via fsl_debug_console
 * - th_buffer: static buffer (no heap dependency)
 */
#include "th_util.h"
#include "th_lib.h"
#include "th_libc.h"
#include "board.h"
#include "fsl_debug_console.h"
#include <stdarg.h>
#include <string.h>

/* DWT cycle counter for timestamping (150 MHz core clock) */
#include "dwt.h"
#include "mbedtls/platform_time.h"

/* mbedTLS time source (no RTC on bare-metal): DWT-based ms */
mbedtls_ms_time_t mbedtls_ms_time(void)
{
    return (mbedtls_ms_time_t)(((uint64_t)dwt_get() * 1000ull) / 150000000ull);
}

/* --- th_libc implementations (EEMBC expects these) --- */
#include <stdlib.h>
#include <string.h>
void *th_memset(void *b, int c, size_t len) { return memset(b, c, len); }
void *th_malloc(size_t size) { return malloc(size); }
void  th_free(void *ptr) { free(ptr); }

/* Simple xorshift RNG for mbedTLS ECP blinding.
 * Blinding does not change the ECDH/ECDSA result (multiplicative and cancels),
 * it only randomizes the intermediate computation. A deterministic PRNG is
 * sufficient and keeps ECDSA signatures deterministic (RFC 6979). */
int mbedtls_rng_for_ecp(void *ctx, unsigned char *buf, size_t len)
{
    static uint32_t s = 0x12345678u;
    (void)ctx;
    for (size_t i = 0; i < len; i++) {
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        buf[i] = (unsigned char)(s & 0xFF);
    }
    return 0;
}

#define CORE_HZ 150000000u

static unsigned char g_generic_buffer[EE_MINBUF * 4];

void
th_pre(void)
{
}

void
th_post(void)
{
}

void
th_buffer_initialize(void)
{
}

unsigned char *
th_buffer_address(void)
{
    return g_generic_buffer;
}

size_t
th_buffer_size(void)
{
    return sizeof(g_generic_buffer);
}

/* --- timestamp: DWT -> us --- */
void
th_timestamp_initialize(void)
{
    dwt_init();
}

static uint64_t g_dwt_total_us = 0;
static uint32_t g_last_cycles = 0;
static int g_first = 1;

/* called by the benchmark's clear_timestamps() to reset lap timing */
void th_timestamp_reset(void)
{
    g_first = 1;
    g_dwt_total_us = 0;
    g_last_cycles = 0;
}

void
th_timestamp(void)
{
    /* The EEMBC profile sets g_verify_mode during un-timed preambles (e.g.
     * wrap_ecdsa_verify signs a test message before timing the verify loop).
     * th_timestamp() must NOT record during those, or g_timestamps[0]/[1]
     * (which the ips formula uses) get corrupted by the preamble. */
    extern bool g_verify_mode;
    if (g_verify_mode) {
        return;
    }

    uint32_t cycles = dwt_get();
    if (g_first) {
        g_last_cycles = cycles;
        g_first = 0;
        g_dwt_total_us = 0;
    } else {
        uint32_t delta = cycles - g_last_cycles; /* unsigned wrap arithmetic */
        g_last_cycles = cycles;
        g_dwt_total_us += ((uint64_t)delta * 1000000ull) / CORE_HZ;
    }
    th_printf(EE_MSG_TIMESTAMP, (unsigned long)g_dwt_total_us);
    extern void push_timestamp(uint64_t us);
    push_timestamp(g_dwt_total_us);
}

/* --- serial output --- */
void
th_serialport_initialize(void)
{
    /* UART already initialized by BOARD_InitHardware() */
}

int
th_vprintf(const char *fmt, va_list args)
{
    /* fsl_debug_console's vprintf */
    return vprintf(fmt, args);
}

void
th_printf(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vprintf(fmt, args);
    va_end(args);
}

void
th_monitor_initialize(void)
{
}

void
th_command_ready(volatile char *p)
{
    (void)p;
}
