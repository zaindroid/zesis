# Standalone PQC bench — native wolfSSL on FRDM-MCXN947

Backend: wolfSSL 5.9.2, native ML-KEM (`wc_mlkem.c`) and ML-DSA (`wc_mldsa.c`),
crypto-only (`WOLFCRYPT_ONLY`), `-Os`, `WOLFSSL_NO_ASM`, Cortex-M33 @ 150 MHz,
bare metal, no debugger.

| Algorithm | keypair | encapsulate / sign | decapsulate / verify | Self-check | Regression CRC |
|---|---|---|---|---|---|
| ML-KEM-512  | 17.43 ms | 14.97 ms | 20.24 ms | PASS | 0xBB6188B7 |
| ML-KEM-768  | 28.02 ms | 25.24 ms | 32.74 ms | PASS | 0x8A48D4A5 |
| ML-KEM-1024 | 44.10 ms | 40.06 ms | 49.84 ms | PASS | 0xFDB3B688 |
| ML-DSA-44   | 66.36 ms | 165.55 ms | 69.70 ms | PASS | 0xBA561067 |
| ML-DSA-65   | 113.20 ms | 198.77 ms | 115.62 ms | PASS | 0x1EE8F069 |
| ML-DSA-87   | 192.68 ms | 254.21 ms | 195.14 ms | PASS | 0xAB6329B9 |
| HashML-DSA-65 | 113.20 ms | 235.17 ms | 115.11 ms | PASS | 0x9C084B80 |

All values from DWT->CYCCNT, wall time = cycles / 150 MHz.

## Reporting honesty

The CRCs are **synthesized regression checksums** over the deterministic output
buffers (ciphertext||shared-secret for KEM, signature for DSA). No EEMBC golden
value exists for a PQC profile, so "EEMBC CRC MATCH" is never claimed here.
`SELF-CHECK: PASS` means the functional round-trip held: KEM decapsulation
recovered the encapsulated shared secret exactly; DSA verification returned
valid. CRCs reproduce across runs (verified on two independent resets).

The ML-DSA sign figures are **single samples**, not medians. ML-DSA signs with
rejection sampling, so one draw can land anywhere on a distribution whose
worst/median ratio is ~6-7x (measured over 2000 runs at 256 B in Task 3B).
The standalone bench is a timing-boundary vehicle, not a distribution study.

## Build chain (recorded for reproducibility)

1. `libwolfssl_crypto.a` — crypto-only wolfSSL built with `WOLFSSL_USER_SETTINGS`,
   `WOLFCRYPT_ONLY`, `WOLFSSL_NO_ASM`, `CUSTOM_RAND_GENERATE_BLOCK`,
   `XMALLOC_OVERRIDE` (static pool, no heap), `-mcpu=cortex-m33 -mfloat-abi=hard`.
2. `pqc_bench_wolfssl_cm33_core0.bin` — driver + `th_mlkem.c` + `th_mldsa.c`,
   links the archive, 96 KB stack, 160 KB static allocation pool.
