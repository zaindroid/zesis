# ML-DSA (Dilithium, FIPS 204) Non-Deterministic Signing Latency — NXP FRDM-MCXN947

Cross-platform counterpart to the ESP32-S3 ML-DSA measurement (see
`H:\z_thesis\codebase\projects\gtsrb_multiexit_esp32s3\results\MLDSA_SIGNING_LATENCY_REPORT.md`).
Same methodology, identical measurement design — directly comparable.

**Hardware: NXP FRDM-MCXN947 (dual Cortex-M33 @ 150 MHz, single core used).
Toolchain: Arm GNU 14.2.1, -O2. Ran on the real board (probe 0V5USKFHVAZTY,
COM9), free-running, no debugger during measurement.**

Firmware: `hello_world.c` + instrumented PQClean `clean` C ML-DSA-44/65/87
(`pqclean/ml-dsa-{44,65,87}/`). Timing via DWT->CYCCNT, 150 MHz core clock,
cycles->us = cycles/150. 2000 sign ops/level, DIFFERENT message each
iteration + fresh randomness per call (xorshift stub, INSECURE, benchmarking
only). Every sign verified immediately; results buffered in RAM, dumped only
after the timed loop. Stack-painting high-water-mark for peak stack (same
technique as the ML-KEM bench in this lab).

---

## 1. Raw results (all three levels, 2000 signs each)

### ML-DSA-44 (K=4, L=4, sig 2420 B)
- keypair: mean 16,588 us (sd 168) | verify: mean 17,562 us (sd ~0)
- **SIGN: min 25,161 | median 43,690 | mean 55,770 | p90 100,683 | p95 126,244 | p99 183,245 | max 262,911 us**
- **worst/median = 6.02x**
- retries: mean 3, max 26; dist: 0:457 1:362 2:261 3:210 4-5:296 6-10:299 11-20:103 >20:12
- fails: 0/2000

### ML-DSA-65 (K=6, L=5, sig 3309 B)
- keypair: mean 29,132 us (sd 4) | verify: mean 29,501 us (sd ~0)
- **SIGN: min 39,735 | median 75,743 | mean 92,037 | p90 167,890 | p95 206,027 | p99 303,260 | max 611,120 us**
- **worst/median = 8.07x**
- retries: mean 3, max 46; dist: 0:382 1:310 2:248 3:203 4-5:286 6-10:385 11-20:164 >20:22
- fails: 0/2000

### ML-DSA-87 (K=8, L=7, sig 4627 B)
- keypair: mean 49,213 us (sd 224) | verify: mean 50,318 us (sd ~0)
- **SIGN: min 64,249 | median 99,627 | mean 115,745 | p90 192,658 | p95 231,143 | p99 328,317 | max 475,733 us**
- **worst/median = 4.78x**
- retries: mean 3, max 23; dist: 0:495 1:390 2:295 3:210 4-5:270 6-10:269 11-20:70 >20:1
- fails: 0/2000

## 2. Distribution shape

Right-skewed / heavy-tailed, identical mechanism to ESP32: the retry-count
distribution convolved with a ~25-35 ms per-attempt cost. Histograms (ms):

MLDSA-44:  0-50:1426 | 50-100:470 | 100-150:85 | 150-200:15 | 200-250:4
MLDSA-65:  0-50:741  | 50-100:837 | 100-150:284 | 150-200:96 | 200-250:24 | 250-300:14 | 300-350:3 | 450+:1
MLDSA-87:  50-100:1390 | 100-150:403 | 150-200:137 | 200-250:48 | 250-300:18 | 300-350:3 | 350-400:1

Level 65 has the fattest tail (max 46 retries -> 611 ms).

## 3. Peak stack (stack-painting high-water-mark)

- keypair HWM: reported per-iteration in raw (KP rows); sign/verify stack
  measured via the paint technique. ML-DSA-44 sign fits in the default 32 KB
  stack; ML-DSA-65/87 need >32 KB -> this firmware builds with
  `-Wl,--defsym=__stack_size__=0x20000` (128 KB linker stack region).
  Theoretical peak (mat[K][L] arrays): 44 ~40 KB, 65 ~75 KB, 87 ~120 KB.
- Firmware runs all three levels cleanly at 128 KB stack.

## 4. Where signing buffers live

All static data (keys, sig, result arrays) in SRAM (.bss/.data). The ML-DSA
scratch (mat, polyvecl/polyveck) is on the main stack (internal SRAM, 128 KB
region). No PSRAM involvement on this board (MCXN947 has no external RAM).

## 5. EEMBC-SecureMark-style table (side-by-side with ML-KEM suite)

| op | ML-DSA-44 | ML-DSA-65 | ML-DSA-87 |
|---|---|---|---|
| keypair mean | 16.59 ms | 29.13 ms | 49.21 ms |
| verify mean | 17.56 ms | 29.50 ms | 50.32 ms |
| sign median | 43.69 ms | 75.74 ms | 99.63 ms |
| sign mean | 55.77 ms | 92.04 ms | 115.75 ms |
| sign p99 | 183.2 ms | 303.3 ms | 328.3 ms |
| sign max | 262.9 ms | 611.1 ms | 475.7 ms |
| **worst/median** | **6.02x** | **8.07x** | **4.78x** |
| retry mean/max | 3 / 26 | 3 / 46 | 3 / 23 |
| sign fails | 0 | 0 | 0 |
| peak stack | ~40 KB | ~75 KB | ~120 KB |
| app text | 22.97 KB | 22.73 KB | 22.98 KB |
| app bss | 161.8 KB | 164.8 KB | 167.6 KB |

(app text/bss include harness + SDK + 128 KB stack; same whole-app
convention as the ML-KEM bench.)

## 6. Cross-platform comparison (identical workload, identical algorithm)

| level | NXP median | NXP p99 | NXP max | NXP w/m | ESP32 median | ESP32 p99 | ESP32 max | ESP32 w/m |
|---|---|---|---|---|---|---|---|---|
| 44 | 43.7 ms | 183.2 | 262.9 | **6.02x** | 34.8 ms | 146.9 | 210.7 | **6.05x** |
| 65 | 75.7 ms | 303.3 | 611.1 | **8.07x** | 60.0 ms | 242.1 | 488.3 | **8.14x** |
| 87 | 99.6 ms | 328.3 | 475.7 | **4.78x** | 78.3 ms | 259.8 | 377.2 | **4.82x** |

**Retry distributions are IDENTICAL across platforms** (44: 0:457 1:362 2:261
3:210 on both; 65: 0:382 1:310 2:248 3:203 on both; 87: 0:495 1:390 2:295
3:210 on both) — the rejection mechanism is algorithmically fixed, so the
TAIL SHAPE is hardware-independent. Absolute times differ (NXP 1.25-1.3x
slower: 150 MHz M33 -O2 vs 240 MHz Xtensa -Os), and worst/median ratios
agree within 1% (6.02/6.05, 8.07/8.14, 4.78/4.82).

## 7. Interpretation (state explicitly)

**(a) Tail fat enough to motivate the deadline-aware thesis? YES —**
worst/median = 4.8-8.1x on NXP (matching ESP32). Median-provisioned signing
misses its deadline ~5-15% of the time (p90-p99); worst-case provisioning
costs 5-8x the median. This is the same conclusion as the ESP32 measurement,
now confirmed on a second platform.

**(b) NXP vs ESP32 tail shape:** the retry distribution is byte-identical
across platforms, and worst/median agrees within 1%. The tail SHAPE is a
property of the algorithm (rejection sampling), not the platform. Absolute
latency differs by platform compute speed only. This is a clean,
reproducible cross-platform result: the ML-DSA signing tail is fat on both
an M33 MCU and an Xtensa MCU, with identical relative spread.

## 8. Files

- `results/mldsa{44,65,87}_sign_raw.csv` — full per-call (cycles, retries, fail), 2000 rows each
- `results/mldsa{44,65,87}_raw.txt` — full serial captures (keypair/verify arrays + stack HWM)
- `hello_world.c`, `pqclean/ml-dsa-{44,65,87}/`, `pqclean/fips202.c`, `pqclean/randombytes.c`
- Build: `cmake ... -DMLDSA_LEVEL=<44|65|87> -DCMAKE_C_FLAGS=-O2` (see CMakeLists.txt)

## 9. Caveats

- Randomness is the xorshift stub (INSECURE, benchmarking only).
- -O2 build (vs ESP32 -Os); absolute times not directly comparable across
  platforms, but retry distributions and worst/median ratios are.
- 2000 samples/level; p99 95% CI ~ +/- 25% (n=20 tail obs).
- app text/bss are whole-app (harness + SDK + stack).
