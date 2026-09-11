/*
 * SecureMark-TLS th_util implementation for ESP32-S3 (ESP-IDF)
 * - th_timestamp: esp_timer_get_time() -> microseconds (int64, wrap-safe)
 * - th_printf / th_vprintf: standard printf (USB Serial/JTAG console)
 * - th_buffer: static buffer
 */
#include "th_util.h"
#include "th_lib.h"
#include "th_libc.h"
#include "esp_timer.h"
#include "mbedtls/platform_time.h"
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>

/* mbedTLS time source: esp_timer-based ms */
mbedtls_ms_time_t mbedtls_ms_time(void)
{
    return (mbedtls_ms_time_t)(esp_timer_get_time() / 1000);
}

/* --- th_libc implementations (EEMBC expects these) --- */
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

/* --- timestamp: esp_timer -> us --- */
void
th_timestamp_initialize(void)
{
    /* esp_timer is initialized by ESP-IDF at startup */
}

/* called by the benchmark's clear_timestamps() to reset lap timing */
void th_timestamp_reset(void)
{
    /* absolute-us timestamps: no state to reset */
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

    uint64_t us = (uint64_t)esp_timer_get_time();
    th_printf(EE_MSG_TIMESTAMP, (unsigned long)us);
    extern void push_timestamp(uint64_t us);
    push_timestamp(us);
}

/* --- serial output --- */
void
th_serialport_initialize(void)
{
    /* console set up by ESP-IDF startup */
}

int
th_vprintf(const char *fmt, va_list args)
{
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
