# EEMBC SecureMark-TLS on ESP32-S3 — Port Result

## Summary

The official **EEMBC SecureMark-TLS** self-hosted benchmark was ported to the
**ESP32-S3** (Xtensa LX7, 240 MHz, ESP-IDF v5.4) using **ESP-IDF's bundled
mbedTLS 3.x**, with the same `th_*` porting layer structure as the MCXN947
port (adapted: `esp_timer_get_time()` for timing, standard printf console,
xorshift ECP-blinding RNG, SEC1 point prefix, ASN.1-DER ECDSA signatures).

**Measured result: SecureMark-TLS Score = 1895.064 marks** (rebuilt at -O2 for a fairer ECC comparison with the MCXN947 -O2 mbedTLS build).
**All 14 component primitives pass the official EEMBC CRC validation (14/14).**

## Component Results (EEMBC CRC validation) — 14/14 PASS

| # | Primitive | ips (per sec) | µs/op | CRC | Expected | Status |
|---|-----------|---------------|-------|-----|----------|--------|
| 0 | AES-ECB-144 enc | 4466.7 | 224 | 0xc7b0 | 0xc7b0 | ✅ PASS |
| 1 | AES-ECB-224 enc | 2997.9 | 334 | 0x5481 | 0x5481 | ✅ PASS |
| 2 | AES-ECB-320 enc | 2100.0 | 476 | 0x998a | 0x998a | ✅ PASS |
| 3 | AES-CCM-52 enc | 3620.6 | 276 | 0xd82d | 0xd82d | ✅ PASS |
| 4 | AES-CCM-168 dec | 1594.8 | 627 | 0x005b | 0x005b | ✅ PASS |
| 5 | ECDH P-256 | 10.6 | 94,733 | 0xb659 | 0xb659 | ✅ PASS |
| 6 | ECDSA sign | 9.9 | 100,806 | 0x3a47 | 0x3a47 | ✅ PASS |
| 7 | ECDSA verify | 5.1 | 196,850 | 0x3a47 | 0x3a47 | ✅ PASS |
| 8 | SHA-256-23 | 141,665 | 7 | 0x2151 | 0x2151 | ✅ PASS |
| 9 | SHA-256-57 | 59,761 | 17 | 0x3b3c | 0x3b3c | ✅ PASS |
| 10 | SHA-256-384 | 48,895 | 20 | 0x1d3f | 0x1d3f | ✅ PASS |
| 11 | variation-001 | 2892.7 | 346 | 0x0000 | 0x0000 | ✅ PASS |
| 12 | SHA-256-4224 | 17,540 | 57 | 0x9284 | 0x9284 | ✅ PASS |
| 13 | AES-ECB-2048 enc | 328.6 | 3,043 | 0x989e | 0x989e | ✅ PASS |

## Port adaptations vs the MCXN947 port

- **Timing**: `esp_timer_get_time()` (int64 µs) replaces the DWT counter.
- **Console**: standard `printf`/`vprintf` (USB Serial/JTAG, COM17).
- **mbedTLS**: ESP-IDF's bundled mbedTLS (no vendored library copy needed).
- **Watchdog**: ESP-IDF task watchdog disabled (the benchmark's long
  non-yielding timed loops would otherwise trigger it).
- **Build**: **-O2** (matched to the MCXN947 mbedTLS -O2 for a fair ECC comparison); a -Os run scored 1605, the -O2 run 1895.
- Kept: `g_verify_mode` timestamp fix, SEC1 `0x04` ECDH point prefix,
  ASN.1-DER ECDSA signatures, xorshift ECP-blinding RNG.

## Cross-platform comparison (same EEMBC benchmark, 14/14 CRC on both)

| Primitive | MCXN947 (M33 150MHz, mbedTLS -O2) | ESP32-S3 (LX7 240MHz, mbedTLS -O2) | Faster |
|-----------|------------------------------------|-------------------------------------|--------|
| AES-ECB-144 | 87 µs | 224 µs | M33 2.6x |
| AES-ECB-2048 | 1162 µs | 3043 µs | M33 2.6x |
| AES-CCM-168 | 338 µs | 627 µs | M33 1.9x |
| ECDH P-256 | 19,676 µs | 94,733 µs | M33 4.8x |
| ECDSA sign | 34,029 µs | 100,806 µs | M33 3.0x |
| ECDSA verify | 56,202 µs | 196,850 µs | M33 3.5x |
| SHA-256-384 | 158 µs | 20 µs | **ESP 7.7x** (HW SHA) |
| SHA-256-4224 | 297 µs | 57 µs | **ESP 5.2x** (HW SHA) |
| SecureMark score | **5472** | **1895** | M33 2.9x |

**Honest caveats:**
1. **Optimization mismatch**: MCXN947 mbedTLS compiled at -O2 (needed for the
   MULADDC asm fix); ESP32-S3 at -Os (ESP-IDF default). ECC software math is
   highly optimization-sensitive — a large part of the ESP32's ECC
   disadvantage is likely the -Os build. A matched -O2 ESP32 build would give a
   fairer ECC comparison.
2. **SHA hardware acceleration**: the ESP32-S3's SHA-256 advantage is its
   hardware SHA engine (7.7x on SHA-384), which the MCXN947 does not use for
   SHA.
3. Both ports validated 14/14 against the official EEMBC reference CRCs, so
   the cryptographic correctness is confirmed on both platforms.

## Files

- `results/securemark_esp32s3_raw.txt` — full serial capture
- `results/securemark_esp32s3_score.txt` — component table + score
- Source: `main/` (th_*.c, sm_main.c, main.cpp), `profile/` (EEMBC sources),
  `scripts/build.sh` + `idf_launcher.py`
