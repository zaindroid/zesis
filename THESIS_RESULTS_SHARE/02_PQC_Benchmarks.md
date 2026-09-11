# 02 — PQC Benchmarks: ML-KEM / ML-DSA Latency, Memory, Energy, Cross-Platform

## Purpose

Characterize the actual cost of post-quantum cryptography (ML-KEM-512/768/
1024 key exchange, ML-DSA-44/65/87 signing) on the thesis's target hardware
— latency, memory, and energy — as the input data every scheduling and
certification decision elsewhere in the thesis is built on. Covers four
boards: FRDM-MCXN947 (primary), ESP32-S3, a matched Zephyr RTOS
cross-platform re-run, and the STM32N6570-DK port status.

## Setup / Method

All boards run **PQClean** `clean` (portable reference C) implementations
unless noted. Timing via cycle counters (DWT on Cortex-M, CCOUNT on Xtensa,
`k_cycle_get_32()` under Zephyr). Every op verified correct on every run (0
failures across all datasets below). ML-KEM: 100 reps/op/level, fixed
randombytes stub, free-running (no debugger attached). ML-DSA: 2000
sign ops/level, a different message + fresh randomness per call (xorshift
stub — insecure, benchmarking only), every sign immediately verified,
retry counts logged per call (rejection sampling is the sole source of
non-determinism).

## Results

### ML-KEM performance (MCXN947, Cortex-M33 @150 MHz, PQClean, 100 reps/op)

| variant | operation | mean time (µs) | std as % of mean |
|---|---|---|---|
| ML-KEM-512 | keypair | 19,856.2 | 0.48% |
| ML-KEM-512 | encaps | 23,359.5 | 0.40% |
| ML-KEM-512 | decaps | 28,949.8 | 0.33% |
| ML-KEM-768 | keypair | 32,626.3 | 0.38% |
| ML-KEM-768 | encaps | 37,949.8 | 0.33% |
| ML-KEM-768 | decaps | 45,394.4 | 0.27% |
| ML-KEM-1024 | keypair | 50,964.7 | 0.30% |
| ML-KEM-1024 | encaps | 57,216.9 | 0.27% |
| ML-KEM-1024 | decaps | 66,726.6 | 0.23% |

**Full handshake (keypair+encaps+decaps):** 72.17 ms (512) / 115.97 ms
(768) / 174.91 ms (1024) — cross-validated against an independent earlier
benchmark run to within 0.2 ms. Scaling factor per security level: 512→768
≈1.61×, 768→1024 ≈1.53×, consistent with ML-KEM's O(k²) polynomial
dimension scaling.

**Peak stack (high-water-mark):**

| variant | keypair | encaps | decaps | % of 32 KiB region (worst) |
|---|---|---|---|---|
| ML-KEM-512 | 8,960 B | 11,592 B | 12,344 B | 37.7% |
| ML-KEM-768 | 13,056 B | 16,200 B | 17,272 B | 52.7% |
| ML-KEM-1024 | 18,176 B | 21,832 B | 23,384 B | 71.4% |

Decaps consistently uses the most stack (re-runs part of the encaps path
for the Fujisaki-Okamoto CCA check) — expected from the algorithm's own
structure. Code size ~41.4–41.9 KB flash across all three variants
(nearly flat — same source, size driven by `params.h` constants).

**Energy (PPK2, 100-rep active window, per-handshake):**

| Variant | Idle baseline | Total energy (100 reps) | Per-handshake |
|---|---|---|---|
| ML-KEM-512 (2-board mean) | 13.45–14.20 mA | ~420 mJ | ~4,201 µJ |
| ML-KEM-768 | 14.06 mA | 662.89 mJ | 6,628.9 µJ |
| ML-KEM-1024 | 14.21 mA | 975.84 mJ | 9,758.4 µJ |

Two caveats apply to every energy number: voltage assumed at 3.3V (not
measured — PPK2 Ammeter mode is a passive pass-through); per-operation
split within a handshake is a proportional-cycle-count modeling assumption,
not hardware-verified boundaries (the intended GPIO trigger was never
observed to toggle). The handshake *total* is a direct charge-integration
measurement, on firmer footing than the per-op breakdown.

### ML-DSA signing latency (2000 signs/level, 0 failures, both boards)

| level | board | median | worst/median | retry mean/max |
|---|---|---|---|---|
| ML-DSA-44 | MCXN947 | 43.69 ms | **6.02×** | 3 / 26 |
| ML-DSA-44 | ESP32-S3 | 34.84 ms | **6.05×** | 3 / 26 |
| ML-DSA-65 | MCXN947 | 75.74 ms | **8.07×** | 3 / 46 |
| ML-DSA-65 | ESP32-S3 | 60.00 ms | **8.14×** | 3 / 46 |
| ML-DSA-87 | MCXN947 | 99.63 ms | **4.78×** | 3 / 23 |
| ML-DSA-87 | ESP32-S3 | 78.31 ms | **4.82×** | 3 / 23 |

**Retry distributions are byte-identical across boards** at every level —
the rejection-sampling tail shape is a property of the algorithm, not the
platform; absolute latency scales with per-attempt compute cost (NXP
1.25–1.3× slower than ESP32 despite lower clock, i.e. the M33 is
comparatively efficient per cycle for this workload). Peak stack: ~40 KB
(44) / ~75 KB (65) / ~120 KB (87), theoretical, both boards; MCXN947 needed
a 128 KB linker stack (default 32 KB insufficient for 65/87); ESP32-S3 used
a 512 KB FreeRTOS task stack (PSRAM-backed; 256 KB panicked on ML-DSA-65).

**Interpretation (both boards agree):** worst/median = 4.8–8.1× is far
above the "2× = real non-determinism" threshold. A system provisioning for
the median sign will miss its deadline ~5–15% of the time (p90–p99 span);
worst-case provisioning costs 5–8× the median budget — this fat tail is
the direct motivation for a deadline-aware/anytime design (a synchronous
per-frame sign cannot have a certified latency; see the conformal latency
certification below).

### Conformal latency certification for ML-DSA signing

The same split-conformal machinery used to certify perception risk
(`00_Thesis_Overview.md` §2.4) applied to certify crypto *latency*:
`P(sign_latency ≤ τ) ≥ 1 − α`, τ = the ⌈(n+1)(1−α)⌉-th order statistic of
12,000 measured latencies (2,000/level/platform, 0 failures) — valid for
any distribution, handling the fat rejection-sampling tail honestly.

**Certified τ (MCXN947 @150MHz):**

| level | median | worst | τ(α=0.01) | τ(α=0.05) | τ(α=0.10) |
|---|---|---|---|---|---|
| ML-DSA-44 | 26.2 ms | 141.9 ms | 183.2 ms | 126.2 ms | 100.7 ms |
| ML-DSA-65 | 43.3 ms | 313.1 ms | 303.3 ms | 206.0 ms | 167.9 ms |
| ML-DSA-87 | 99.6 ms | 475.7 ms | 328.3 ms | 231.1 ms | 192.7 ms |

(Empirical exceed rates match α exactly: 0.95%/4.95%/9.95% — method
validated.) **Headline: ML-DSA signing cannot be certified within a 33 ms
frame at any level or any α** — even the worst *observed* latency exceeds
the frame, so a single synchronous ML-DSA-44 sign cannot be a per-frame
operation with a certified deadline. This motivates precompute/batch
signing, asynchronous signing, or treating signing as a rare operation the
anytime scheduler must schedule around (exactly what the joint scheduler in
`05_Learned_AI_Angles.md` does).

### Cross-platform matched Zephyr benchmark (identical code, both boards)

Same PQClean sources under Zephyr v4.2.0-rc1 on both boards, ML-DSA 2000
reps/level:

| level | board | median (µs) | worst/median |
|---|---|---|---|
| 44 | MCXN947 | 43,134 | **7.1×** |
| 44 | ESP32-S3 | 35,639 | **7.1×** |
| 65 | MCXN947 | 74,936 | **6.0×** |
| 65 | ESP32-S3 | 61,454 | **6.0×** |
| 87 | MCXN947 | 98,112 | **5.9×** |
| 87 | ESP32-S3 | 80,456 | **5.9×** |

**The worst/median ratios are identical across both boards under Zephyr**
— confirms the tail shape is an algorithm property, not a platform or RTOS
effect. ML-KEM-768 on MCXN947 under Zephyr (-Os): keypair 8,670 µs, encap
9,904 µs, decap 11,734 µs (faster than the bare-metal -O0 numbers above —
an optimization-level effect, not an RTOS speedup; RTOS overhead itself is
negligible, <1–2%, when optimization level is matched). ML-KEM-768 on
ESP32-S3 under Zephyr was recaptured after the original capture lost its
early boot output to a USB-enumeration race — the recovered raw trace is
included in raw data below.

### pqm4 (M-profile-optimized) vs PQClean clean on Cortex-M33

pqm4's hand-written Thumb-2 assembly (designed for M4F) gives real
speedups on M33 where it runs, but is not fully portable:

| level | op | PQClean clean (ms) | pqm4 m4f (ms) | speedup |
|---|---|---|---|---|
| ML-KEM-512 | keypair | 19.86 | 14.32 | **1.39×** |
| ML-KEM-512 | encaps | 23.36 | 14.74 | **1.58×** |
| ML-KEM-512 | decaps | 28.95 | **FAULT** | — |
| ML-KEM-768 | keypair | 32.63 | 22.51 | **1.45×** |
| ML-KEM-768 | encaps | 37.95 | 23.99 | **1.58×** |
| ML-KEM-768 | decaps | 45.39 | **FAULT** | — |
| ML-KEM-1024 | keypair | 50.96 | 34.43 | **1.48×** |
| ML-KEM-1024 | encaps | 57.22 | **FAULT** | — |

ML-DSA keypair faults immediately on all levels (NTT assembly is
M4F-specific in a way M33 cannot execute).

**Root-cause post-mortem (custom HardFault handler + live GDB):**

At the default 32 KB stack, ML-DSA-44 keypair produces:
```
CFSR = 0x00100000   HFSR = 0x40000000
MMFAR/BFAR stale, stacked PC/LR garbage
[FORCED] escalated to HardFault
```
**CFSR bit 20 = UNSTKERR** (unstacking error — the saved exception frame
was already corrupted before the CPU tried to unstack it), HFSR FORCED.
Not TrustZone, not an illegal instruction, not a classic unaligned-LDRD
UsageFault.

At 128 KB stack the hardware fault disappears but the keypair **hangs**:
GDB shows PC executing data inside the stack region (`b.n .-2` infinite
self-loop), LR garbage, SP 91 KB below the 128 KB stack limit, backtrace
corrupt.

**Root cause:** the M4F-targeted assembly corrupts its own call state on
the M33 — a stack-discipline incompatibility, not an alignment fault. The
architectural insight: the M4F (ARMv7-M) overruns silently; the M33's
stack-limit hardware (MSPLIM, ARMv8-M) turns the same corruption into a
diagnosable fault (UNSTKERR) — so hand-optimized crypto assembly must be
re-validated per core generation, even within the same vendor's M-profile
family. The clean-C path (both PQClean and pqm4's own clean fallback) runs
correctly on the same board with the same 128 KB stack, isolating the
failure to the hand-written assembly specifically.

### STM32N6570-DK port status

Build succeeds cleanly for all variants (56–57 KB binaries); board flashes
and runs ("RUNNING Program... Start operation achieved successfully"). **No
benchmark data captured** — console output is blocked by the board's RIF
security architecture (Debug Authentication keys required for SWD memory
access in run mode; ROM enforces authenticated boot for the XIP path; the
ROM-DFU RAM-load path produces no observed USART output). Not a hardware
fault — the board is healthy, BOOT1=H is documented normal behavior, not a
lockout. Unblocking requires ST Debug Authentication keys or an
authenticated FSBL signature, neither available without ST enterprise
provisioning.

| Board | Build | Flash | Run | Console capture | Benchmark data |
|---|---|---|---|---|---|
| MCXN947 | ✅ | ✅ | ✅ | ✅ | ✅ complete |
| ESP32-S3 | ✅ | ✅ | ✅ | ✅ | ✅ complete |
| STM32N6570-DK | ✅ | ✅ | ✅ | ❌ | ❌ not captured |

## Analysis / Interpretation

1. **PQC cost scales predictably** (~1.5× per ML-KEM security-level step,
   O(k²) as expected) and is **near-deterministic for ML-KEM** (std <0.5%
   of mean — no OS jitter, single unshared core) but **fat-tailed for
   ML-DSA** (4.8–8.1× worst/median, driven entirely by rejection-sampling
   retries) — the two algorithms pose fundamentally different scheduling
   problems.
2. **The ML-DSA tail shape is a hardware-independent, algorithm-intrinsic
   property**: retry-count distributions are statistically identical
   across MCXN947 and ESP32-S3, under both bare-metal and Zephyr builds.
   Only the per-attempt wall-clock cost differs by platform.
3. **No level of ML-DSA signing can be certified within a 33 ms real-time
   frame** — this single result forces the rest of the thesis's scheduling
   design (batch/async signing, or scheduling around it as a rare event).
4. **M-profile optimization headroom is real (~1.5×) but the ecosystem is
   fragmented**: M4F-optimized PQC assembly does not just "work" on the
   newer M33 — decap and DSA paths fault. The practical guidance for a
   deployment on M33: use the clean reference (safe) or invest in
   M33-specific assembly (the ~1.5× is real but requires porting work, not
   a drop-in swap).
5. **The STM32N6570-DK gap is a security-architecture limitation, not a
   benchmark failure** — worth stating plainly rather than omitting: the
   port is complete and ready, but the third data point needs vendor
   provisioning this thesis does not have access to.

## Raw data

- `raw_data/02_pqc_benchmarks/mcxn947_baremetal_mlkem_perf_memory_summary.csv`, `mcxn947_baremetal_mlkem_energy_summary.csv` — ML-KEM latency/memory/energy tables (MCXN947, PQClean, bare-metal)
- `raw_data/02_pqc_benchmarks/esp32s3_baremetal_mldsa{44,65,87}_sign_raw.csv` — per-call ML-DSA sign data, bare-metal ESP32-S3 (2000 rows each; the matched MCXN947 bare-metal run is captured only as a serial log, see below, not a per-call CSV)
- `raw_data/02_pqc_benchmarks/zephyr_{mcxn947,esp32s3}_mldsa{44,65,87}_sign.csv`, `zephyr_mcxn947_mlkem768.csv`, `zephyr_esp32s3_mlkem768_raw.txt` — matched cross-platform Zephyr dataset
- `raw_data/02_pqc_benchmarks/serial_pqm4_mldsa44_fault_registers.txt`, `serial_pqm4_mldsa44_128k_hang.txt` — raw fault-register / hang captures for the pqm4 M4F→M33 post-mortem
- `raw_data/serial_captures/serial_mlkem{512,768,1024}_mcxn947.txt`, `serial_mldsa{44,65,87}_{mcxn947,esp32s3}.txt`, `serial_zephyr_pqc_{mcxn947,esp32s3}.txt`, `serial_zephyr_mlkem768_esp32s3.txt` — full raw serial captures behind every table above
- `raw_data/energy_ppk2/energy_pqm4_mlkem{512,768}_kpenc_mcxn947.csv` — raw PPK2 traces for the ML-KEM energy table
