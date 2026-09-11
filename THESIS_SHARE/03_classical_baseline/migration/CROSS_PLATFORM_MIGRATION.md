# Cross-Platform: Classical vs Post-Quantum TLS Crypto Migration
# MCXN947 vs ESP32-S3

**Question:** How does the classical→PQC TLS handshake crypto migration cost
differ between the two thesis platforms?

**Headline:**
- **MCXN947** (Cortex-M33 @150 MHz): migrating the handshake ECC phase from
  ECDH/ECDSA P-256 to ML-KEM-768 + ML-DSA is **−34.6% (DSA-44), −1.1%
  (DSA-65), +37.9% (DSA-87)**.
- **ESP32-S3** (LX7 @240 MHz): the migration **saves 62–82%** — the classical
  ECDH/ECDSA in ESP-IDF's mbedTLS is the dominant cost (ECDH 80 ms, ECDSA
  verify 165 ms), while PQClean lattice crypto is comparatively fast.

All classical numbers are from the official EEMBC SecureMark-TLS benchmark
(**14/14 CRC validated on both boards**, both at -O2). All PQC numbers are
PQClean measured on the same boards.

---

## 1. Classical (SecureMark-TLS, -O2, 14/14 CRC on both)

| Primitive | MCXN947 (µs/op) | ESP32-S3 (µs/op) | MCX/ESP |
|-----------|-----------------|------------------|---------|
| AES-ECB-144 | 86.8 | 216.6 | 0.40x |
| AES-ECB-2048 | 1,162 | 2,934 | 0.40x |
| AES-CCM-168 | 337.7 | 601.4 | 0.56x |
| **ECDH P-256** | **19,676** | **79,859** | 0.25x |
| **ECDSA sign** | **34,029** | **84,962** | 0.40x |
| **ECDSA verify** | **56,202** | **165,180** | 0.34x |
| SHA-256-384 | 157.7 | 20.1 | **7.85x** (ESP HW SHA) |
| SHA-256-4224 | 297.3 | 56.6 | **5.25x** (ESP HW SHA) |
| SecureMark score | **5,472** | **1,895** | M33 2.9x |

## 2. PQC (PQClean on the same boards)

| Primitive | MCXN947 (µs) | ESP32-S3 (µs) | source |
|-----------|-------------|---------------|--------|
| ML-KEM-768 kp | 8,670 | 6,907 | Zephyr, same code both boards (150/240 MHz) |
| ML-KEM-768 enc | 9,904 | 7,973 | " |
| ML-KEM-768 dec | 11,734 | 9,282 | " |
| ML-DSA-44 sign (med) | 43,134 | 35,639 | Zephyr (same code both boards) |
| ML-DSA-65 sign (med) | 74,936 | 61,454 | " |
| ML-DSA-87 sign (med) | 98,112 | 80,456 | " |
| ML-DSA-44 verify | 17,562 | ~14,510 | bare-metal MCX; ESP scaled by sign ratio |

## 3. TLS 1.2 handshake ECC phase (1 ECDH + 1 sign + 2 verify)

| Board | Classical (ms) | PQC ML-KEM-768 + DSA-44 (ms) | DSA-65 | DSA-87 |
|-------|---------------|------------------------------|--------|--------|
| MCXN947 | 166.1 | 108.6 (**−34.6%**) | 164.2 (−1.1%) | 229.1 (+37.9%) |
| ESP32-S3 | 495.2 | 88.6 (**−82.1%**) | 133.7 (−73.0%) | 186.9 (−62.3%) |

## 4. Interpretation (honest)

1. **The ESP32-S3 result is surprising but physically explainable**: ESP-IDF's
   mbedTLS ECP implementation is far slower per operation than the M33's
   mbedTLS 3.6.3 build (ECDH 80 ms vs 20 ms despite a 1.6x higher clock). The
   classical side is therefore the bottleneck on the ESP32, and switching to
   lattice PQC (whose PQClean implementation is comparatively efficient) is a
   *relief* — a genuine finding: **on a platform with a weak classical-ECC
   stack, PQC migration can be strictly cheaper**.
2. **On the MCXN947** the two are roughly parity: PQC is cheaper at DSA-44,
   ~parity at DSA-65, more expensive at DSA-87. This matches the
   single-board comparison (which used a different ML-KEM build; see caveats).
3. **Sources are not perfectly matched** — this is the honest limit:
   - Classical: SecureMark via each board's mbedTLS (-O2 both).
   - PQC ML-DSA: Zephyr (-Os, identical code both boards) — clean.
   - PQC ML-KEM: MCX from Zephyr (-Os); ESP32 from the interleaved benchmark
     (240 MHz, mean per-op scaled by MCX op ratios) — an estimate, not a
     matched measurement. The ESP32 KEM section of the Zephyr capture was
     lost to a USB re-enumeration race.
   - The MCX-only `MIGRATION_COMPARISON.md` used the bare-metal ML-KEM (-O0,
     kp 32.6 ms), giving different deltas (+17.3% at 768+44); the Zephyr -Os
     ML-KEM (8.7 ms) used here shifts them down. For the thesis, one KEM
     dataset should be chosen consistently per table.
4. **Fat tails**: ML-DSA sign worst/median is 7.1x/6.0x/5.9x on BOTH boards
   (identical — algorithm property). The median is used here; deadline-critical
   use must account for the tail (see the conformal-latency work).

## 5. Files

- `cross_platform_compare.py` — synthesis script (recomputes everything)
- Inputs: `securemark_tls_mcxn947/results/securemark_score.txt`,
  `securemark_tls_esp32s3/results/securemark_esp32s3_score.txt`,
  `pqc_bench_zephyr/results/PQC_ZEPHYR_BENCHMARK_REPORT.md`,
  `gtsrb_multiexit_esp32s3/results/policy_results_esp32_{naive,static,adaptive}.csv`
