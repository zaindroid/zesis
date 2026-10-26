/*
 * th_util.h — minimal harness surface for the standalone PQC bench.
 *
 * The authoritative shims live in
 * codebase/securemark-v2/examples/selfhosted/profile/wolfssl_th_api/ and are
 * built there against the full EEMBC harness headers. This file supplies the
 * same three symbols (ee_status_t, th_malloc/th_free, th_printf) so the shims
 * compile standalone, without pulling in ee_main.h and the suite engine.
 */
#ifndef __TH_UTIL_H
#define __TH_UTIL_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
    EE_STATUS_OK    = 0,
    EE_STATUS_ERROR = 1
} ee_status_t;

/* static bump allocator in the bench driver — no heap on bare metal */
void *th_malloc(size_t size);
void  th_free(void *p);
int   th_printf(const char *fmt, ...);

#endif /* __TH_UTIL_H */
