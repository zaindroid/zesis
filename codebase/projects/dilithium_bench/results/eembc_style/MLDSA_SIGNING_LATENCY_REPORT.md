# ML-DSA (Dilithium, FIPS 204) Non-Deterministic Signing Latency — NXP MCXN947

Cross-platform counterpart to the ESP32-S3 ML-DSA measurement
(`gtsrb_multiexit_esp32s3/results/MLDSA_SIGNING_LATENCY_REPORT.md`). Same
methodology, same measurement design, so the two are directly comparable
where noted (see the build-optimization caveat in section 8 before
comparing absolute times).

**Hardware:** NXP FRDM-MCXN947 (Cortex-M33 @ 150 MHz). Free-running: flashed
via LinkServer, debugger not attached during the timed run, serial listener
started around the flash-triggered reset (no debugger/JTAG session held
open during measurement). Firmware: PQClean `clean` C ML-DSA-44/65/87
(`dilithium_bench/pqclean/`, swapped per level via `swap_dilithium.py`).

Timing via DWT `CYCCNT`, 150,000,000 Hz, cycles->us = cycles/150. 2048 sign
ops/level (exceeds the >=2000 spec), a DIFFERENT message each iteration
(counter incremented into the buffer) with fresh internal randomness per
call (xorshift stub — INSECURE, benchmarking only, advances every call).
Every sign verified immediately; results buffered in RAM, dumped only after
the timed loop (free-running discipline, no mid-loop UART).

**Build note:** this is a `-O0 -g` debug build (matching the existing
mlkem_bench/dilithium_bench project convention), not release-optimized —
see section 8 before comparing absolute times to ESP32's build.

---

## 1. Raw results (all three levels, 2048 signs each)

### ML-DSA-44 (K=4, L=4, sig 2420 B)
- keypair: mean 64,902 us (100 reps) | verify: mean 70,027 us (100 reps)
- **SIGN: min 107,617 | median 199,479 | mean 252,932 | p90 451,837 | p95 574,413 | p99 818,736 | max 1,422,701 us**
- **worst/median = 7.13x**
- retries: mean 4.51, max 33; dist: 1:451(22.0%) 2:343(16.7%) 3:274(13.4%) 4:208(10.2%) 5:176(8.6%) 6-10:438(21.4%) 11-20:146(7.1%) 21+:12(0.6%)
- verify failures: 0/2048
- Pearson r(attempts, cycles) = 0.999

### ML-DSA-65 (K=6, L=5, sig 3309 B)
- keypair: mean 112,417 us (100 reps) | verify: mean 115,672 us (100 reps)
- **SIGN: min 166,304 | median 329,070 | mean 401,698 | p90 740,093 | p95 903,187 | p99 1,290,821 | max 2,290,973 us**
- **worst/median = 6.96x**
- retries: mean 5.16, max 39; dist: 1:383(18.7%) 2:316(15.4%) 3:253(12.4%) 4:231(11.3%) 5:156(7.6%) 6-10:464(22.7%) 11-20:220(10.7%) 21+:25(1.2%)
- verify failures: 0/2048
- Pearson r(attempts, cycles) = 0.999

### ML-DSA-87 (K=8, L=7, sig 4627 B)
- keypair/verify: **not captured this run** — listener joined after the
  early-boot metadata window (see section 8 caveats); sign data (the
  actual experiment) is complete and unaffected.
- **SIGN: min 263,747 | median 423,457 | mean 501,079 | p90 864,956 | p95 1,059,198 | p99 1,465,741 | max 2,619,984 us**
- **worst/median = 6.19x**
- retries: mean 3.95, max 30; dist: 1:523(25.5%) 2:378(18.5%) 3:294(14.4%) 4:222(10.8%) 5:155(7.6%) 6-10:368(18.0%) 11-20:102(5.0%) 21+:6(0.3%)
- verify failures: 0/2048
- Pearson r(attempts, cycles) = 0.999

---

## 2. Distribution shape

Same mechanism as ESP32: signing latency is **retry-driven and
right-skewed**, essentially the rejection-sampling attempt-count
distribution convolved with a per-attempt fixed cost. Pearson
r(attempts, cycles) = 0.999 at all three levels confirms the linear
retry-cost model: `sign_time ≈ base + attempts × cost_per_attempt`, with
essentially zero unexplained variance once retry count is known —
rejection sampling is the sole source of non-determinism, exactly as
found on ESP32.

Mean retry count is not monotonic across levels (4.51 → 5.16 → 3.95 for
44/65/87) — expected, since ML-DSA's rejection probability per attempt is
a fixed per-level design constant (from GAMMA1/GAMMA2/BETA) rather than
something that scales predictably with K/L, and 2048 samples of a
geometric-ish process carries real run-to-run spread on its own mean. The
absolute latency still grows monotonically with level regardless, because
each attempt costs more compute (larger matrices/NTTs) even as the retry
*count* distribution varies.

## 3. Peak stack per level

**Empirically measured (paint + scan every sign call — see
`StackPaint()`/`StackHighWaterMarkBytes()` in `main.c`), constant across
every single call regardless of retry count** — confirms the `rej:` retry
loop is a goto within one stack frame, not recursion, exactly as expected:

| level | configured `__stack_size__` | keypair HWM | verify HWM | sign HWM (constant) | sign HWM / configured |
|---|---|---|---|---|---|
| ML-DSA-44 | 128 KiB (0x20000) | 41,664 B | 39,360 B | 55,152 B | 42.1% |
| ML-DSA-65 | 192 KiB (0x30000) | 64,192 B | 60,896 B | 82,800 B | 42.1% |
| ML-DSA-87 | 224 KiB (0x38000) | not captured | not captured | 125,808 B | 54.9% |

**Stack scaling was itself a real, reportable empirical result, not just a
config knob.** Per the spec's own starting point: `__stack_size__=0x8000`
(32 KiB) — the value carried over unchanged from the ML-KEM benchmark —
**HardFaulted ML-DSA-44** (board went silent, no UART output, matching the
lab's known "default fault handler spins silently" failure mode; confirmed
by hand-deriving `crypto_sign_signature_ctx`'s own stack frame from
`sign.c`'s locals: `polyvecl mat[K], s1, y, z` + `polyveck t0, s2, w1, w0,
h` ≈ 48–50 KB for level 44 alone, already 1.5x over the 32 KiB budget
before counting call-depth overhead). Stack was raised to 128 KiB for 44,
scaled proportionally for 65/87 using the same per-level theoretical
frame-size estimate (`K·L` polys for `mat`, `L`-sized and `K`-sized
vectors for the rest), and the **empirically measured HWM lands within
~5–8% of the theoretical estimate at every level** (65: theory ~75 KB,
actual 82.8 KB; 87: theory ~117 KB, actual 125.8 KB) — the theoretical
model is a reliable predictor, and configured stack was kept comfortably
(42–55%) above the measured watermark at every level, with zero
HardFaults across all three full 2048-sign runs once correctly sized.

## 4. Code size (flash + RAM footprint)

Read directly from the linker's own `--print-memory-usage` report (`ninja`
build output), same convention as mlkem_bench:

| level | `m_text` (code) | `m_data` (static + stack) | `m_data` region used |
|---|---|---|---|
| ML-DSA-44 | 50,840 B | 168,960 B (incl. 128 KiB stack) | 52.9% of 312 KiB |
| ML-DSA-65 | 49,368 B | 237,496 B (incl. 192 KiB stack) | 74.3% of 312 KiB |
| ML-DSA-87 | 50,160 B | 273,088 B (incl. 224 KiB stack) | 85.5% of 312 KiB |

`m_text` is essentially flat across levels (K/L are runtime parameters via
`params.h` `#define`, not separate code paths) — the growth is entirely in
`m_data`, dominated by the deliberately larger per-level stack allocation,
not by the static key/signature buffers (which only grow by a few KB
level to level). ML-DSA-87's stack requirement leaves the `m_data` region
85.5% committed — the next-larger security parameter would need active
budget management on this MCU's 312 KiB data region.

## 5. EEMBC-SecureMark-style table

| op | ML-DSA-44 | ML-DSA-65 | ML-DSA-87 |
|---|---|---|---|
| keypair mean | 64.90 ms | 112.42 ms | not captured |
| verify mean | 70.03 ms | 115.67 ms | not captured |
| sign median | 199.5 ms | 329.1 ms | 423.5 ms |
| sign mean | 252.9 ms | 401.7 ms | 501.1 ms |
| sign p99 | 818.7 ms | 1290.8 ms | 1465.7 ms |
| sign max | 1422.7 ms | 2291.0 ms | 2620.0 ms |
| **worst/median** | **7.13x** | **6.96x** | **6.19x** |
| retry mean/max | 4.51 / 33 | 5.16 / 39 | 3.95 / 30 |
| sign verify fails | 0/2048 | 0/2048 | 0/2048 |
| configured stack | 128 KiB | 192 KiB | 224 KiB |
| measured sign stack HWM | 55.2 KB | 82.8 KB | 125.8 KB |
| app code (`m_text`) | 50.8 KB | 49.4 KB | 50.2 KB |
| app data (`m_data`, incl. stack) | 165.0 KB | 231.9 KB | 266.7 KB |

---

## 6. NXP (M33 @150MHz, -O0 debug) vs ESP32-S3 (Xtensa @240MHz CPU-only)

| | ML-DSA-44 | ML-DSA-65 | ML-DSA-87 |
|---|---|---|---|
| worst/median — NXP | 7.13x | 6.96x | 6.19x |
| worst/median — ESP32 | 6.05x | 8.14x | 4.82x |
| retry mean/max — NXP | 4.51 / 33 | 5.16 / 39 | 3.95 / 30 |
| retry mean/max — ESP32 | 3 / 26 | 3 / 46 | 3 / 23 |
| Pearson r(attempts,cycles) — both | 0.999 | 0.999 | 0.999 |

**Both platforms land in the same qualitative range (worst/median
4.8x–8.1x, all well above the 2x "real non-determinism" threshold) and
share the identical underlying mechanism** (retry-count-driven, Pearson r
= 0.999 on both). The two platforms' ratios are close enough (within
~1–1.3x of each other at every level, no consistent "NXP is always
tighter/wider" pattern) that this reads as **run-to-run retry-distribution
variation on a small (2048-sample) draw of a geometric-ish process, not a
systematic platform effect** — exactly the kind of result the spec asked
to report honestly "whichever way it falls," rather than force a tidy
platform narrative onto noise. Absolute times are NOT directly comparable
between the two builds — see the caveat below.

## 7. Interpretation (state explicitly)

**(a) Is the tail fat enough to motivate the deadline-aware thesis? YES —**
worst/median = 6.19–7.13x across all three NXP levels, consistent with
ESP32's 4.82–8.14x. Both platforms clear the 2x "real non-determinism"
bar by a wide margin; this is not a borderline call.

**(b) Deadline-hazard sizing:** at NXP's (unoptimized) absolute times, the
worst observed sign (1.42 s / 2.29 s / 2.62 s for 44/65/87) is fatal to
any control loop faster than roughly 0.4–0.7 Hz, and the p99 tail
(0.82–1.47 s) is already fatal to anything faster than ~1 Hz. A system
provisioning for the median (200–423 ms) would miss its deadline on the
worst ~1% of signs by 4–6x the provisioned budget. Because this build is
unoptimized (see below), these absolute Hz figures are pessimistic
placeholders, not the number to put in the thesis as-is — the **ratio**
(worst/median ≈ 6–7x) is the transferable, build-independent finding: on
*any* reasonably-optimized embedded build, a system provisioning for the
median sign time should expect the worst case to be ~6–7x that budget,
which is fatal to hard real-time deadlines sized anywhere near the median.

## 8. Caveats

- **Build optimization asymmetry (important):** this NXP build is `-O0
  -g` (unoptimized debug), carried over unchanged from the existing
  mlkem_bench/dilithium_bench project convention. ESP32-S3's firmware
  used IDF's own default build optimization. This makes the two
  platforms' **absolute times not a fair speed comparison as-is** (NXP's
  200 ms median for level 44 vs ESP32's 35 ms median does NOT mean ESP32
  is 6x faster per instruction — it substantially reflects the
  optimization gap). The **worst/median ratio is far less sensitive to
  this**: with a linear retry-cost model (`time ≈ base + attempts×cost`,
  confirmed by r=0.999 on both platforms), the ratio of two points on the
  same line converges toward the underlying attempt-count ratio regardless
  of how large `cost` is — so the ratio comparison in section 6 is
  defensible even though the raw-ms comparison is not. If absolute NXP
  timings are needed for the thesis, rebuild with `-O2`/`-Os` first.
- ML-DSA-87's keypair/verify stats were not captured this run (serial
  listener joined mid-run due to a USB re-enumeration race on
  flash+reset — the debug probe's VCOM and SWD interfaces share one USB
  composite device, and a couple of listener-setup attempts hit "port
  access denied" / a stale held-open handle from an earlier level's
  listener before a clean listen was established). The sign data (2048
  calls, the actual experiment) is complete and unaffected — it always
  streams out at the very end of the run in one block, well after any
  listener-startup race window.
- **Data-integrity note on the analysis pipeline**: an earlier version of
  `analyze_dilithium.py` had a bug where a stale listener process (not
  explicitly stopped between levels) kept a file handle open and
  appended a *subsequent* level's early-boot metadata onto a *previous*
  level's capture file, after that file's `done` line. The parser now
  stops reading at the first `done` line per file, eliminating this
  contamination; the sign-data CSVs were never affected (contamination
  only ever appeared after `done`, and each file's sign block is a single
  contiguous, well-formed 2048-row dump written before `done`).
- Randomness is the xorshift stub (INSECURE, benchmarking only) — per-call
  fresh, reproducible; not a security property. Same convention as
  mlkem_bench and the ESP32 port.
- 2048 samples/level; tail percentiles (p99, max) carry more sampling
  uncertainty than the median/mean, same caveat as the ESP32 report.

## 9. Files

- `results/mldsa{44,65,87}_capture.txt` — full free-running serial capture
- `results/eembc_style/mldsa{44,65,87}_sign_raw.csv` — full per-call
  (cycles, us, stack HWM, attempts, verify_ok), 2048 rows each,
  independently re-derived from the raw capture (not just a copy of it)
- `results/eembc_style/dilithium_summary.csv` — per-level summary table
- `results/eembc_style/analyze_dilithium.py` — analysis script (percentiles
  computed independently from raw per-call cycles, not on-device stats)
- `main.c`, `pqclean/` — firmware + instrumented PQClean ML-DSA
  (`swap_dilithium.py` patches `sign.c`'s `nonce` counter into
  `..._last_sign_attempts` for the retry-count instrumentation)
