# Classical vs Post-Quantum TLS Crypto Migration — NXP FRDM-MCXN947

**Question answered:** What does migrating a TLS 1.2 handshake's public-key
crypto from classical ECC (ECDH/ECDSA P-256) to post-quantum lattice crypto
(ML-KEM/ML-DSA) cost on the same MCU, measured with the same (EEMBC)
methodology?

**Headline:** At NIST security level 1 the migration is **−9.1%** (PQC is
faster). At the thesis operating point (ML-KEM-768 + ML-DSA-65, NIST L3) the
ECC phase costs **+50.9%**. At the maximum (1024+87) it is **+125.9%**.

All numbers were measured on the **FRDM-MCXN947 (Cortex-M33 @ 150 MHz)**,
single core, no crypto accelerator, and recomputed independently from the raw
captures for this report.

---

## 1. Data sources and optimization levels

| Dataset | Project | Build | Source |
|---------|---------|-------|--------|
| Classical ECDH/ECDSA/AES/SHA | `securemark_tls_mcxn947` | mbedTLS **-O2**, th_* -O0 | SecureMark-TLS score run (14/14 CRC pass) |
| ML-KEM-512/768/1024 | `mlkem_bench` | PQClean **-O0** | `eembc_style/perf_memory_summary.csv` |
| ML-DSA-44/65/87 | `mldsa_bench_nxp` | PQClean **-O2** | `results/mldsa{44,65,87}_raw.txt`, `*_sign_raw.csv` |

**Optimization-level caveat:** the classical ECC and ML-DSA are at -O2; ML-KEM
was measured at -O0 (debug). At matched -O2, ML-KEM would be faster, so the
reported migration overhead is *conservative* (biased against PQC). ML-DSA
signing is fat-tailed (worst/median 4.8-8x); the median is used here and the
tail is addressed separately by the conformal latency certificates.

## 2. Per-operation comparison (same board, 150 MHz)

| Primitive | µs/op | PQC equivalent | µs/op | Ratio (PQC/class) |
|-----------|-------|----------------|-------|-------------------|
| ECDH P-256 | 19,676 | ML-KEM-512 (kp+enc+dec) | 72,166 | 3.67x |
|           |        | ML-KEM-768 (kp+enc+dec) | 115,971 | 5.89x |
|           |        | ML-KEM-1024 (kp+enc+dec) | 174,908 | 8.89x |
| ECDSA sign P-256 | 34,029 | ML-DSA-44 sign (median) | 43,690 | 1.28x |
|           |        | ML-DSA-65 sign (median) | 75,743 | 2.23x |
|           |        | ML-DSA-87 sign (median) | 99,627 | 2.93x |
| ECDSA verify P-256 | 56,202 | ML-DSA-44 verify | 17,562 | **0.31x** |
|           |        | ML-DSA-65 verify | 29,501 | 0.52x |
|           |        | ML-DSA-87 verify | 50,318 | 0.90x |

Key asymmetry: ML-DSA **verify** is much cheaper than ECDSA verify (Dilithium
verification is a small linear-algebra check), which offsets part of the
ML-KEM key-exchange cost. AES/SHA (bulk crypto) do not migrate and remain
classical (AES-CCM-168: 338 µs; SHA-256-384: 158 µs).

## 3. TLS 1.2 handshake public-key phase (EEMBC 14-phase model)

Per handshake, per device: **1 x ECDH + 1 x ECDSA sign + 2 x ECDSA verify**
(classical) vs **1 x ML-KEM (kp+enc+dec) + 1 x ML-DSA sign + 2 x ML-DSA
verify** (PQC). AES/SHA bulk phases are unchanged.

Classical ECC phase: **166.1 ms**.

| KEM | DSA | PQC ECC phase (ms) | Delta vs classical |
|-----|-----|--------------------|--------------------|
| 512 | 44 | 151.0 | **−9.1%** |
| 768 | 44 | 194.8 | +17.3% |
| 512 | 65 | 206.9 | +24.6% |
| 768 | 65 | 250.7 | **+50.9%** |
| 1024 | 44 | 253.7 | +52.7% |
| 512 | 87 | 272.4 | +64.0% |
| 1024 | 65 | 309.7 | +86.4% |
| 768 | 87 | 316.2 | +90.4% |
| 1024 | 87 | 375.2 | +125.9% |

## 4. NIST security-level matched (the fair comparison)

| NIST level | Classical | PQC | ECC-phase delta |
|------------|-----------|-----|-----------------|
| 1 | P-256 ECDH+ECDSA: **166.1 ms** | ML-KEM-512 + ML-DSA-44: **151.0 ms** | **−9.1%** |
| 3 (thesis op. point) | P-256 (practical baseline): 166.1 ms | ML-KEM-768 + ML-DSA-65: **250.7 ms** | **+50.9%** |

**Plain statement:** for equal (level-1) security, software lattice PQC on the
Cortex-M33 is *competitive with / faster than* classical ECC for the TLS
handshake public-key phase — because ML-DSA verification is dramatically
cheaper than ECDSA verification. Stepping to NIST level 3 (the thesis's
ML-KEM-768 operating point) costs about +51% in this phase. The
worst-case (1024+87) more than doubles it.

## 5. Caveats and honest limits

1. **Optimization mismatch**: ML-KEM measured at -O0 vs classical ECC at -O2
   → the migration overhead is overstated (conservative for PQC).
2. **ML-DSA fat tail**: median used for sign; the conformal-latency work
   (separate experiment) shows worst/median ratios of 4.8-8x, which is the
   real deadline risk, not the median.
3. **No energy comparison yet**: SecureMark-TLS has no PPK2 energy capture;
   ML-KEM energy is known (6629 µJ per 768 handshake, 3.3 V). An energy
   capture of the SecureMark run would complete the EEMBC/ULPMark-style
   picture.
4. **Single board**: this is the MCXN947 only; the ESP32-S3 port of
   SecureMark-TLS (in progress) will extend it cross-platform.
5. The SecureMark-TLS score itself (5472 marks) is a composite
   benchmark-throughput number; this report instead uses its per-primitive
   µs/op values for the phase-level migration model.

## 6. Files

- `migration_compare.py` — the synthesis script (reads the raw CSVs/captures)
- `migration_summary.csv` — machine-readable per-op values
- Inputs: `securemark_score.txt`, `mlkem_bench/results/eembc_style/perf_memory_summary.csv`,
  `mldsa_bench_nxp/results/mldsa{44,65,87}_raw.txt` + `*_sign_raw.csv`
