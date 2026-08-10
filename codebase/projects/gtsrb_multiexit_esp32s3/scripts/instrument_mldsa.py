"""Instrument PQClean ML-DSA sign.c files with a rejection-retry counter.

Each `goto rej` site (the 4 rejection conditions in crypto_sign_signature)
increments a file-local counter, exposed via reset/get hooks. This lets the
benchmark log the rejection-retry count per signature call, which is the
direct source of the non-deterministic signing latency.
"""
import glob
import re

for f in glob.glob('ml-dsa-*/sign.c'):
    s = open(f).read()
    m = re.search(r'PQCLEAN_(\w+)_CLEAN', s)
    prefix = m.group(1)
    hook = (
        "\n/* --- BENCHMARK INSTRUMENTATION: rejection-retry counter (not part of PQClean) --- */\n"
        f"static uint32_t {prefix}_bench_rejections = 0;\n"
        f"void {prefix}_bench_reset_rejections(void) {{ {prefix}_bench_rejections = 0; }}\n"
        f"uint32_t {prefix}_bench_get_rejections(void) {{ return {prefix}_bench_rejections; }}\n"
        "/* -------------------------------------------------------------------------------- */\n"
    )
    s = s.replace('#include <stdint.h>\n', '#include <stdint.h>\n' + hook, 1)
    s = s.replace('        goto rej;', '        { %s_bench_rejections++; goto rej; }' % prefix)
    open(f, 'w').write(s)
    n = s.count('_bench_rejections++')
    print(f'{f}: instrumented {n} rejection sites')

hdr = """#ifndef PQC_MLDSA_BENCH_H
#define PQC_MLDSA_BENCH_H
#include <stdint.h>
void PQCLEAN_MLDSA44_CLEAN_bench_reset_rejections(void);
uint32_t PQCLEAN_MLDSA44_CLEAN_bench_get_rejections(void);
void PQCLEAN_MLDSA65_CLEAN_bench_reset_rejections(void);
uint32_t PQCLEAN_MLDSA65_CLEAN_bench_get_rejections(void);
void PQCLEAN_MLDSA87_CLEAN_bench_reset_rejections(void);
uint32_t PQCLEAN_MLDSA87_CLEAN_bench_get_rejections(void);
#endif
"""
open('mldsa_bench.h', 'w').write(hdr)
print('wrote mldsa_bench.h')
