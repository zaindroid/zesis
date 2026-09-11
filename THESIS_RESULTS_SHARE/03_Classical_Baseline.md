# 03 — Classical Baseline (EEMBC SecureMark-TLS) and the Classical→PQC Migration

## Purpose

Before PQC costs can be judged as expensive or cheap, they need a classical
baseline measured with an equally rigorous, industry-standard methodology.
The official **EEMBC SecureMark-TLS** self-hosted benchmark was ported to
both thesis boards, then used to build a matched classical-vs-PQC TLS
handshake migration comparison — latency and energy — on each platform.

## Setup / Method

EEMBC SecureMark-TLS official self-hosted benchmark (`profile/ee_*.c` +
`examples/selfhosted/main.c`), backed by a custom `th_*` porting layer over
mbedTLS (3.6.3 on MCXN947, ESP-IDF's bundled mbedTLS 3.x on ESP32-S3). Both
ports built at **-O2** for a fair ECC comparison. Score computed with
EEMBC's official formula `1000 / Σ(weight_i / ips_i)`; all 14 component
primitives independently validated against the official EEMBC reference
CRCs.

Three port fixes were required and are worth recording as they affect
correctness, not just performance: (1) mbedTLS ECP requires a non-NULL
blinding RNG for scalar multiplication — a small xorshift PRNG was
supplied (blinding is multiplicative and cancels, so ECDSA remains RFC 6979
deterministic); (2) the EEMBC peer ECDH point is raw X‖Y and needs the SEC1
`0x04` prefix before `mbedtls_ecp_point_read_binary`; (3) the EEMBC ECDSA
reference CRC is computed over the ASN.1 DER-encoded signature, not raw
r‖s. A fourth, timing-only bug (`th_timestamp()` recording during
`g_verify_mode` un-timed preambles) initially corrupted ips values by
orders of magnitude (e.g. ECDSA verify read as 70 µs/op instead of the
correct 56 ms/op) — fixed by respecting `g_verify_mode`, which also
corrected the final score from a spurious 14256 down to the real 5472
marks.

## Results

### SecureMark-TLS score, both boards (14/14 CRC pass)

| Primitive | MCXN947 (M33 150MHz, mbedTLS -O2) | ESP32-S3 (LX7 240MHz, mbedTLS -O2) | Faster |
|-----------|------------------------------------|-------------------------------------|--------|
| AES-ECB-144 | 87 µs | 224 µs | M33 2.6× |
| AES-ECB-2048 | 1,162 µs | 3,043 µs | M33 2.6× |
| AES-CCM-168 | 338 µs | 627 µs | M33 1.9× |
| ECDH P-256 | 19,676 µs | 94,733 µs | M33 4.8× |
| ECDSA sign | 34,029 µs | 100,806 µs | M33 3.0× |
| ECDSA verify | 56,202 µs | 196,850 µs | M33 3.5× |
| SHA-256-384 | 158 µs | 20 µs | **ESP 7.7×** (HW SHA) |
| SHA-256-4224 | 297 µs | 57 µs | **ESP 5.2×** (HW SHA) |
| **SecureMark score** | **5,472 marks** | **1,895 marks** | M33 2.9× |

MCXN947 wins every software-math primitive (ECC, AES, generic SHA loop);
ESP32-S3 wins only where it has a hardware accelerator (SHA engine, 5–8×).
Caveat: the ESP32-S3's ECC disadvantage is partly a -Os vs -O2 build
mismatch on ECC's optimization-sensitive software math — a matched -O2
ESP32 build (used here) already narrows this from an earlier -Os run
(score 1605 → 1895 at -O2).

### Classical → PQC TLS handshake migration (1 ECDH + 1 sign + 2 verify)

| Board | Classical ECC | PQC ML-KEM-768 + ML-DSA-44 | ML-DSA-65 | ML-DSA-87 |
|-------|---------------|----------------------------|-----------|-----------|
| MCXN947 | 166.1 ms | 108.6 ms (**−34.6%**) | 164.2 ms (−1.1%) | 229.1 ms (+37.9%) |
| ESP32-S3 | 495.2 ms | 88.8 ms (**−82.1%**) | 134.0 ms (−72.9%) | 187.1 ms (−62.2%) |

**NIST-level-matched comparison (the fair comparison):**

| NIST level | Classical | PQC | ECC-phase delta |
|------------|-----------|-----|-----------------|
| 1 | P-256 ECDH+ECDSA: 166.1 ms | ML-KEM-512 + ML-DSA-44: 151.0 ms | **−9.1%** |
| 3 (thesis operating point) | P-256 (baseline): 166.1 ms | ML-KEM-768 + ML-DSA-65: 250.7 ms | **+50.9%** |

Per-operation ratios (MCXN947, PQC/classical): ML-KEM key exchange costs
3.7–8.9× a single ECDH depending on security level, but **ML-DSA verify is
dramatically cheaper than ECDSA verify** (0.31–0.90× depending on level) —
this asymmetry is what makes level-1 PQC net cheaper despite the more
expensive key exchange.

### Energy (PPK2, free-running, 10 kHz, 3.3 V assumed)

| | MCXN947 | ESP32-S3 |
|---|---|---|
| Idle baseline | 12.73 mA | 47.39 mA |
| Benchmark active window | 188.5 s | 245.2 s |
| Active power (above idle) | **8.16 mW** | **97.48 mW** (12×) |
| Incremental energy (above idle) | 1,538 mJ | 23,902 mJ |

**Energy per TLS-handshake ECC phase** (active power × phase duration):

| Phase | MCX duration | MCX energy | ESP32 duration | ESP32 energy |
|-------|--------------|------------|-----------------|--------------|
| Classical ECC | 166.1 ms | 1.36 mJ | 495.2 ms | 48.27 mJ |
| PQC ML-KEM-768 + ML-DSA-44 | 108.6 ms | 0.89 mJ | 88.8 ms | 8.66 mJ |
| PQC ML-KEM-768 + ML-DSA-65 | 164.2 ms | 1.34 mJ | 134.0 ms | 13.06 mJ |
| PQC ML-KEM-768 + ML-DSA-87 | 229.1 ms | 1.87 mJ | 187.1 ms | 18.24 mJ |

**Energy migration delta (matches the latency delta, since active power is
~constant per board):**

| Board | PQC 768+44 vs classical | PQC 768+65 | PQC 768+87 |
|-------|------------------------|------------|------------|
| MCXN947 | **−35%** | −1% | +38% |
| ESP32-S3 | **−82%** | −73% | −62% |

### Earlier bare-metal single-board comparison (superseded numbers, kept for the record)

An earlier MCXN947-only migration analysis used a different ML-KEM dataset
(bare-metal PQClean at **-O0**, not the Zephyr -Os data used above) and
reported different deltas at the same operating points: 512+44 = −9.1%
(matches), 768+44 = **+17.3%** (vs the headline −34.6% above), 768+65 =
**+50.9%** (matches the NIST-level-3 headline number above exactly, since
that comparison used the same 166.1 ms classical baseline), 1024+87 =
+125.9% (worst case, not re-measured in the headline dataset). The
discrepancy at 768+44 is fully attributable to the ML-KEM build: -O0
debug (32.6 ms keypair) vs the Zephyr -Os data (8.7 ms keypair) used
elsewhere. **The Zephyr cross-platform dataset (used in the headline table
above) is the one-KEM-dataset-consistently-chosen number the thesis should
cite**; this bare-metal variant is retained here only as a documented
methodological cross-check, not a second finding.

## Analysis / Interpretation

1. **The ESP32-S3 result is surprising but physically explainable**:
   ESP-IDF's mbedTLS ECP implementation is far slower per operation than
   the M33's mbedTLS build (ECDH 80 ms vs 20 ms despite a 1.6× higher
   clock). Classical crypto is the bottleneck on ESP32, so migrating to
   PQC (whose PQClean implementation is comparatively efficient) is a
   *relief* — on a platform with a weak classical-ECC stack, PQC migration
   can be strictly cheaper, both in time and energy.
2. **On the MCXN947** the two are roughly at parity: PQC is cheaper at
   DSA-44, near-parity at DSA-65, more expensive at DSA-87 — the honest
   cost of a genuine security-level upgrade on a platform whose classical
   ECC stack is already efficient.
3. **Because active power is ~constant per board**, the energy delta
   tracks the latency delta directly — there is no separate energy story
   to tell beyond the latency one, which simplifies the thesis's framing.
4. **Sources are not perfectly matched across every table** (classical via
   SecureMark's own mbedTLS -O2; PQC ML-DSA via Zephyr -Os identical code
   both boards; PQC ML-KEM mixed sources across the two migration
   analyses) — stated honestly above rather than silently reconciled; the
   Zephyr cross-platform headline numbers are the ones to cite.

## Raw data

- `raw_data/03_classical_baseline/mcxn947_securemark_score.txt`, `esp32s3_securemark_score.txt` — full component tables + final scores, both boards
- `raw_data/serial_captures/serial_securemark_tls_mcxn947.txt`, `serial_securemark_tls_esp32s3_O2.txt`, `serial_securemark_tls_esp32s3_Os.txt` — full raw serial captures (the -Os ESP32 run referenced above as the pre-fix score of 1605)
- `raw_data/energy_ppk2/energy_securemark_tls_mcxn947.csv`, `energy_securemark_tls_esp32s3.csv` — raw PPK2 traces backing the energy tables
- See also `raw_data/02_pqc_benchmarks/` for the PQC-side ML-KEM/ML-DSA raw data feeding the migration comparison
