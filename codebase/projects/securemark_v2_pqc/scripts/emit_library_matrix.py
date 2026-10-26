#!/usr/bin/env python3
"""Emit results/PQC_LIBRARY_CONFIG_MATRIX.csv (Task 2)."""
import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results", "PQC_LIBRARY_CONFIG_MATRIX.csv")
CPU_HZ = 150_000_000.0

def cyc(ms):
    return int(round(ms / 1000.0 * CPU_HZ))

rows = []

# ---- PQClean clean C, ML-KEM-768, -O2 (measured this session) ----
# mlkem_bench, o2 build, mean of 174 iterations
for op, ms in (("keypair", 13.86), ("encapsulate", 15.33), ("decapsulate", 17.39)):
    rows.append(["PQClean (clean C)", "ML-KEM-768", "-O2", cyc(ms), f"{ms:.2f}",
                 "", "20680", "", "mlkem_bench/o2, n=174 mean"])

# ---- PQClean clean C, ML-KEM-768, -O0 (earlier) ----
for op, ms in (("keypair", 32.6), ("encapsulate", 37.9), ("decapsulate", 45.4)):
    rows.append(["PQClean (clean C)", "ML-KEM-768", "-O0", cyc(ms), f"{ms:.2f}",
                 "", "20680", "", "mlkem_bench, single run"])

# ---- PQClean clean C, ML-DSA-65, -O2 (measured this session) ----
rows.append(["PQClean (clean C)", "ML-DSA-65 sign", "-O2", cyc(91.61), "91.61",
             "", "23848", "", "mldsa_bench_nxp/b65o2, n=2000 mean; median 74.77"])

# ---- PQClean clean C, ML-DSA-65, -Os (earlier) ----
rows.append(["PQClean (clean C)", "ML-DSA-65 sign", "-Os", cyc(90.93), "90.93",
             "", "23848", "", "mldsa_bench_nxp/b65, n=2000 mean; median 73.72"])

# ---- wolfSSL native, -O2 (harness, 30-iteration means) ----
w = [
    ("ML-KEM-512 keypair", 1000/229.375), ("ML-KEM-512 encapsulate", 1000/266.075),
    ("ML-KEM-512 decapsulate", 1000/196.734),
    ("ML-KEM-768 keypair", 1000/142.626), ("ML-KEM-768 encapsulate", 1000/156.928),
    ("ML-KEM-768 decapsulate", 1000/121.330),
    ("ML-KEM-1024 keypair", 1000/90.329), ("ML-KEM-1024 encapsulate", 1000/98.613),
    ("ML-KEM-1024 decapsulate", 1000/79.620),
    ("ML-DSA-44 keypair", 1000/68.988), ("ML-DSA-44 sign", 1000/34.275),
    ("ML-DSA-44 verify", 1000/68.810),
    ("ML-DSA-65 keypair", 1000/39.797), ("ML-DSA-65 sign", 1000/16.566),
    ("ML-DSA-65 verify", 1000/40.694),
    ("ML-DSA-87 keypair", 1000/23.126), ("ML-DSA-87 sign", 1000/12.465),
    ("ML-DSA-87 verify", 1000/23.575),
    ("HashML-DSA-65 sign", 1000/17.960), ("HashML-DSA-65 verify", 1000/40.904),
]
for alg, ms in w:
    rows.append(["wolfSSL 5.9.2 (native)", alg, "-O2", cyc(ms), f"{ms:.2f}",
                 "", "", "575910", "libwolfssl_crypto.a; harness n=30 mean"])

# ---- wolfSSL native, -Os (first harness run) ----
wos = [("ML-KEM-768 keypair", 1000/35.730), ("ML-KEM-768 encapsulate", 1000/39.659),
       ("ML-KEM-768 decapsulate", 1000/30.571),
       ("ML-DSA-65 sign", 1000/3.377)]
for alg, ms in wos:
    rows.append(["wolfSSL 5.9.2 (native)", alg, "-Os", cyc(ms), f"{ms:.2f}",
                 "", "", "862146", "libwolfssl_crypto.a; harness n=3 mean"])

# ---- mbedTLS (classical reference, v1 SecureMark-TLS port) ----
for alg, ms in (("ECDH P-256", 19.68), ("ECDSA P-256 sign", 34.03),
                ("ECDSA P-256 verify", 56.20), ("AES-128 CCM", 1000/12026.938),
                ("SHA-256", 1000/40139.148)):
    rows.append(["mbedTLS 3.6.3 (classical)", alg, "-O2", cyc(ms), f"{ms:.2f}",
                 "", "", "", "securemark_tls_mcxn947"])

# ---- pqm4 (Cortex-M4F hand assembly) ----
# pqm4 measured on hardware (reset-loop, one op per boot) - absolute numbers
for op, ms in (("ML-KEM-768 keypair", 22.51), ("ML-KEM-768 encapsulate", 23.99)):
    rows.append(["pqm4 (M4F asm)", op, "-O3", cyc(ms), f"{ms:.2f}",
                 "", "", "", "measured; decap/ML-DSA fault on M33"])
rows.append(["pqm4 (M4F asm)", "ML-KEM-768 decapsulate", "-O3", "", "",
             "", "", "", "FAULTS on M33 (m4f asm)"])
rows.append(["pqm4 (M4F asm)", "ML-DSA-44/65/87", "-O3", "", "",
             "", "", "", "FAULTS on M33 (m4f asm)"])
rows.append(["pqm4 (M4F asm)", "ML-KEM-512 keypair", "-O3", "", "",
             "", "", "", "measured speedup 1.39x vs PQClean, absolute not captured"])

with open(OUT, "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["Library", "Algorithm", "Compile Flags", "Cycles",
                 "Latency (ms)", "Stack HWM (Bytes)", "Flash Text (Bytes)",
                 "Static Data (Bytes)", "Source / note"])
    wr.writerows(rows)

print(f"wrote {OUT}  ({len(rows)} rows)")
print()
print("Library                    Algorithm                 Flags  Latency(ms)")
for r in rows:
    print(f"  {r[0]:<26} {r[1]:<24} {r[2]:<5} {r[4] or '-':>10}")
