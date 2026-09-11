# EEMBC SecureMark-TLS on FRDM-MCXN947 — Port Result

## Summary

The official **EEMBC SecureMark-TLS** self-hosted benchmark was ported to the
FRDM-MCXN947 (Cortex-M33 @ 150 MHz) and executed with the EEMBC-provided
profile (`profile/ee_*.c` + `examples/selfhosted/main.c`), backed by a
custom `th_*` porting layer implemented over **mbedTLS 3.6.3**.

**Measured result: SecureMark-TLS Score = 5472.076 marks** (computed with
EEMBC's official score formula: `1000 / Σ(weight_i / ips_i)`). **All 14
component primitives pass the official EEMBC CRC validation** (14/14).

## Porting Layer (th_* implementations written for this port)

| File | Implements | Backed by |
|------|-----------|-----------|
| `th_aes.c` | AES-128 ECB + CCM encrypt/decrypt | `mbedtls_aes_crypt_ecb`, `mbedtls_ccm_*` |
| `th_sha.c` | SHA-256 | `mbedtls_sha256_*` |
| `th_ecdh.c` | ECDH P-256 | `mbedtls_ecdh_compute_shared` |
| `th_ecdsa.c` | ECDSA P-256 sign/verify | `mbedtls_ecdsa_sign_det_ext`, `mbedtls_ecdsa_verify` |
| `th_util.c` | Timestamp (DWT), printf (UART), buffer, ECP RNG | DWT cycle counter |

Platform fixes during the port:
- **printf retarget**: newlib `_write` → UART (LPUART4) via `retarget.c`
- **Float printf**: `-u _printf_float` for `%f` in ips/score output
- **DWT timing**: wrap-safe 64-bit cycle accumulator
- **Stack/heap**: 96 KB stack + 96 KB heap (`--defsym=__stack_size__/__heap_size__`)
- **Iteration tuning**: fixed per-component iteration counts (the EEMBC
  self-tuning diverges on this fast MCU — ips is still measured from the
  timed run, so the score is valid)

## Component Results (EEMBC CRC validation) — 14/14 PASS

| # | Primitive | ips (per sec) | µs/op | CRC | Expected | Status |
|---|-----------|---------------|-------|-----|----------|--------|
| 0 | AES-ECB-144 enc | 11515.8 | 87 | 0xc7b0 | 0xc7b0 | ✅ PASS |
| 1 | AES-ECB-224 enc | 7575.4 | 132 | 0x5481 | 0x5481 | ✅ PASS |
| 2 | AES-ECB-320 enc | 5370.3 | 186 | 0x998a | 0x998a | ✅ PASS |
| 3 | AES-CCM-52 enc | 6918.9 | 145 | 0xd82d | 0xd82d | ✅ PASS |
| 4 | AES-CCM-168 dec | 2961.2 | 338 | 0x005b | 0x005b | ✅ PASS |
| 5 | ECDH P-256 | 50.8 | 19,683 | 0xb659 | 0xb659 | ✅ PASS |
| 6 | ECDSA sign | 29.4 | 34,014 | 0x3a47 | 0x3a47 | ✅ PASS |
| 7 | ECDSA verify | 17.8 | 56,180 | 0x3a47 | 0x3a47 | ✅ PASS |
| 8 | SHA-256-23 | 93641.1 | 11 | 0x2151 | 0x2151 | ✅ PASS |
| 9 | SHA-256-57 | 39635.0 | 25 | 0x3b3c | 0x3b3c | ✅ PASS |
| 10 | SHA-256-384 | 6341.7 | 158 | 0x1d3f | 0x1d3f | ✅ PASS |
| 11 | variation-001 | 1101.6 | 908 | 0x0000 | 0x0000 | ✅ PASS |
| 12 | SHA-256-4224 | 3364.1 | 297 | 0x9284 | 0x9284 | ✅ PASS |
| 13 | AES-ECB-2048 enc | 860.6 | 1162 | 0x989e | 0x989e | ✅ PASS |

## Fixes Applied

### ECC correctness (ECDH, ECDSA) — three root causes resolved

1. **mbedTLS ECP requires a non-NULL RNG** (for scalar-multiplication
   blinding). Passing `NULL, NULL` returned `MBEDTLS_ERR_ECP_BAD_INPUT_DATA`
   (-0x4F80), aborting ECDH/ECDSA before any computation. Fixed by providing a
   small xorshift PRNG (`mbedtls_rng_for_ecp` in `th_util.c`); blinding is
   multiplicative and cancels, so ECDSA signatures remain RFC 6979
   deterministic.
2. **ECDH peer-point encoding**: the EEMBC peer public key is raw X||Y
   (64 bytes, no SEC1 `0x04` prefix). `mbedtls_ecp_point_read_binary` needs the
   SEC1 format, so `th_ecdh_init` prepends `0x04` before reading.
3. **ECDSA signature format**: EEMBC's reference CRC is over the **ASN.1
   DER-encoded** signature (70-72 bytes), not raw r||s (64 bytes).
   `th_ecdsa_sign` now DER-encodes and `th_ecdsa_verify` parses it.

Host-side verification (Python, pycryptodome) independently confirmed all three:
standard `X(d·Qp)` reproduces 0xb659, and the DER-encoded RFC 6979 signature
reproduces 0x3a47.

### Timing correctness — g_verify_mode fix (important!)

The EEMBC profile sets `g_verify_mode` during un-timed preambles (e.g.,
`wrap_ecdsa_verify` signs a test message before the timed verify loop;
`wrap_aes_ccm` runs an un-timed encrypt before the timed decrypt). The EEMBC
contract is that `th_timestamp()` must NOT record during these phases.
The first port implementation ignored `g_verify_mode` and always pushed a
timestamp, which corrupted `g_timestamps[0]/[1]` — the values the ips formula
uses. The symptoms were physically impossible ips values:

| Component | Wrong ips (before fix) | Correct ips (after fix) | Physical sanity check |
|-----------|----------------------|------------------------|----------------------|
| AES-CCM-168 dec | 1,429,592 (0.7 µs/op) | 2,961 (338 µs/op) | CCM-168 decrypt ≥ ~300 µs in software |
| ECDSA verify | 14,188 (70 µs/op) | 17.8 (56 ms/op) | P-256 verify = 2 scalar mults ≈ 2× sign cost |

The corrected ips values are consistent with the raw `m-lap-us` lap times in
the capture (e.g., 500 verifies in 28.1 s → 17.8 ips). This fix also affected
the final score: the corrupted values inflated it from the correct **5472
marks** to a wrong 14256 marks.

## Score Interpretation

The **5472 marks** score reflects all 14 primitives with their real measured
throughputs. ECC dominates the TLS handshake weighting: ECDH P-256 at ~51
ops/s (19.7 ms/op), ECDSA sign at ~29 ops/s (34 ms/op), ECDSA verify at ~18
ops/s (56 ms/op) — all software mbedTLS on the Cortex-M33. Symmetric crypto is
fast (AES-ECB-144 at ~11.5k ops/s, SHA-256-23 at ~94k ops/s). Per the EEMBC
methodology, higher is better. This is a preliminary/unofficial score (the
benchmark itself prints the disclaimer that submitting an official score
requires an EEMBC license).

## Artifacts

- `results/securemark_selfhosted_raw.txt` — full serial capture (14 components + score)
- `results/securemark_score.txt` — component table + final score
- Source: `th_aes.c`, `th_sha.c`, `th_ecdh.c`, `th_ecdsa.c`, `th_util.c`,
  `retarget.c`, `sm_main.c`, `board_main.c`, `mbedtls/` (mbedTLS 3.6.3)
