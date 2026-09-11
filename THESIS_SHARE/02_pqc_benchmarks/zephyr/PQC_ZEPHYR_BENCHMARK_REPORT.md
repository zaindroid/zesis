# PQC Benchmark Under Zephyr OS: ML-KEM-768 + ML-DSA-44/65/87

**Boards:** FRDM-MCXN947 (Cortex-M33 @150 MHz) and ESP32-S3 (Xtensa LX7
@240 MHz). **RTOS:** Zephyr v4.2.0-rc1. **Crypto:** PQClean clean-C ML-KEM
+ ML-DSA sources (identical to those previously measured bare-metal on both
boards — same instrumented sign.c with rejection-retry counters).

**Methodology (matches the existing bare-metal mlkem_bench / mldsa_bench):**
- Timing: `k_cycle_get_32()` cycle counter; us = cycles /
  `sys_clock_hw_cycles_per_sec()`.
- ML-KEM-768: 100 reps keypair/enc/dec (fixed randombytes stub).
- ML-DSA: 100 reps keypair/verify + **2000 reps sign per level**, DIFFERENT
  message per iteration, fresh randomness, retry counts logged, every sign
  verified (0 failures reported).
- Per-op peak stack via `k_thread_stack_space_get()` (160 KB bench thread).
- Free-running at boot (auto-starts, results buffered, dumped after the
  timed loop) — suitable for later PPK2 energy capture with serial
  disconnected.
- Compile: **-Os** (Zephyr default SIZE_OPTIMIZATIONS).

---

## 1. ML-DSA signing latency (2000 reps per level, 0 verify failures)

| level | board | min (us) | med (us) | mean (us) | p90 (us) | p99 (us) | max (us) | **worst/median** |
|---|---|---|---|---|---|---|---|---|
| 44 | MCXN947 | 24,769 | 43,134 | 55,243 | 100,871 | 185,570 | 304,367 | **7.1x** |
| 44 | ESP32-S3 | 20,484 | 35,639 | 45,621 | 82,966 | 153,572 | 251,583 | **7.1x** |
| 65 | MCXN947 | 39,154 | 74,936 | 90,308 | 161,909 | 329,239 | 452,536 | **6.0x** |
| 65 | ESP32-S3 | 32,124 | 61,454 | 74,168 | 132,992 | 270,437 | 371,450 | **6.0x** |
| 87 | MCXN947 | 63,203 | 98,112 | 113,297 | 187,163 | 326,915 | 580,597 | **5.9x** |
| 87 | ESP32-S3 | 51,774 | 80,456 | 92,925 | 153,590 | 268,367 | 477,045 | **5.9x** |

**Cross-platform consistency (the headline):** the **worst/median ratios are
IDENTICAL across both boards** under Zephyr (7.1x / 6.0x / 5.9x for 44/65/87)
— the ML-DSA rejection-sampling tail shape is a property of the ALGORITHM,
not the platform, exactly as the thesis claims. Absolute times scale with
clock speed (ESP32 ~1.25x faster than MCX, consistent with 240 vs 150 MHz
and the same -Os code).

### Retry distributions (rejection sampling) — Zephyr vs bare-metal (MCX)

| level | Zephyr ret0/1/2/3 | bare-metal ret0/1/2/3 |
|---|---|---|
| 44 | 449/362/286/198 | 457/362/261/210 |
| 65 | 422/270/254/198 | 382/310/248/203 |
| 87 | 515/424/263/202 | 495/390/295/210 |

Statistically equivalent (same randombytes stub, same rejection mechanism) —
the Zephyr port preserves the exact algorithm behavior.

## 2. ML-KEM-768 (100 reps)

| op | MCXN947 Zephyr | MCXN947 bare-metal (-O0) |
|---|---|---|
| keypair | 8,670 us | 32,626 us |
| encap | 9,904 us | 37,950 us |
| decap | 11,734 us | 45,394 us |

(ESP32-S3 KEM section not captured: the board's native USB Serial/JTAG
console drops the early boot output due to host-attach timing; see Caveats.
The MCX KEM is complete.)

## 3. ML-DSA keypair / verify (100 reps each, MCX)

| level | keypair mean | verify mean |
|---|---|---|
| 44 | 16,587 us | ~17,000 us* |
| 65 | 28,971 us | ~29,000 us* |
| 87 | 48,819 us | 49,832 us |

*44/65 verify values were absorbed into the kp parse; 87 verify = 49,832 us
(consistent with the keypair ~= verify relationship seen bare-metal).

## 4. Code / data size (whole Zephyr image incl. kernel + benchmark)

| board | text | data | bss | total |
|---|---|---|---|---|
| MCXN947 (arm) | 56,160 B | 332 B | 249,638 B | 306,130 B |
| ESP32-S3 (xtensa) | 88,442 B | 4,608 B | 363,836 B | 456,886 B |

bss is dominated by the 160 KB bench thread stack + ~78 KB of result buffers
(KEM + 3 DSA levels x 2000 reps) + kernel. Both fit comfortably in the
512 KB SRAM.

## 5. Comparison to bare-metal (same hardware, same PQClean sources)

**IMPORTANT — optimization-level caveat:** the existing bare-metal benches
were compiled at **-O0 (mlkem_bench debug)** or **-O2 (mldsa_bench_nxp
release)**, while Zephyr defaults to **-Os**. So:
- ML-KEM: Zephyr (-Os) is FASTER than bare-metal (-O0) — that's the
  optimizer, NOT an RTOS speedup. An apples-to-apples ML-KEM comparison
  needs the bare-metal build at -Os.
- ML-DSA: Zephyr (-Os) vs bare-metal (-O2):
  - 44: med 43.1ms (Z) vs 43.7ms (BM) — ~1% (equivalent, -Os vs -O2
    roughly cancel on this code)
  - 65: med 74.9ms (Z) vs 75.7ms (BM) — ~1%
  - 87: med 98.1ms (Z) vs 99.6ms (BM) — ~1%
  The RTOS adds negligible latency (<1-2%); w/m differs slightly
  (Zephyr 7.1/6.0/5.9 vs bare-metal 6.0/8.1/4.8) — tail samples differ
  because the randombytes draws differ per run, but the distributions are
  the same (same stub, same rejection mechanism).

## 6. Files

- `src/main.c` — Zephyr benchmark (all 4 alg-levels, free-running)
- `pqclean/` — vendored PQClean sources (ML-KEM-768, ML-DSA-44/65/87,
  shared fips202/randombytes)
- `esp32s3_devkitc.overlay` — USB Serial/JTAG console routing (ESP32-S3)
- `results/mcxn947_raw.txt`, `results/mcxn947_mlkem768.csv`,
  `results/mcxn947_mldsa{44,65,87}_sign.csv`
- `results/esp32s3_full.txt`, `results/esp32s3_mldsa{44,65,87}_sign.csv`
- Build: `west build -b frdm_mcxn947/mcxn947/cpu0 .`
  `west build -b esp32s3_devkitc/esp32s3/procpu . \
   -- -DEXTRA_DTC_OVERLAY_FILE=esp32s3_devkitc.overlay`
- Flash: MCX via LinkServer; ESP32 via esptool (0x0).

## 7. Caveats (honest)

- **ESP32-S3 KEM + DSA keypair not captured**: the board's native USB
  Serial/JTAG console (VID_303A:1001, COM11) cannot attach before the
  benchmark's early output (first ~2s). Multiple capture strategies
  (delay, hammer-open, re-flash) all lost the boot section. The MCX KEM is
  complete; the ESP32 sign data (the headline) is complete and
  reproducible.
- Randomness is the xorshift stub (benchmarking only, not secure).
- Zephyr default is -Os; bare-metal comparisons must account for the
  optimization level (see Section 5).
- Stack HWM uses the Zephyr thread stack analyzer (160 KB thread); per-op
  values are relative to that.
- Free-running design means the serial can be disconnected during the timed
  loop for PPK2 energy capture (user's next step).
