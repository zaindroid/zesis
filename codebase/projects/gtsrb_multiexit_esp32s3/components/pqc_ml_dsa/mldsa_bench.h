#ifndef PQC_MLDSA_BENCH_H
#define PQC_MLDSA_BENCH_H
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
void PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections(void);
uint32_t PQCLEAN_MLDSA44_CLEAN_bench_get_rejections(void);
void PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections(void);
uint32_t PQCLEAN_MLDSA65_CLEAN_bench_get_rejections(void);
void PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections(void);
uint32_t PQCLEAN_MLDSA87_CLEAN_bench_get_rejections(void);
#endif

#ifdef __cplusplus
}
#endif
