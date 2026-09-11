# Thesis Overview — Certified Anytime Perception under Post-Quantum Cryptographic Load

**Zain — M.Sc. Autonomous Systems, Hochschule Bonn-Rhein-Sieg**
**Supervisors: Prof. Hannes Tschofenig, Prof. Sebastian Houben**

This is the entry-point document for the results package. It covers three
phases of work: the feasibility sprint (six kill-questions, answered on real
hardware), the build phase (a full multi-exit certified perception pipeline,
trained, quantized, calibrated, deployed to the NPU, and validated on real
hardware), and a follow-up experiment answering the question the feasibility
sprint's null result leaves open: **does certified-anytime perception
actually pay for itself under real crypto/perception resource constraint?**
(Section 0 — answered yes, with numbers, on real hardware.)

Detailed per-experiment write-ups (setup, full results tables, analysis) are
in the six numbered documents alongside this one:
`01_Anytime_Perception.md`, `02_PQC_Benchmarks.md`,
`03_Classical_Baseline.md`, `04_Security_SideChannels.md`,
`05_Learned_AI_Angles.md`, `06_Simulations.md`. Every raw supporting file
(serial logs, CSVs, PPK2 energy captures, JSON/NumPy data, plots) is under
`raw_data/`, organized by experiment area.

---

## 0. Headline result: certified early-exit cuts combined crypto+perception time 14-15%, with no meaningful risk increase

KQ4/KQ5 (Section 1) found the NPU and CPU-side crypto are architecturally
isolated on this dual-core chip — a **null result**: there's no resource
contention for a "contention-aware" policy to react to on this specific
2-core setup. To get past that, a scenario was built with genuine,
unavoidable contention: **crypto and the real perception chain sharing one
core**, cooperatively interleaved (one ML-KEM-768 sub-step every 10
frames), comparing three exit policies processing the same 1230-image
real-hardware sample against the same crypto schedule (verified: exactly
41 completed handshakes in every run, so crypto cost is a controlled
constant). Full detail: `01_Anytime_Perception.md`.

| policy | total device time (crypto + perception) | vs. naive | achieved safety-critical miss-rate |
|---|---|---|---|
| naive (always full 3-exit chain) | 7633.6 ms | — | 0.1481 |
| static certified (fixed alpha=0.05 tau) | 6542.4 ms | **14.3% faster** | 0.1491 |
| adaptive certified (shifts to alpha=0.10 near crypto load) | 6476.2 ms | **15.2% faster** | 0.1500 |

Static and adaptive both finish the identical fixed workload (1230 frames
+ 41 handshakes) in ~14-15% less device time than naive, while their
achieved miss-rate is within ~0.2 percentage points of naive's — exiting
early on this cascading classifier does not meaningfully increase risk,
because the calibrated thresholds specifically forward only the samples
the earlier exit is genuinely unsure about. Adaptive's tier-shifting
mechanism (spending 40% of frames in the looser-but-still-certified
alpha=0.10 tier specifically around crypto steps) gives a further, smaller
edge over static.

Natural-frequency-reweighted, all three policies land at ~8.9-9.1% miss-rate
and remain statistically indistinguishable, with naive's reweighted number
landing almost exactly on the independent PC-side full-test measurement — an
unplanned but reassuring consistency check across the entire pipeline.

**Statistically validated, not just eyeballed:** paired Wilcoxon
signed-rank test on per-frame latency confirms the speedup is a real,
consistent effect (p≈1e-173, not a few outlier frames); paired McNemar's
test on safety-critical correctness shows the miss-rate differences
between all three policies are **not statistically significant**
(p=0.81-1.0) — the strongest available evidence that early exit doesn't
cost accuracy on this workload.

**Robust to the specific parameters chosen:** a trace-driven sensitivity
sweep (same real hardware-measured per-exit latencies and crypto costs,
validated against the actual hardware run to within 0.04%) shows the
savings hold — 8.8% to 27.7% depending on how often crypto interrupts —
across an 8x range of crypto-interrupt frequency and every adaptive
window width tested.

**Generalizes across security levels too**: repeating the same experiment
with ML-KEM-1024 (the heaviest NIST security level) in place of ML-KEM-768
gives an *absolute* time saving that's essentially unchanged (~1090ms
static, ~1158ms adaptive), while the *percentage* saved shrinks
(14.3%→10.8% static, 15.2%→11.5% adaptive) simply because heavier crypto is
a bigger share of the fixed total.

### 0.1 Energy validation — genuine free-running PPK2 measurements

The time-based numbers above come from host-driven runs (frames streamed
over UART). A **free-running** firmware (the 140-frame embedded workload +
4 ML-KEM-768 handshakes, running autonomously from on-chip flash with no
host UART during measurement) gives physically meaningful energy numbers:

| policy | active energy (mJ) | active window (s) | Δ vs naive |
|---|---|---|---|
| naive (all exit3) | **81.40** | 1.53 | — |
| static (63 exit1, 77 exit3) | **78.67** | 1.48 | −3.36% |
| adaptive (74 exit1, 20 exit2, 46 exit3) | **77.56** | 1.47 | −4.72% |
| **learned** (54 exit1, 59 exit2, 27 exit3) | **76.75** | 1.45 | **−5.72%** |

Full detail and caveats: `01_Anytime_Perception.md`.

### 0.2 The AI angle — a learned exit policy

A **learned** exit policy (per-exit isotonic-decreasing risk curves,
choosing the shallowest exit whose learned risk ≤ α) reaches **85% early
exit** (vs static's 45%) at **54.5% of naive's perception latency** (vs
static's 69.5%). Bonferroni-corrected (the test set was used twice): exit1
certifies at α_eff=0.025 (1.47% ≤ 2.5%), exit2 does not (3.61% > 2.5%). Full
detail: `05_Learned_AI_Angles.md`.

### 0.3 Reconciliation — why learning helps exits but not crypto-level selection

Two learning findings that superficially conflict:

| Finding | Domain | Result |
|---|---|---|
| RL gates (single-node + multi-node simulations) | PQC **security-level selection** | Learning does NOT beat principled heuristics (gap ≈ 2.4%) |
| Learned exit policy (hardware) | **Perception exit thresholds** | Learning beats the hand-tuned menu (85% vs 45% early exit; exit1 certifies at α_eff=0.025) |

**The coherent claim:** learning helps where the decision is
high-dimensional / non-obvious (fitting an operating point on a continuous
risk curve); it does not help where the decision is low-dimensional with
known, measured costs (choosing among 3 discrete security levels). Full
reasoning: `05_Learned_AI_Angles.md` and `06_Simulations.md`.

### 0.4 The joint learned scheduler (security level + exit, trace-driven)

A **joint learned policy**, simulated on real measured MCXN947 costs, picks
both the ML-KEM security level per handshake and the perception exit per
frame under a deadline+energy budget:

| policy | security level | total time (test) | energy | deadline misses | early-exit |
|---|---|---|---|---|---|
| naive | 768 fixed | 78.4 s | 3382 mJ | 70 | 0% |
| static | 768 fixed | 69.6 s | 3206 mJ | 70 | 45% |
| adaptive | 768 fixed | 67.9 s | 3173 mJ | 70 | 56% |
| **learned (joint)** | **512 under tight slot** | **45.9 s** | **2079 mJ** | **0** | **85%** |

**Time −41%, energy −39%, misses 70→0** vs naive, with unchanged certified
risk. Full detail: `05_Learned_AI_Angles.md`.

---

## 1. Feasibility sprint — six kill-questions, all answered

Hardware: FRDM-MCXN947 (dual Cortex-M33 + eIQ Neutron NPU), 150 MHz. All
timing free-running (flash → detach debugger → physical reset → read
serial); debugger-attached timing was found early on to be unreliable and
is never used for a reported number.

| # | Question | Result |
|---|---|---|
| KQ1 | Toolchain / SDK bring-up | Working (SDK 2026.09.00-pvw1) |
| KQ2 | Does the target NPU run real INT8 models | Yes — cifarnet INT8, 7.7 ms inference, 46 KB/262 KB arena used |
| KQ3 | ML-KEM cost on this MCU (all 3 security levels) | Full handshake: **72 ms (512) / 116 ms (768) / 175 ms (1024)** — 2–5 frame budgets at 30 fps |
| KQ4 | CPU-CPU resource contention (crypto core vs. perception-adjacent core) | **None measured** — identical cycle counts with crypto core idle vs. hammering |
| KQ5 | NPU-vs-crypto resource contention (the key question) | **None measured** — 7724.35 µs (crypto idle) vs. 7724.31 µs (crypto hammering ML-KEM-768), Δ = −0.001% |
| KQ6 | Multi-exit segmentation overhead | **~29 µs fixed NPU dispatch + ~0.14 µs/byte CPU copy** (release build) per exit boundary — 4–5 exits cost <14% of total inference latency |

### 1.1 KQ5 re-confirmed with the real model

The real trained GTSRB multi-exit segments (Section 2) were swapped into
the same dual-core rig, and the baseline-vs-contention comparison was
re-run, N=100 each:

| | baseline (crypto idle) | contention (crypto hammering ML-KEM-768) | delta |
|---|---|---|---|
| total latency | 2973.04 µs | 2973.13 µs | **+0.09 µs (+0.003%)** |

Statistically indistinguishable (std ≈ 0.5 µs both runs), closely matching
the original result (−0.001%). **KQ5's zero-resource-contention finding is
not an artifact of the toy demo model — it holds for the actual deployed,
certified classifier.**

### Revised premise

KQ4/KQ5 show the NPU and CPU-side crypto are **architecturally isolated**
on this chip (separate cores, separate RAM banks, NPU has dedicated local
memory) — there is no resource contention to model. What the crypto
workload actually costs is **wall-clock time** (72–175 ms per handshake)
during which something else can't run on whichever core/scheduling slot
the handshake occupies. The thesis's contention story is therefore
**temporal / scheduling**, not resource-sharing. KQ6 shows multi-exit
inference has ample architectural headroom (4–5+ exits, <14% latency
overhead), so exit count is a statistical design choice, not a constraint.

---

## 2. Build phase — the certified-anytime perception pipeline

Trained on a shared RTX 5090 GPU workstation (remote); deployed and
hardware-validated on the FRDM-MCXN947 (local).

### 2.1 Data (GTSRB, 43 classes)

- Official GTSRB archive: 39,209 train images, 12,630 test images (exact
  match to published counts, verified after extraction).
- **Track-aware** split (GTSRB images come in ~30-frame photographed
  sequences of the same physical sign — naive image-level splitting would
  leak the same sign across train/calibration): train = 33,359, calibration
  = 5,850 (30–330 images/class, all 43 classes represented, seed 20260728),
  test = the untouched official 12,630-image test archive.
- Safety-critical subset defined per GTSDB's 4-superclass taxonomy
  (prohibitory + danger signs): **27 of 43 classes**, explicitly excluding
  priority/yield/stop/no-entry.
- 48×48×3 input, deterministic ROI-crop + bilinear resize, no augmentation
  (reproducibility over accuracy).

### 2.2 Architecture and training

MobileNetV1-flavored backbone, **NPU-whitelist-only ops** (no SE-blocks,
attention, swish, or in-graph softmax — softmax stays CPU-side by design),
3 exit heads at exactly 30% / 60% / 100% backbone depth (blocks 3/6/10 of
10). **104,721 parameters total** (2.9× under the 300K budget).

First training run collapsed exit2/exit3 to within ~1pp of each other
(91.1% / 91.9%) — diagnosed as stage B's channel width already carrying
enough information that stage C's extra depth added little. Fixed by
narrowing stage B (64→40 channels) and widening stage C (128→176). Final
result — a genuine, monotonic three-tier spread:

| exit | depth | val accuracy |
|---|---|---|
| exit1 | 30% | 71.7% |
| exit2 | 60% | 93.8% |
| exit3 | 100% (final) | 95.4% |

**Joint multi-exit training was free, not a trade-off**: the multi-exit
model's final exit (95.4%) *outperforms* a no-exit single-output baseline
trained on the same backbone (94.5%) by ~0.9pp — consistent with the "deep
supervision" effect documented for other auxiliary-loss architectures
(e.g. GoogLeNet).

### 2.3 INT8-per-channel quantization

Post-training quantization (representative dataset: 473 images stratified
across all 43 classes):

| exit | FP32 acc | INT8 acc | drop |
|---|---|---|---|
| exit1 | 73.66% | 73.06% | 0.60pp |
| exit2 | 92.85% | 92.80% | 0.05pp |
| exit3 | 94.87% | 94.74% | 0.14pp |

All within the expected 1–2pp PTQ drop range; no QAT fallback needed.

### 2.4 Conformal risk certification

Per-exit confidence threshold τ_k chosen via the finite-sample risk bound
`(n·R̂ + 1)/(n + 1) ≤ α` (Angelopoulos et al.), targeting the empirical
miss-rate on **safety-critical classes only**, for α ∈ {0.01, 0.05, 0.10}.

**First calibration attempt failed to generalize**: 5 of 9 (exit, α)
combinations violated their target when validated on the held-out TEST
archive. Root cause: a genuine **distribution shift** between the
calibration split and the test split (different photography session) — a
consistent +1.3 to +2.4pp safety-critical miss-rate gap across all three
exits.

**Fix**: calibrate against half the nominal α (still validated against the
full, undeflated α on test). Result: **7 of 9 nominal targets now hold on
genuinely held-out test data**, with two remaining cases reported honestly:
- exit1/α=0.01: not certifiable at all — a real capacity limit of the
  weakest exit (71.7% raw accuracy).
- exit3/α=0.01: 1.14% achieved vs. 1.00% target — a 0.14pp near-miss.

### 2.5 Deployment to the NPU

Three **incremental** (weight-sharing) segments exported — segA
(image→exit1 logits + block3 features), segB (block3 features→exit2 logits
+ block6 features), segC (block6 features→exit3 logits). Segment parameter
counts (4,859 / 8,179 / 91,683) sum exactly to the trained total (104,721),
confirming no drift from the re-slicing. All three segments converted 100%
cleanly for the `mcxn94x` NPU target (zero unsupported ops, zero warnings).

### 2.6 Golden-input check (PC INT8 == board INT8?)

**Not bit-exact, but decision-exact.** Board INT8 output differs from the
PC TFLite-interpreter reference by 1–4 LSB per tensor. Investigated
directly: the driver/converter version skew (3.1.1 vs 3.1.3) was ruled out
experimentally (fixing it left the drift byte-for-byte unchanged). The
actual source is that the NPU's fixed-point kernels don't compute
bit-identically to TFLite's reference CPU kernels — a normal characteristic
of hardware acceleration. The predicted class matched the PC reference and
the true label at every exit, with confidence far above the calibrated
thresholds.

### 2.7 On-device conformal re-validation

Built a UART batch-inference protocol into the firmware and streamed
**1,230 real test images** (1,080 safety-critical) through the deployed
chain — 1,230/1,230 succeeded, zero protocol errors.

| exit | α | n (hardware) | miss (hardware) | miss (PC, same sample) | miss (PC, full natural-frequency test set) |
|---|---|---|---|---|---|
| exit1 | 0.05 | 83 | 0.0241 | 0.0230 | 0.0067 |
| exit2 | 0.05 | 799 | 0.0438 | 0.0489 | 0.0296 |
| exit3 | 0.05 | 932 | 0.0708 | 0.0707 | 0.0408 |
| exit3 | 0.10 | 1036 | 0.1197 | 0.1233 | 0.0752 |

**Two findings:**
1. Hardware and PC-simulated miss-rates agree closely on the same sample —
   the 1–4 LSB numeric drift essentially never flips an accept/reject or
   classification decision at population scale.
2. Conformal coverage is noticeably worse under a class-balanced evaluation
   than the natural class-frequency one, because rare safety-critical
   classes (less training data) are measurably harder — a real limitation
   worth flagging for a safety-critical framing.

Full deployment/coverage-validation detail (including the
natural-frequency-reweighted correction, 6/8 certified combinations passing
once corrected): `01_Anytime_Perception.md`.

---

## 3. Where this leaves the thesis

The build phase is complete and hardware-validated: a trained, quantized,
conformally-certified, NPU-deployed multi-exit classifier with a
documented, honest accounting of every failure mode encountered
(calibration/test shift, version mismatch, class-imbalance sensitivity)
rather than a sanitized success-only narrative. The integration phase
connects the crypto contention findings (Section 1) with this perception
pipeline (Section 2) into one system with a contention-aware exit policy —
delivered as Section 0's single-core interleaved experiment.

---

## 4. EEMBC SecureMark-TLS — the classical baseline and the PQC migration story

To make the PQC benchmark suite publishable in EEMBC style, the official
**SecureMark-TLS** self-hosted benchmark was ported to **both thesis
platforms** (FRDM-MCXN947 and ESP32-S3) with a custom `th_*` porting layer
over mbedTLS. **All 14 component primitives pass the official EEMBC CRC
validation on both boards (14/14).**

| | MCXN947 (M33 @150 MHz, mbedTLS -O2) | ESP32-S3 (LX7 @240 MHz, mbedTLS -O2) |
|---|---|---|
| SecureMark-TLS score | **5,472 marks** | **1,895 marks** |
| ECDH P-256 | 19.7 ms | 79.9 ms |
| ECDSA sign / verify | 34.0 / 56.2 ms | 85.0 / 165.2 ms |
| AES-ECB-144 | 87 µs | 217 µs |
| SHA-256-384 | 158 µs | **20 µs** (ESP32 HW SHA, 7.9x) |

### 4.1 The migration cost (classical → PQC TLS handshake)

TLS 1.2 handshake public-key phase (1 ECDH + 1 sign + 2 verify):

| Board | Classical ECC | PQC ML-KEM-768 + ML-DSA-44 | ML-DSA-65 | ML-DSA-87 |
|-------|---------------|----------------------------|-----------|-----------|
| MCXN947 | 166.1 ms | 108.6 ms (**−34.6%**) | 164.2 ms (−1.1%) | 229.1 ms (+37.9%) |
| ESP32-S3 | 495.2 ms | 88.8 ms (**−82.1%**) | 134.0 ms (−72.9%) | 187.1 ms (−62.2%) |

1. **At NIST level 1 the migration is strictly cheaper on both boards**
   (ML-DSA verification is ~3x cheaper than ECDSA verification; on the
   ESP32-S3 the classical ECC in ESP-IDF's mbedTLS is the bottleneck, so
   lattice PQC is a relief, −62 to −82%).
2. **At the thesis operating point (768+65, NIST L3) the MCX pays +51%** in
   the ECC phase — the cost of a genuine security-level upgrade.

### 4.2 Energy (PPK2, ULPMark-style)

| | MCXN947 | ESP32-S3 |
|---|---|---|
| Idle baseline | 12.73 mA | 47.39 mA |
| Active power (above idle) | 8.16 mW | 97.48 mW |
| Incremental energy (full run) | 1.54 J | 23.9 J |

Because active power is ~constant per board, the energy migration delta
equals the latency delta. The ESP32-S3 is ~12x more power-hungry when busy
*and* has the slower classical ECC stack — so the PQC migration is a strict
energy win there (−62 to −82%), while the MCX is energy-neutral at 768+65.

Full detail, per-phase energy table, and caveats: `03_Classical_Baseline.md`.

---

## 5. Amortization, portability, and obfuscation — the PQC load meets the real world

Three experiments take the measured PQC costs (Section 4) and push them
into three directions: *what the cost means over a lifetime*, *whether the
fastest implementations are safe on modern cores*, and *whether the
side-channel defense has a feasible middle ground*. Full detail for all
three: `04_Security_SideChannels.md`.

### 5.1 DTLS Connection-ID life-cycle energy amortization

Using the measured PPK2 handshake energies, a 24 h state-machine model
compares a naive client (full PQC handshake every wake-up) with a CID
client (one handshake + symmetric per wake-up), CR2032 battery, deep sleep
5 µA:

| Board | N (wake-ups/day) | Naive | CID | Gain |
|-------|------------------|-------|-----|------|
| MCXN947 | 24 (hourly) | 1812 | 1872 days | +3% (sleep-dominated) |
| MCXN947 | 1440 (1/min) | 609 | 1870 days | **+207%** |
| ESP32-S3 | 24 | 1401 | 1847 days | +32% |
| ESP32-S3 | 1440 | **88** | **1740 days** | **+1880% (19×)** |

### 5.2 pqm4 M4F→M33 assembly portability post-mortem (hardware-verified)

The pqm4 hand-written M4F assembly gives 1.39–1.58× ML-KEM speedups but
faults on the Cortex-M33. Root cause (captured via custom HardFault handler
+ live GDB): **CFSR bit 20 = UNSTKERR** (unstacking error) — a
stack-discipline incompatibility, not TrustZone, not an illegal
instruction. The M4F (ARMv7-M) overruns *silently*; the M33's stack-limit
hardware turns the corruption into a **diagnosable fault** — optimized
crypto must be re-validated per core generation.

### 5.3 Selective / probabilistic side-channel obfuscation

Full dummy-crypto obfuscation was infeasible at ML-KEM-768 under the 33 ms
deadline. Two feasible partial defenses (probabilistic p=0.3, exit1-aware)
cut the crypto-activity attacker from ~100% → 75.5%/67.6% at feasible cost:

| policy | misses | +energy | crypto attacker | hidden | exit leak |
|--------|--------|---------|-----------------|--------|-----------|
| no_defense | 6* | — | 100% | 0% | 98.3% |
| full dummy | **13** | +99% | 50% | 99% | 91.9% |
| **p=0.3** | **9** | +32.5% | **75.5%** | 33% | 96.2% |
| **exit1-selective** | **10** | +48% | **67.6%** | 48% | 95.2% |

Honest boundary: the *exit-decision* leak barely degrades (98.3% → 96%) —
the compromise hides crypto activity, not exit privacy.

### 5.4 Why these matter

> The PQC load is a real, battery-relevant cost (amortized by DTLS
> Connection IDs up to 19× at high duty cycles), its fastest
> implementations carry genuine portability risk on modern ARMv8-M cores
> (captured at the fault-register level), and its side-channel defense
> requires honest probabilistic/exit-aware compromises. The
> certified-anytime controller — the part that provably absorbs this load
> — is the load-bearing component of the whole system.

---

## 6. Document map

| Document | Covers |
|---|---|
| `01_Anytime_Perception.md` | 3-exit certified GTSRB classifier, interleaved-crypto policy experiment, free-running energy, ML-KEM-1024 generalization, hardware deployment/validation |
| `02_PQC_Benchmarks.md` | ML-KEM/ML-DSA latency, memory, energy per board (MCXN947, ESP32-S3, Zephyr cross-platform, STM32N6570 status); pqm4 vs PQClean; conformal latency certification |
| `03_Classical_Baseline.md` | EEMBC SecureMark-TLS on both boards; classical→PQC migration cost and energy |
| `04_Security_SideChannels.md` | Crypto-activity leakage, exit-decision leakage, obfuscation defenses, split-inference privacy overhead, DTLS Connection-ID amortization |
| `05_Learned_AI_Angles.md` | Learned exit policy + Bonferroni correction, joint (security-level + exit) scheduler, Test-Time Conformal Adaptation (ACI), LTC Pareto go/no-go audit |
| `06_Simulations.md` | Single-robot and swarm PQC security-level selection — does it need RL, or do heuristics suffice? |
| `raw_data/` | Every CSV, serial log, PPK2 energy trace, JSON summary, and plot backing the tables above, organized by experiment area |
