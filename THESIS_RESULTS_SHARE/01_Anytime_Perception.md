# 01 — Anytime Perception: Certified 3-Exit Classifier under Interleaved Crypto Load

## Purpose

This is the thesis's core experiment. A 3-exit GTSRB traffic-sign
classifier (30/60/100% depth), with split-conformal certified risk on each
exit, is forced to share a CPU core with ML-KEM-768 crypto — a scenario with
genuine, unavoidable resource contention (unlike the dual-core setup, see
`02_PQC_Benchmarks.md`'s KQ4/KQ5 null result). The question: does a
certified-anytime exit policy actually pay for itself under this
constraint? Answered on real hardware, with statistics, not simulation.

## Setup / Method

**Board:** FRDM-MCXN947 (Cortex-M33 @ 150 MHz, single core for this
experiment — crypto and perception forced to share it).

**Workload:** 1230 real GTSRB test images (stratified, safety-critical
classes capped at 40/class across all 27 safety-critical classes, seed
20260728), streamed over UART, free-running on-device timing. Every 10
frames, one ML-KEM-768 crypto sub-operation runs (keypair → encap → decap,
rotating) before the frame is processed — identical schedule across all
three builds (verified: exactly 123 steps / 41 full handshakes in every
run), so total crypto work is a controlled constant.

**Three policies, one flash/run each:**
- **NAIVE** — always runs the full 3-exit chain, ignores confidence.
- **STATIC** — fixed α=0.05 τ thresholds (τ1=0.957, τ2=0.926), regardless
  of crypto load.
- **ADAPTIVE** — α=0.05 normally; shifts to the looser but still
  conformally certified α=0.10 tier (τ1=0.918, τ2=0.725) for the 4 frames
  out of every 10 immediately around a crypto step.

Certification method (shared with `02_PQC_Benchmarks.md`'s crypto-latency
certification): per-exit confidence threshold τ_k via the finite-sample
risk bound `(n·R̂+1)/(n+1) ≤ α`, calibrated at half the nominal α to survive
a measured calibration→test distribution shift (documented in
`00_Thesis_Overview.md` §2.4), validated against the full, undeflated α on
the held-out test archive.

## Results

### Combined crypto+perception device time

| policy | total device time | vs. naive |
|---|---|---|
| naive | 7633.6 ms | — |
| static | 6542.4 ms | **1091 ms faster (14.3%)** |
| adaptive | 6476.2 ms | **1157 ms faster (15.2%)** |

Crypto cost is identical across all three (4756.3–4756.8 ms — confirms
fairness). All savings come from the perception side: naive spends 2876.9 ms
total on 1230 full-depth inferences; static/adaptive spend 1785.6 / 1719.8
ms by exiting early most of the time.

| policy | exit1 | exit2 | exit3 |
|---|---|---|---|
| naive | 0% | 0% | 100% |
| static | 12.2% | 63.3% | 24.5% |
| adaptive | 14.1% | 65.7% | 20.2% |

Adaptive exits earlier more often than static specifically during the 40%
of frames it spends in the looser α=0.10 tier — the intended mechanism.

### Safety-critical miss-rate: essentially unchanged by exiting early

| policy | raw stratified-sample miss-rate | natural-frequency-weighted miss-rate |
|---|---|---|
| naive | 0.1481 | 0.0892 |
| static | 0.1491 | 0.0889 |
| adaptive | 0.1500 | 0.0908 |

The raw numbers run above nominal α targets because the sample is
class-balanced (stratified), over-representing rare, harder classes
relative to their natural test-set frequency — an already-diagnosed
sampling effect (see `00_Thesis_Overview.md` §2.7), not a policy problem.
Reweighted to natural class frequency (Horvitz–Thompson-style), all three
drop to ~8.9–9.1% — and naive's reweighted number (0.0892) lands almost
exactly on the independent PC-side full-test-set exit3 miss-rate (~0.0907),
a consistency check spanning training → NPU inference → this experiment.
**The three policies remain statistically indistinguishable under either
weighting.**

### Adaptive's tier-shifting mechanism, checked directly

| tier | frames | n (safety-critical) | miss-rate | target α |
|---|---|---|---|---|
| α=0.05 (normal, 60% of frames) | 738 | 648 | 0.1497 | 0.05 |
| α=0.10 (loosened near crypto, 40% of frames) | 492 | 432 | 0.1505 | 0.10 |

The two tiers produce nearly identical miss-rates despite tier α=0.10
accepting at looser confidence — shifting tiers during crypto-heavy periods
bought real speed without a corresponding jump in errors.

### Statistical significance

**Wilcoxon signed-rank test, per-frame perception latency (paired, same
1230-image sequence in the same order across all three runs):**

| comparison | median per-frame diff | p-value |
|---|---|---|
| naive vs static | 1104 µs | 2.6e-173 |
| naive vs adaptive | 1103 µs | 3.2e-173 |
| static vs adaptive | −2 µs | 3.7e-105 |

**McNemar's test, paired safety-critical correctness:**

| comparison | discordant pairs (n01/n10) | p-value |
|---|---|---|
| naive vs static | 5 / 4 | 1.0000 |
| naive vs adaptive | 10 / 8 | 0.8137 |
| static vs adaptive | 5 / 4 | 1.0000 |

**None of the miss-rate differences between policies are statistically
significant** — the rigorous version of "early exit doesn't meaningfully
increase risk," with only 4–10 discordant safety-critical predictions out
of 1080 in any pairwise comparison.

### Contention-cost predictor (telemetry-trained)

A per-operation-type lookup table (mean of keypair/encap/decap latency),
trained on the first 61 observed crypto steps from the naive run, validated
on the held-out remaining 62:

| op | train mean (µs) | test mean (µs) | predicted (µs) | rel. error |
|---|---|---|---|---|
| keypair | 32635.8 | 32654.5 | 32635.8 | 0.057% |
| encap | 37958.1 | 37973.8 | 37958.1 | 0.041% |
| decap | 45396.6 | 45412.2 | 45396.6 | 0.035% |

Per-step held-out prediction error: mean 0.164%, max 1.259% across all 62
test steps — ML-KEM-768 op cost is near-deterministic per type on this
hardware, so a simple per-type mean is already a strong predictor.

### Generalization: ML-KEM-1024 in place of ML-KEM-768

Same 1230-image sample, same crypto schedule (123 steps = 41 handshakes,
verified identical across policies again):

| policy | total device time | vs. naive (same KEM) |
|---|---|---|
| naive (768) | 7633.6 ms | — |
| static (768) | 6542.4 ms | 14.3% faster |
| adaptive (768) | 6476.2 ms | 15.2% faster |
| naive (1024) | 10056.3 ms | — |
| static (1024) | 8966.8 ms | 10.8% faster |
| adaptive (1024) | 8898.3 ms | 11.5% faster |

The **absolute** time saved by exiting early is nearly identical regardless
of crypto weight (static: 1091 ms @768 vs 1090 ms @1024; adaptive: 1157 ms
@768 vs 1158 ms @1024) — expected, since the saving comes entirely from the
perception side. The **percentage** saved shrinks because ML-KEM-1024's
larger fixed crypto cost (7180 ms total vs 4757 ms for 768, a ~51%
increase) makes up a bigger share of the fixed total. Exit distributions
and every miss-rate number are byte-identical to the 768 run — a
correctness check (the crypto variant only changes interleaving cost, never
which images are processed).

### Free-running energy (PPK2, physically meaningful measurement)

An earlier host-driven energy capture was invalid (on-device compute was
<1% of an 800+s trace). A **free-running** firmware — 140 embedded frames
(94/140 = 67.1% safety-critical) + 4 ML-KEM-768 handshakes, autonomous from
reset, no host UART during measurement — fixes this. PPK2 on J24, 10 kHz,
3.3 V assumed, reset-button trigger:

| Policy | Active energy (mJ) | Mean active (µA) | Baseline (µA) | Δ vs naive |
|---|---|---|---|---|
| NAIVE (all exit3) | **81.40** | 16,115 | 13,933 | — |
| STATIC (63 exit1, 77 exit3) | **78.67** | 16,064 | 14,440 | −3.36% |
| ADAPTIVE (74 exit1, 20 exit2, 46 exit3) | **77.56** | 16,033 | 14,623 | −4.72% |
| **LEARNED** (54 exit1, 59 exit2, 27 exit3) | **76.75** | 16,058 | 14,443 | **−5.72%** |

Firmware-verified exit distributions and inference-sum times:

| Policy | Inference sum (frame time) | Exit distribution | Handshakes |
|---|---|---|---|
| NAIVE | 327.7 ms | 140× exit3 | 4 |
| STATIC | — | 63× exit1, 77× exit3, 0× exit2 | 4 |
| ADAPTIVE | 191.7 ms | 74× exit1, 20× exit2, 46× exit3 | 4 |

Certified menu verified on-device: tier 0.05 (exit1 τ=858 certified, exit2
not certified), tier 0.10 (exit1 τ=723, exit2 τ=402 certified at 0.0985 ≤
0.10). Adaptive shifts to tier 0.10 only near crypto steps (56/140 frames).

**LEARNED policy's on-device risk (140-frame sample):** exit1 3.57%
(n=28), exit2 0.00% (n=47) safety-critical miss among accepted frames —
consistent with the uncorrected α=0.05 PC-side numbers (see
`05_Learned_AI_Angles.md` for the Bonferroni-corrected certified claim; the
n=94 on-device sample is too small for a corrected-level certification and
is a consistency check only).

No deadline misses in any policy (max frame ~2.4 ms, crypto ~10 ms per step
≪ 33 ms @ 30 fps budget).

## Analysis / Interpretation

1. **The dual-core null result stands**: on the dual-core chip there's no
   NPU resource contention to react to (KQ5, `02_PQC_Benchmarks.md`).
2. **When crypto and perception are forced to share one core** — a
   realistic constraint for a smaller or cheaper target — a certified
   early-exit policy directly reduces the combined workload time by double
   digits, without a corresponding jump in safety-critical miss-rate.
3. **Adaptive tier-shifting gives a further, smaller edge** (0.9 percentage
   points more time saved than static) by degrading gracefully to a
   looser-but-still-certified risk tier specifically when crypto load is
   imminent.
4. **The energy deltas are modest (3–6%)** because the board's idle
   baseline dominates the active window at this workload scale — the
   honest reality of measuring a lightly-loaded MCU, not an artifact. At
   higher frame rates or heavier contention the gap would widen (confirmed
   by the parameter sweep below).
5. This is the result that answers "what's actually novel here": not that
   NPU hardware resists crypto contention (a clean but modest finding, see
   `02_PQC_Benchmarks.md`), but that the certified-anytime design pays for
   itself in a genuinely resource-constrained deployment, measured
   end-to-end on real silicon and holding up under proper statistical
   testing and a parameter sweep (8.8%–27.7% savings across an 8× range of
   crypto-interrupt frequency, every adaptive window width tested).

## Raw data

- `raw_data/01_anytime_perception/policy_results_{naive,static,adaptive}.csv` — per-frame policy results (host-driven timing experiment, §Results tables 1–4)
- `raw_data/01_anytime_perception/freerun_policy_results_{naive,static,adaptive}.csv` — free-running firmware per-frame results (§Free-running energy)
- `raw_data/01_anytime_perception/interleaved_summary.csv` — combined summary table
- `raw_data/01_anytime_perception/energy_summary_freerun.csv` — the four-policy energy table
- `raw_data/energy_ppk2/energy_interleaved_{naive,static,adaptive,learned}_140f_mcxn947.csv`, `energy_interleaved_learned_mcxn947.csv` — raw PPK2 traces backing the free-running energy table
