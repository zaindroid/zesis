#!/usr/bin/env python3
"""Wire the PQC suites into the SecureMark-V2 self-hosted main.c."""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "..", "..", "securemark-v2", "examples", "selfhosted", "main.c")
P = os.path.abspath(P)

s = open(P, "rb").read().replace(b"\r\n", b"\n").decode("utf-8")

if "ee_pqc.h" in s:
    print("already patched")
    raise SystemExit(0)

s = s.replace('#include "ee_main.h"',
              '#include "ee_main.h"\n#include "ee_pqc.h"\n#include <string.h>', 1)

wrappers = r'''/* ------------------------------------------------------------------
 * Post-quantum suite wrappers (Task 1).
 *
 * Per-primitive components: ML-KEM keypair/encapsulate/decapsulate for each
 * level, ML-DSA keypair/sign/verify for each level, and the HashML-DSA-65
 * pre-hash path. res->crc is 1 when the component behaved correctly (and, for
 * encapsulate and sign, when the synthesized regression CRC matched the
 * recorded value); the harness prints a mismatch against expected_crc = 1.
 * ---------------------------------------------------------------- */
static void
pqc_component(ee_pqc_algo_t algo, ee_pqc_op_t op, uint32_t i, wres_t *res)
{
    uint32_t it = 0, dt = 0, crc32v = 0;
    uint16_t pass = 0;

    ee_bench_pqc(algo, op, (i == 0) ? 3u : 1u, &it, &dt, &pass, &crc32v);
    res->iter = it;
    res->dt   = dt;
    res->crc  = pass;
    if (i == 0)
    {
        printf("      [pqc] crc32=0x%08lx self-check=%s\r\n",
               (unsigned long)crc32v,
               pass ? "PASS" : "FAIL");
    }
}

#define MAKE_WRAP_PQC(name, algo, op)                               \
    void wrap_##name(void *ex, uint32_t n, uint32_t i, wres_t *res) \
    {                                                               \
        (void)ex;                                                   \
        (void)n;                                                    \
        pqc_component((algo), (op), i, res);                        \
    }

MAKE_WRAP_PQC(kem512_kp     , EE_PQC_MLKEM_512   , EE_PQC_OP_KEYPAIR)
MAKE_WRAP_PQC(kem512_enc    , EE_PQC_MLKEM_512   , EE_PQC_OP_ENCAP)
MAKE_WRAP_PQC(kem512_dec    , EE_PQC_MLKEM_512   , EE_PQC_OP_DECAP)
MAKE_WRAP_PQC(kem768_kp     , EE_PQC_MLKEM_768   , EE_PQC_OP_KEYPAIR)
MAKE_WRAP_PQC(kem768_enc    , EE_PQC_MLKEM_768   , EE_PQC_OP_ENCAP)
MAKE_WRAP_PQC(kem768_dec    , EE_PQC_MLKEM_768   , EE_PQC_OP_DECAP)
MAKE_WRAP_PQC(kem1024_kp    , EE_PQC_MLKEM_1024  , EE_PQC_OP_KEYPAIR)
MAKE_WRAP_PQC(kem1024_enc   , EE_PQC_MLKEM_1024  , EE_PQC_OP_ENCAP)
MAKE_WRAP_PQC(kem1024_dec   , EE_PQC_MLKEM_1024  , EE_PQC_OP_DECAP)
MAKE_WRAP_PQC(dsa44_kp      , EE_PQC_MLDSA_44    , EE_PQC_OP_KEYPAIR)
MAKE_WRAP_PQC(dsa44_sign    , EE_PQC_MLDSA_44    , EE_PQC_OP_SIGN)
MAKE_WRAP_PQC(dsa44_ver     , EE_PQC_MLDSA_44    , EE_PQC_OP_VERIFY)
MAKE_WRAP_PQC(dsa65_kp      , EE_PQC_MLDSA_65    , EE_PQC_OP_KEYPAIR)
MAKE_WRAP_PQC(dsa65_sign    , EE_PQC_MLDSA_65    , EE_PQC_OP_SIGN)
MAKE_WRAP_PQC(dsa65_ver     , EE_PQC_MLDSA_65    , EE_PQC_OP_VERIFY)
MAKE_WRAP_PQC(dsa87_kp      , EE_PQC_MLDSA_87    , EE_PQC_OP_KEYPAIR)
MAKE_WRAP_PQC(dsa87_sign    , EE_PQC_MLDSA_87    , EE_PQC_OP_SIGN)
MAKE_WRAP_PQC(dsa87_ver     , EE_PQC_MLDSA_87    , EE_PQC_OP_VERIFY)
MAKE_WRAP_PQC(hashdsa65_sign, EE_PQC_HASHMLDSA_65, EE_PQC_OP_SIGN)
MAKE_WRAP_PQC(hashdsa65_ver , EE_PQC_HASHMLDSA_65, EE_PQC_OP_VERIFY)

'''
anchor = "static task_entry_t g_task[] ="
assert anchor in s
s = s.replace(anchor, wrappers + anchor, 1)

last = "    TASK(ecdsa_verify_p384r1  ,   32,  1.0f, 1)\n};"
assert last in s
pqc_tasks = """    TASK(ecdsa_verify_p384r1  ,   32,  1.0f, 1)
    /* Version 3: post-quantum (Task 1), per-primitive components. */
    TASK(kem512_kp     , 0, 1.0f, 1)
    TASK(kem512_enc    , 0, 1.0f, 1)
    TASK(kem512_dec    , 0, 1.0f, 1)
    TASK(kem768_kp     , 0, 1.0f, 1)
    TASK(kem768_enc    , 0, 1.0f, 1)
    TASK(kem768_dec    , 0, 1.0f, 1)
    TASK(kem1024_kp    , 0, 1.0f, 1)
    TASK(kem1024_enc   , 0, 1.0f, 1)
    TASK(kem1024_dec   , 0, 1.0f, 1)
    TASK(dsa44_kp      , 0, 1.0f, 1)
    TASK(dsa44_sign    , 0, 1.0f, 1)
    TASK(dsa44_ver     , 0, 1.0f, 1)
    TASK(dsa65_kp      , 0, 1.0f, 1)
    TASK(dsa65_sign    , 0, 1.0f, 1)
    TASK(dsa65_ver     , 0, 1.0f, 1)
    TASK(dsa87_kp      , 0, 1.0f, 1)
    TASK(dsa87_sign    , 0, 1.0f, 1)
    TASK(dsa87_ver     , 0, 1.0f, 1)
    TASK(hashdsa65_sign, 0, 1.0f, 1)
    TASK(hashdsa65_ver , 0, 1.0f, 1)
};"""
s = s.replace(last, pqc_tasks, 1)

done = "    { NULL, 0, 0, 0.0f } /* Done */"
assert done in s
s = s.replace(done, '    { "PQC_All", 20, 1000, 0.0f },\n' + done, 1)

disc = '    printf(\n        "\\nDisclaimer: these are not official scores.'
assert disc in s, "disclaimer anchor not found"
dual = r'''    /* Protocol-weighted score: the PQC operating point of this thesis, one
       encapsulation and decapsulation of ML-KEM-768 plus one signature and
       verification of ML-DSA-65 (TLS 1.3 style). Keypair cost is amortised
       across an established session, so it does not enter this figure. */
    {
        float i_e = 0.0f, i_d = 0.0f, i_s = 0.0f, i_v = 0.0f;
        size_t t;
        for (t = 0; t < g_numtasks; ++t)
        {
            if (strcmp(g_task[t].name, "kem768_enc") == 0) i_e = g_task[t].ips;
            if (strcmp(g_task[t].name, "kem768_dec") == 0) i_d = g_task[t].ips;
            if (strcmp(g_task[t].name, "dsa65_sign") == 0) i_s = g_task[t].ips;
            if (strcmp(g_task[t].name, "dsa65_ver") == 0)  i_v = g_task[t].ips;
        }
        if (i_e > 0.0f && i_d > 0.0f && i_s > 0.0f && i_v > 0.0f)
        {
            float pqc_tls13 = 1000.0f / (0.25f / i_e + 0.25f / i_d
                                         + 0.25f / i_s + 0.25f / i_v);
            printf("\nProtocol-weighted PQC score\n");
            printf("Suite                         Score\n");
            printf("----------------- -----------------\n");
            printf("%-19s %15.3f\n", "PQC_TLS1.3 (768/65)", pqc_tls13);
            printf("  w=0.25 each over kem768 enc/dec and dsa65 sign/verify\n");
        }
    }

'''
s = s.replace(disc, dual + disc, 1)

open(P, "w", encoding="utf-8", newline="\n").write(s)
print("main.c patched: wrappers", s.count("MAKE_WRAP_PQC"),
      "| PQC_All", s.count("PQC_All"),
      "| protocol block", s.count("PQC_TLS1.3"))
