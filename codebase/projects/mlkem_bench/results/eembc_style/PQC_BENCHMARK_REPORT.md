# EEMBC-Style ML-KEM Benchmark Results — Performance & Memory

Methodology: `BENCHMARK_METHODOLOGY.md` (same directory tree, one level
up). Board: NXP FRDM-MCXN947, Cortex-M33 @ 150 MHz, single core, PQClean
`clean` reference implementation. All runs free-running (no debugger
attached), 100 repetitions per operation per variant, `kem_match=1`
(correctness verified) on every run.

## 1. Performance (cycle count → time)

| variant | operation | mean cycles | std cycles | mean time (μs) | std as % of mean |
|---|---|---|---|---|---|
| ML-KEM-512 | keypair | 2,978,432 | 14,156 | 19,856.2 | 0.48% |
| ML-KEM-512 | encaps | 3,503,918 | 14,157 | 23,359.5 | 0.40% |
| ML-KEM-512 | decaps | 4,342,471 | 14,156 | 28,949.8 | 0.33% |
| ML-KEM-768 | keypair | 4,893,951 | 18,548 | 32,626.3 | 0.38% |
| ML-KEM-768 | encaps | 5,692,464 | 18,549 | 37,949.8 | 0.33% |
| ML-KEM-768 | decaps | 6,809,160 | 18,549 | 45,394.4 | 0.27% |
| ML-KEM-1024 | keypair | 7,644,704 | 23,209 | 50,964.7 | 0.30% |
| ML-KEM-1024 | encaps | 8,582,539 | 23,211 | 57,216.9 | 0.27% |
| ML-KEM-1024 | decaps | 10,008,989 | 23,210 | 66,726.6 | 0.23% |

Standard deviation stays below 0.5% of the mean throughout — expected for
a deterministic algorithm on a single, unshared core with no OS
scheduling noise (no jitter source to produce wider variance).

**Full handshake (keypair + encaps + decaps, summed means):**

| variant | handshake time |
|---|---|
| ML-KEM-512 | 72.17 ms |
| ML-KEM-768 | 115.97 ms |
| ML-KEM-1024 | 174.91 ms |

These numbers **independently cross-validate** the earlier feasibility-sprint
(KQ3) measurements from a separate benchmark run (~72 / 116 / 175 ms) —
agreement to within 0.2 ms despite being a completely separate flash/run
cycle, strong evidence the timing methodology is sound and reproducible.

**Scaling factor per security level** (mean of the three per-op ratios):
512→768 ≈ 1.61×, 768→1024 ≈ 1.53× — consistent with ML-KEM's polynomial
dimension scaling (512 uses k=2, 768 uses k=3, 1024 uses k=4 module rank;
roughly O(k²) cost for the dominant matrix-vector operations, so ~1.5×
per step is the theoretically expected order of magnitude, not a surprise).

## 2. Memory: peak stack usage (high-water-mark)

| variant | operation | stack HWM (bytes) | % of 32 KiB region |
|---|---|---|---|
| ML-KEM-512 | keypair | 8,960 | 27.3% |
| ML-KEM-512 | encaps | 11,592 | 35.4% |
| ML-KEM-512 | decaps | 12,344 | 37.7% |
| ML-KEM-768 | keypair | 13,056 | 39.8% |
| ML-KEM-768 | encaps | 16,200 | 49.4% |
| ML-KEM-768 | decaps | 17,272 | 52.7% |
| ML-KEM-1024 | keypair | 18,176 | 55.5% |
| ML-KEM-1024 | encaps | 21,832 | 66.6% |
| ML-KEM-1024 | decaps | 23,384 | 71.4% |

**Consistent pattern across all three variants**: decapsulation uses the
most stack, then encapsulation, then keypair generation — decaps
internally re-runs part of the encapsulation path (for the
Fujisaki-Okamoto re-encryption check central to ML-KEM's CCA security),
so its deeper call stack is expected from the algorithm's own structure,
not an implementation inefficiency.

**Headroom**: even the worst case (ML-KEM-1024 decaps, 23,384 bytes)
leaves ~28.6% of the 32 KiB stack region unused — comfortable margin on
this target, but a genuinely useful number for anyone considering a
smaller-RAM target: ML-KEM-1024 alone would need a stack region of at
least ~23 KB, before accounting for anything else the application does.

## 3. Memory: code size (flash + static RAM)

| variant | code (flash, bytes) | static data (RAM, bytes) |
|---|---|---|
| ML-KEM-512 | 41,648 | 40,928 |
| ML-KEM-768 | 41,432 | 42,400 |
| ML-KEM-1024 | 41,944 | 44,032 |

Flash usage is nearly flat across variants (~41.4-41.9 KB) — expected,
since all three security levels share the same PQClean `clean` source
structure and the compiler generates similar code regardless of the
`params.h`-driven size constants. Static RAM usage grows modestly with
security level (~1.5 KB per step) — attributable to the differently-sized
public-key/secret-key/ciphertext buffers declared in `hello_world.c`
(larger security level → larger keys/ciphertexts), not to any change in
the crypto library's internal working-memory footprint.

## 4. Energy

Measured for all three variants. Full methodology, wiring procedure, and
caveats: `BENCHMARK_METHODOLOGY.md` Section 6. Two caveats apply to
every number below and must not be dropped when citing them:

1. **Voltage assumed (3.3V), not measured** — PPK2 Ammeter mode is a
   passive current pass-through and does not report the DUT's actual
   rail voltage.
2. **Per-operation split is a modeling assumption** (energy allocated
   proportionally to each operation's share of DWT cycles), not read
   from hardware-verified per-op boundaries — the GPIO trigger pin
   intended for that purpose has not been observed to toggle in any
   capture on record; see the methodology doc for what was ruled out.

ML-KEM-512 was captured on two independent physical boards (agreement
within ~3%, good reproducibility evidence); 768/1024 were captured on
board B only, after board A developed an unrelated hardware SWD fault
(see methodology doc).

| Variant | Board | Idle baseline | Active window (100 reps) | Total energy | Per-handshake |
|---|---|---|---|---|---|
| ML-KEM-512 | A | 13.45 mA | 7.95s | 414.08 mJ | 4140.8 µJ |
| ML-KEM-512 | B | 14.20 mA | 7.97s | 426.13 mJ | 4261.3 µJ |
| ML-KEM-768 | B | 14.06 mA | 12.32s | 662.89 mJ | 6628.9 µJ |
| ML-KEM-1024 | B | 14.21 mA | 18.19s | 975.84 mJ | 9758.4 µJ |

**Per-operation energy (proportional cycle-count split; ML-KEM-512 uses the mean of both boards):**

| variant | operation | % of total cycles | energy/op |
|---|---|---|---|
| ML-KEM-512 | keypair | 27.51% | ~1156 µJ |
| ML-KEM-512 | encaps | 32.37% | ~1360 µJ |
| ML-KEM-512 | decaps | 40.12% | ~1685 µJ |
| ML-KEM-768 | keypair | 28.13% | 1864.9 µJ |
| ML-KEM-768 | encaps | 32.73% | 2169.2 µJ |
| ML-KEM-768 | decaps | 39.14% | 2594.8 µJ |
| ML-KEM-1024 | keypair | 29.14% | 2843.4 µJ |
| ML-KEM-1024 | encaps | 32.71% | 3192.2 µJ |
| ML-KEM-1024 | decaps | 38.15% | 3722.8 µJ |

**Scaling**: per-handshake energy grows 512→768→1024 in roughly the same
proportion as the timing numbers from Section 1 (~1.6× then ~1.47×) —
expected, since mean active current stays in a narrow 14-17 mA band
across all three variants (more cycles at similar power draw per cycle,
not a fundamentally different power profile per security level).

**Artifacts**: `energy/mlkem{512_boardA,512_boardB,768_boardB,1024_boardB}_raw.csv`
(raw PPK2 exports), `analyze_energy.py` (analysis script, documents the
active-window detection and both caveats above in its docstring),
`energy_summary.csv` (generated output).

## 5. A transparent, non-official weighted summary

**This is not an EEMBC SecureMark score** — the real committee's
per-operation weights are not public, and this benchmark targets ML-KEM
rather than SecureMark-TLS's classical-crypto suite. This section is
offered only as one legitimate way to compress the table above into a
single comparative number per variant, with the weighting explicitly
stated so a reader can disagree with it and recompute their own.

**Weighting used**: equal weight per operation (1/3 each) — the simplest
defensible choice, since a real deployment doing repeated key exchanges
performs each operation roughly once per handshake (see
Section 1's "full handshake" table, which is really the same idea without
any weighting question at all — arguably the more honest headline number).

| variant | mean handshake time (equal-weighted) | peak stack (max of 3 ops) | code+data size | mean handshake energy |
|---|---|---|---|---|
| ML-KEM-512 | 24,055.2 μs/op | 12,344 B | 82,576 B | ~4201 µJ (mean of 2 boards) |
| ML-KEM-768 | 38,656.8 μs/op | 17,272 B | 83,832 B | 6628.9 µJ |
| ML-KEM-1024 | 58,302.7 μs/op | 23,384 B | 85,976 B | 9758.4 µJ |

Energy column carries the same two caveats as Section 4 (assumed 3.3V,
proportional-split modeling for the per-op breakdown feeding this
handshake total) — the handshake total itself is a direct
charge-integration measurement, not modeled, so it's on firmer footing
than the per-op breakdown.

## Artifacts

- `mlkem{512,768,1024}_raw.txt` — raw UART capture, 100 reps × 3 ops each,
  free-running, `kem_match=1` confirmed
- `perf_memory_summary.csv` — parsed summary table (this report's source data)
- `analyze_perf_memory.py` — the parsing/analysis script (rerun to regenerate)
- `energy/mlkem{512_boardA,512_boardB,768_boardB,1024_boardB}_raw.csv` —
  raw PPK2 Ampere-meter exports (see Section 4)
- `analyze_energy.py` / `energy_summary.csv` — energy analysis script and
  generated summary
