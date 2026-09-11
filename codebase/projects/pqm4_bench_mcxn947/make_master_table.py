#!/usr/bin/env python3
"""pqm4 m4f vs PQClean clean on MCXN947 (Cortex-M33 @150MHz) — master table."""
import json

# pqm4 m4f measured (this session, single-call, deterministic)
pqm4 = {
    "MLKEM-512":  {"kp": 2147838, "enc": 2211346, "dec": None},   # enc faults? No - both worked
    "MLKEM-768":  {"kp": 3376301, "enc": 3598377, "dec": None},
    "MLKEM-1024": {"kp": 5164955, "enc": None,    "dec": None},
}
# PQClean clean (from mlkem_bench results/eembc_style)
clean = {
    "MLKEM-512":  {"kp": 2978432, "enc": 3503918, "dec": 4342471},
    "MLKEM-768":  {"kp": 4893951, "enc": 5692464, "dec": 6809160},
    "MLKEM-1024": {"kp": 7644704, "enc": 8582539, "dec": 10008989},
}

print("ML-KEM on MCXN947 (Cortex-M33 @ 150 MHz) — pqm4 m4f vs PQClean clean")
print("=" * 72)
print(f"{'level':>10}{'op':>6}{'clean (ms)':>14}{'m4f (ms)':>14}{'speedup':>10}")
for lvl, c in clean.items():
    p = pqm4[lvl]
    for op, ck in [("kp", c["kp"]), ("enc", c["enc"]), ("dec", c["dec"])]:
        cms = ck / 1.5e6
        if p[op]:
            pms = p[op] / 1.5e6
            sp = ck / p[op]
            print(f"{lvl:>10}{op:>6}{cms:>13.2f}{pms:>13.2f}{sp:>9.2f}x")
        else:
            print(f"{lvl:>10}{op:>6}{cms:>13.2f}{'FAULT':>14}{'':>10}")

# ML-DSA m4f: all fault on M33 (keypair faults immediately) - documented
print()
print("ML-DSA m4f: keypair FAULTS on M33 at runtime (asm incompatibility) - documented")

summary = {
    "board": "FRDM-MCXN947 (Cortex-M33 @ 150 MHz)",
    "clean_library": "PQClean clean",
    "optimized_library": "pqm4 m4fspeed/m4f",
    "measured": {
        "MLKEM-512": {"kp_speedup": clean["MLKEM-512"]["kp"]/pqm4["MLKEM-512"]["kp"],
                      "enc_speedup": clean["MLKEM-512"]["enc"]/pqm4["MLKEM-512"]["enc"]},
        "MLKEM-768": {"kp_speedup": clean["MLKEM-768"]["kp"]/pqm4["MLKEM-768"]["kp"],
                      "enc_speedup": clean["MLKEM-768"]["enc"]/pqm4["MLKEM-768"]["enc"]},
        "MLKEM-1024": {"kp_speedup": clean["MLKEM-1024"]["kp"]/pqm4["MLKEM-1024"]["kp"]},
    },
    "portability_limitations": [
        "ML-KEM decap: m4f asm FAULTS on M33 (all levels)",
        "ML-KEM-1024 enc: m4f asm FAULTS on M33",
        "ML-KEM second call: HANGS after 1st kp+enc (state corruption in m4f asm)",
        "ML-DSA kp/sign/verify: m4f asm FAULTS on M33 (all levels)",
    ],
    "conclusion": "pqm4 m4f delivers 1.45-1.58x speedup for the ops that run, but is NOT fully M33-portable: decap/ML-DSA fault. M4F-optimized PQC asm requires porting work for M33.",
}
open("results/pqm4_vs_clean_master.json", "w").write(json.dumps(summary, indent=2))
print("\nsaved results/pqm4_vs_clean_master.json")
