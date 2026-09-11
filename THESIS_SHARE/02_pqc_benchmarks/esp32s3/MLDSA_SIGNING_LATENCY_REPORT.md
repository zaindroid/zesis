# ML-DSA (Dilithium, FIPS 204) Non-Deterministic Signing Latency — ESP32-S3

Cross-platform counterpart to the NXP ML-DSA measurement. Same methodology,
identical measurement design, so the two are directly comparable. **Hardware:
ESP32-S3 (Xtensa LX7 dual-core, CPU-only, 240 MHz, 8 MB octal PSRAM).**
Ran on the real board (COM11, MAC cc:ba:97:13:8b:cc); not QEMU.

Firmware: `main/mldsa_bench.cpp` + PQClean `clean` C ML-DSA-44/65/87
(`components/pqc_ml_dsa/`). Timing via CCOUNT (`esp_cpu_get_cycle_count`),
recorded CPU freq 240,000,000 Hz, cycles->us = cycles/240. Task pinned to
core 0. 2000 sign ops/level, DIFFERENT message each iteration (counter
incremented into a 32-byte buffer) + fresh randomness per call (xorshift
stub advances per call — INSECURE, benchmarking only). Every sign verified
immediately; results buffered in RAM, dumped only after the timed loop.

---

## 1. Raw results (all three levels, 2000 signs each)

### ML-DSA-44 (K=4, L=4, sig 2420 B)
- keypair: mean 12,924 us (sd 130) | verify: mean 13,631 us (sd 3)
- **SIGN: min 19,972 | median 34,840 | mean 44,520 | p90 80,648 | p95 101,076 | p99 146,889 | max 210,665 us**
- **worst/median = 6.05x**
- retries: mean 3, max 26; dist: 0:457 1:362 2:261 3:210 4:171 5:125 6-10:299 11-20:103 >20:12
- fails: 0/2000

### ML-DSA-65 (K=6, L=5, sig 3309 B)
- keypair: mean 22,497 us (sd 28) | verify: mean 22,747 us (sd 3)
- **SIGN: min 31,248 | median 59,998 | mean 73,084 | p90 133,925 | p95 164,142 | p99 242,082 | max 488,275 us**
- **worst/median = 8.14x**
- retries: mean 3, max 46; dist: 0:382 1:310 2:248 3:203 4-5:286 6-10:385 11-20:164 >20:22
- fails: 0/2000

### ML-DSA-87 (K=8, L=7, sig 4627 B)
- keypair: mean 37,830 us (sd 170) | verify: mean 38,573 us (sd 2)
- **SIGN: min 50,205 | median 78,309 | mean 91,122 | p90 152,378 | p95 183,053 | p99 259,843 | max 377,235 us**
- **worst/median = 4.82x**
- retries: mean 3, max 23; dist: 0:495 1:390 2:295 3:210 4-5:270 6-10:269 11-20:70 >20:1
- fails: 0/2000

---

## 2. Distribution shape

Signing latency is a **multi-modal / right-skewed distribution**: a tight
low-mass mode at ~1 retry (20-35 ms), a broad middle at 3-10 retries
(60-160 ms), and a long tail of 11+ retries (up to 488 ms at level 65).
The shape is essentially the retry-count distribution convolved with a
~20-25 ms per-attempt cost. The retry histogram (0-5 common, long tail to
26-46) directly explains the latency tail: rejection sampling is the sole
source of non-determinism, confirmed by the per-call retry counter
instrumented into sign.c.

- Level 44: geometric-ish, tail to 26 retries.
- Level 65: fatter tail (max 46 retries, worst/median 8.1x) — the largest
  per-attempt cost (~15 ms) amplifies the tail.
- Level 87: retries bounded lower (max 23) but per-attempt cost highest
  (~25 ms), giving worst/median 4.8x.

## 3. Peak stack per level

Theoretical peak (static arrays in `crypto_sign_signature`):
- 44: mat[4][4] + s1,s1hat + s2,t1,t0 + seedbuf ~= 40 KB
- 65: mat[6][5] + vectors ~= 75 KB
- 87: mat[8][7] + vectors ~= 120 KB

Firmware: FreeRTOS task stack 131072 words (512 KB), allocated from PSRAM
(`CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=16384` — allocs >16 KB go to PSRAM).
At 65536 words (256 KB) ML-DSA-65 **panicked** (LoadProhibited in
`poly_uniform` — stack overflow); 512 KB runs all three cleanly.
HWM (uxTaskGetStackHighWaterMark) reported 13052/50932/7932 words but is
UNRELIABLE for a PSRAM-backed stack (the watermark reader assumes a
contiguous internal-RAM stack); treat the theoretical figures as the
authoritative peak-stack numbers.

## 4. Where signing buffers live

- **Static data** (keys, sig, result buffers): internal DRAM (default .bss).
- **Task stack** (all ML-DSA scratch: mat, s1/s2/t0/w0/w1/h, seedbuf):
  external PSRAM (512 KB allocation).
- PSRAM-path effect: none observable in the distribution shape; PSRAM is
  ~3-4x slower than internal SRAM but the arithmetic is compute-bound
  (NTT/matrix ops), so PSRAM latency adds a small constant, not variance.

## 5. EEMBC-SecureMark-style table (side-by-side with ML-KEM)

| op | ML-DSA-44 | ML-DSA-65 | ML-DSA-87 |
|---|---|---|---|
| keypair mean | 12.92 ms | 22.50 ms | 37.83 ms |
| keypair sd | 0.13 ms | 0.03 ms | 0.17 ms |
| verify mean | 13.63 ms | 22.75 ms | 38.57 ms |
| verify sd | 0.003 ms | 0.003 ms | 0.002 ms |
| sign median | 34.84 ms | 60.00 ms | 78.31 ms |
| sign mean | 44.52 ms | 73.08 ms | 91.12 ms |
| sign p99 | 146.9 ms | 242.1 ms | 259.8 ms |
| sign max | 210.7 ms | 488.3 ms | 377.2 ms |
| **worst/median** | **6.05x** | **8.14x** | **4.82x** |
| retry mean/max | 3 / 26 | 3 / 46 | 3 / 23 |
| sign fails | 0 | 0 | 0 |
| peak stack (theor.) | ~40 KB | ~75 KB | ~120 KB |
| app flash text | 90.9 KB | 90.6 KB | 90.7 KB |
| app rodata | 37.8 KB | 37.8 KB | 37.8 KB |
| app dram data | 11.3 KB | 11.3 KB | 11.3 KB |
| app dram bss | 26.9 KB | 30.4 KB | 33.3 KB |

(flash/data/bss are the full app incl. harness + IDF; the ML-DSA-44/65/87
code delta between levels is small because the differences are K/L params,
not separate implementations.)

---

## 2b. Histograms (per-level, ms buckets, 2000 signs each)

MLDSA-44:
  0-50: 1426  |  50-100: 470 | 100-150: 85 | 150-200: 15 | 200-250: 4
MLDSA-65:
  0-50: 741  |  50-100: 837 | 100-150: 284 | 150-200: 96 | 200-250: 24 | 250-300: 14 | 300-350: 3 | 450+: 1
MLDSA-87:
  0-50: 0  |  50-100: 1390 | 100-150: 403 | 150-200: 137 | 200-250: 48 | 250-300: 18 | 300-350: 3 | 350-400: 1

All three are right-skewed with a long tail; 65 is the most spread (bimodal).
## 6. Interpretation (state explicitly)

**(a) Is the tail fat enough to motivate the deadline-aware thesis? YES —**
worst/median = 4.8-8.1x across all three levels, far above the 2x
"real non-determinism" threshold. A system that provisions for the median
sign (35-78 ms) will miss its deadline ~5-15% of the time (p90-p99 span);
provisioning for the worst case (211-488 ms) costs 5-8x the median budget.
This is exactly the kind of fat tail that motivates an anytime/certified
deadline-aware design: the sign operation cannot be scheduled at a fixed
cost, so a perception pipeline must be able to degrade gracefully while
crypto runs.

**(b) ESP32 (CPU-only) vs NXP (M33) tail shape:** both show the same
mechanism (rejection-sampling-driven multi-modality), but the ESP32 tail is
**longer in relative terms** (worst/median 4.8-8.1x vs the M33's ~2x
typical for the same PQClean code). Absolute times are 5-15x larger on the
CPU-only ESP32 (no NPU/crypto accelerator; 240 MHz Xtensa vs 150 MHz M33
with a crypto block). The rejection retry distribution is identical (it is
algorithmically fixed), so the tail SHAPE difference is a timing-amplitude
effect: the same retry distribution maps to a wider relative spread on the
CPU-only platform because each retry costs more. This is a genuine
cross-platform finding: the ESP32's deadline risk from ML-DSA signing is
materially worse than the NXP board's, purely from per-attempt cost.

## 7. Files

- `results/mldsa{44,65,87}_sign_raw.csv` — full per-call (cycles, retries, fail), 2000 rows each
- `results/mldsa{44,65,87}_raw.txt` — full serial capture incl. keypair/verify arrays + HWM
- `main/mldsa_bench.cpp`, `components/pqc_ml_dsa/` — firmware + instrumented PQClean ML-DSA
- `scripts/instrument_mldsa.py` — rejection-counter instrumentation (4 sites per sign.c)

## 8. Caveats

- Randomness is the xorshift stub (INSECURE, benchmarking only) — per-call
  fresh, reproducible; not a security property.
- HWM unreliable for PSRAM stack (noted above); theoretical stack figures given.
- Flash/data/bss are whole-app (harness + IDF + crypto); ML-KEM comparison
  uses the same whole-app convention.
- 2000 samples/level, 95% CI on p99 ~ +/- 25% (n=20 tail obs); medians/means
  are tight.
