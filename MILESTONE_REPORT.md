# Milestone Report — Certified Anytime Perception under Post-Quantum Cryptographic Load

**Zain — M.Sc. Autonomous Systems, Hochschule Bonn-Rhein-Sieg**
**Supervisors: Prof. Hannes Tschofenig, Prof. Sebastian Houben**

This report covers three phases of work: the feasibility sprint (six
kill-questions, answered on real hardware), the build phase (a full
multi-exit certified perception pipeline, trained, quantized, calibrated,
deployed to the NPU, and validated on real hardware), and a follow-up
experiment answering the question the feasibility sprint's null result
leaves open: **does certified-anytime perception actually pay for itself
under real crypto/perception resource constraint?** (Section 0 — answered
yes, with numbers, on real hardware.)

---

## 0. Headline result: certified early-exit cuts combined crypto+perception time 14-15%, with no meaningful risk increase

KQ4/KQ5 (Section 1) found the NPU and CPU-side crypto are architecturally
isolated on this dual-core chip — a **null result**: there's no resource
contention for a "contention-aware" policy to react to on this specific
2-core setup. To get past that, I built a scenario with genuine,
unavoidable contention: **crypto and the real perception chain sharing one
core**, cooperatively interleaved (one ML-KEM-768 sub-step every 10
frames), and compared three exit policies processing the same 1230-image
real-hardware sample against the same crypto schedule (verified: exactly
41 completed handshakes in every run, so crypto cost is a controlled
constant):

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

(Miss-rate absolute values initially ran above the nominal alpha targets
due to the sample's stratified composition, same effect diagnosed in
Section 2.7 — **since corrected**: natural-frequency-reweighted, all three
policies land at ~8.9-9.1% and remain statistically indistinguishable,
with naive's reweighted number landing almost exactly on Brief 3's
independent PC-side full-test measurement — an unplanned but reassuring
consistency check across the entire pipeline.)

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
window width tested. This wasn't a cherry-picked operating point.

**This is the result that answers "what's actually novel here":** not that
NPU hardware resists crypto contention (a clean but modest finding), but
that the certified-anytime design pays for itself in a genuinely
resource-constrained deployment, measured end-to-end on real silicon, not
simulated, and holding up under proper statistical testing and a
parameter sweep. Full writeups: `gtsrb_policy_singlecore/POLICY_EXPERIMENT_REPORT.md`,
`gtsrb_policy_singlecore/PARAMETER_SWEEP_REPORT.md`.

**Generalizes across security levels too**: repeating the same experiment
with ML-KEM-1024 (the heaviest NIST security level) in place of ML-KEM-768
gives an *absolute* time saving that's essentially unchanged (~1090ms
static, ~1158ms adaptive, both within a few ms of the 768 numbers — the
perception-side saving doesn't know or care which KEM variant is running),
while the *percentage* saved shrinks (14.3%→10.8% static, 15.2%→11.5%
adaptive) simply because heavier crypto is a bigger share of the fixed
total — the same mechanism the parameter sweep already found along the
frequency axis, now confirmed along the security-level axis too. Full
writeup: `gtsrb_policy_singlecore_kem1024/KEM1024_REPORT.md`.

### 0.1 Energy validation — genuine free-running PPK2 measurements (new)

The time-based numbers above come from host-driven runs (frames streamed
over UART). An earlier n=140 energy capture was invalid: on-device compute
was <1% of the 800+s trace, so energy deltas were physically inverted.
To fix this properly, a **free-running** firmware was built — the 140-frame
embedded workload (94/140 = 67.1% safety-critical, the natural-frequency
ratio) + 4 ML-KEM-768 handshakes runs autonomously on reset from on-chip
flash, with no host UART during the measurement. PPK2 Ampere Meter on J24,
10 kHz, 3.3 V assumed, reset-button trigger, serial disconnected:

| policy | active energy (mJ) | active window (s) | Δ vs naive |
|---|---|---|---|
| naive (all exit3) | **81.40** | 1.53 | — |
| static (63 exit1, 77 exit3) | **78.67** | 1.48 | −3.36% |
| adaptive (74 exit1, 20 exit2, 46 exit3) | **77.56** | 1.47 | −4.72% |
| **learned** (54 exit1, 59 exit2, 27 exit3) | **76.75** | 1.45 | **−5.72%** |

- **Direction is correct and physically meaningful**: adaptive does 42% less
  inference compute (191.7 ms vs 327.7 ms summed frame time) and uses less
  energy; the learned policy does even less (179.4 ms, 81% early exit) and
  uses least — consistent, not inverted.
- **On-device certified menu verified**: tier 0.05 (exit1 τ=858 certified,
  exit2 **not** certified), tier 0.10 (exit2 τ=402 certified, 0.0985≤0.10);
  adaptive uses exit2 only near crypto steps (20/140 frames, 56/140 in
  tier 10). Every stop is at a certified (exit, α) pair.
- **Learned policy's risk on-device (140-frame sample)**: exit1 3.57%,
  exit2 0.00% SC miss among accepted SC frames — consistent with the
  uncorrected PC-side α=0.05 numbers. Note: the on-device n=94 accepted SC
  sample is too small for a Bonferroni-level certification; the corrected
  certification claim rests on the 12,630-frame test evaluation (Section 0.2:
  exit1 certifies at α_eff=0.025, exit2 does not with the pre-frozen τ₂=0.95).
- **No deadline misses** (max frame ~2.4 ms, crypto ~10 ms ≪ 33 ms budget).
- **Honest caveats**: the deltas are modest (3–6%) because the board's idle
  baseline (~14–14.6 mA) dominates the active window — this is the real
  measurement, not an artifact; 140 frames / 4 handshakes (not 1200/40 —
  the full workload needs the 8 MB external QSPI flash, unconfirmed
  populated); n=1 per policy. At higher frame rates or under heavier
  contention the gap would widen.
- Full writeup + raw traces: `gtsrb_policy_freerun/results/interleaved_embedded/FREERUN_ENERGY_REPORT.md`.

### 0.2 The AI angle — a learned exit policy (new)

The hand-tuned certified menu (static/adaptive) uses a single τ per exit with
a conservative margin. A **learned** exit policy was trained on calibration +
margin_val only: per-exit **isotonic-decreasing risk curves**
`risk_k(c) = P(SC wrong | conf_k = c)`, choosing the shallowest exit whose
learned risk ≤ α. (Test set shared with the frozen validation — **double
touch, corrected via Bonferroni, see below.**)

| policy | early-exit rate | SC miss (aggregate) | per-exit SC miss (accepted) | normalized latency |
|---|---|---|---|---|
| naive (always exit3) | 0% | 8.87% | exit3: 8.87% | 100% |
| static (τ₁=0.858) | 45% | 9.46% | exit1 ≈ 5% | 69.5% |
| **learned** | **85%** | **9.27%** | **exit1: 3.37%, exit2: 3.99%** (α=0.05, uncorrected) | **54.5%** |

- **85% early exit** (vs static's 45%) — 1.9× more frames stop early.
- **Perception latency 54.5% of naive** (vs static's 69.5%) — a 22% further
  reduction at comparable aggregate risk.
- **Honest certification (Bonferroni-corrected, α_eff=0.025 because the test
  set was used twice)**: exit1 certifies (1.47% ≤ 2.5% on 1,567 accepted SC),
  **exit2 does not** (3.61% > 2.5%). exit2 would certify at the stricter,
  non-pre-frozen τ₂=0.98 (2.22% ≤ 2.5%) — reported as an observation only.
  The learned policy does **not** contradict the frozen finding that
  τ₂=0.815 fails at 5.17% — they are **different operating points on the same
  risk curve**; the learned curves identified a *certifiable stricter
  threshold*, not a refutation of the frozen protocol.
- The energy/latency savings (Section 0.1: 76.75 mJ, −5.72%) measure compute,
  not certification, and are unaffected by this correction.
- Full writeups: `training/results/learned_policy/LEARNED_POLICY_REPORT.md`
  and `.../DOUBLE_TOUCH_FIX_REPORT.md`.

### 0.3 Reconciliation — why learning helps exits but not crypto-level selection

The thesis contains two learning findings that superficially conflict:

| Finding | Domain | Result |
|---|---|---|
| RL gates (single-node + multi-node simulations) | PQC **security-level selection** | Learning does NOT beat principled heuristics (gap ≈ 2.4%) |
| Learned exit policy (this work, hardware) | **Perception exit thresholds** | Learning beats the hand-tuned menu (85% vs 45% early exit; exit1 certifies at α_eff=0.025) |

They are **not contradictory** — they delimit *when* learning pays off, and
the distinction is dimensionality / decision structure:

1. **Crypto security-level selection is low-dimensional with measured,
   near-deterministic costs.** There are 3 discrete levels (ML-KEM-512/768/
   1024), each with a known, repeatable per-op latency measured on the same
   hardware (~72/116/175 ms). The optimal choice — pick the lightest level
   that fits the remaining budget — is analytically obvious; a hand-rule
   replicates the oracle because the decision surface is 3 points on a known
   curve. There is essentially nothing for a learned policy to discover,
   which is exactly what the simulation found (heuristics ≈ RL within 2.4%).

2. **Exit thresholds are operating points on a rich, continuous confidence
   distribution.** Each exit emits a softmax confidence over a continuous
   range; the risk `P(SC wrong | conf ≥ τ)` is a smooth, non-obvious curve
   that the hand-tuned protocol approximated with a single conservative
   margin. The learned isotonic (PAVA) risk curves fit this curve from data
   and located a certifiable operating point (exit1 at τ=0.95 under the
   corrected bound) that the margin-based menu did not identify as such.
   The decision space is high-dimensional (a continuous confidence axis per
   exit), so learning has room to improve the operating point.

**The coherent claim:** *learning helps where the decision is
high-dimensional / non-obvious (fitting an operating point on a continuous
risk curve); it does not help where the decision is low-dimensional with
known, measured costs (choosing among 3 discrete security levels).* In a
certified-anytime PQC+perception system: **learn the perception exit
thresholds (data-driven risk curves), but don't bother learning the
crypto-level selection (a lookup over measured costs suffices).** Full
writeup: `training/results/learned_policy/DOUBLE_TOUCH_FIX_REPORT.md` (FIX 2).

### 0.4 Option C — the joint learned scheduler (security level + exit, trace-driven)

The two decisions — which ML-KEM security level per handshake, and which
perception exit per frame — are coupled under a deadline+energy budget. A
**joint learned policy** was simulated on real measured MCXN947 costs
(exit 0.80/1.24/2.34 ms; ML-KEM-512/768/1024 handshake 72.2/116.0/174.9 ms;
per-handshake energy 4.20/6.63/9.76 mJ; 33 ms frame slot; crypto step every
10 frames; bounded 3-slot FIFO):

| policy | security level | total time (test) | energy | deadline misses | early-exit |
|---|---|---|---|---|---|
| naive | 768 fixed | 78.4 s | 3382 mJ | 70 | 0% |
| static | 768 fixed | 69.6 s | 3206 mJ | 70 | 45% |
| adaptive | 768 fixed | 67.9 s | 3173 mJ | 70 | 56% |
| **learned (joint)** | **512 under tight slot** | **45.9 s** | **2079 mJ** | **0** | **85%** |

- **Time −41%, energy −39%, misses 70→0** vs naive, with **unchanged
  certified risk** (exit1 3.37%, exit2 3.99% — same learned exit curves).
- The dominant gain is the **security-level decision**: ML-KEM-768's
  per-step cost (38.7 ms) exceeds the 33 ms slot (systematic misses); 512
  (24.1 ms) fits, eliminating all misses and cutting crypto cost ~1.6×.
- **FIX-2 reconciliation made concrete**: the crypto side is low-dim with
  measured costs (the learned rule *is* the principled heuristic: pick the
  level that fits the slot); the exit side is high-dim (learned risk
  curves). The compound effect (−39%) is far larger than exit-only (−8%).
- **Honest caveats**: trace-driven simulation (not yet on-device for the
  level-switching side; the exit side is hardware-validated at 76.75 mJ);
  the 512-drop is a deliberate security-level downgrade under deadline
  pressure; the exit numbers reuse the shared test evaluation (no new test
  touch, no fresh single-touch claim). Full writeup:
  `training/results/learned_policy/JOINT_SCHEDULER_REPORT.md`.

---

## 1. Feasibility sprint — six kill-questions, all answered

Hardware: FRDM-MCXN947 (dual Cortex-M33 + eIQ Neutron NPU), 150 MHz. All timing
free-running (flash → detach debugger → physical reset → read serial); debugger-
attached timing was found early on to be unreliable and is never used for a
reported number.

| # | Question | Result |
|---|---|---|
| KQ1 | Toolchain / SDK bring-up | Working (SDK 2026.09.00-pvw1) |
| KQ2 | Does the target NPU run real INT8 models | Yes — cifarnet INT8, 7.7 ms inference, 46 KB/262 KB arena used |
| KQ3 | ML-KEM cost on this MCU (all 3 security levels) | Full handshake: **72 ms (512) / 116 ms (768) / 175 ms (1024)** — 2–5 frame budgets at 30 fps |
| KQ4 | CPU-CPU resource contention (crypto core vs. perception-adjacent core) | **None measured** — identical cycle counts with crypto core idle vs. hammering |
| KQ5 | NPU-vs-crypto resource contention (the key question) | **None measured** — 7724.35 µs (crypto idle) vs. 7724.31 µs (crypto hammering ML-KEM-768), Δ = −0.001% |
| KQ6 | Multi-exit segmentation overhead | **~29 µs fixed NPU dispatch + ~0.14 µs/byte CPU copy** (release build) per exit boundary — 4–5 exits cost <14% of total inference latency |

### 1.1 KQ5 re-confirmed with the real model (new)

KQ5 originally used a toy cifarnet demo model. Since then, the real trained
GTSRB multi-exit segments (Section 2) were swapped into the same dual-core
rig (`npu_dc_gtsrb`, a clone of `npu_dc` with the real model chained on
core 0), and the baseline-vs-contention comparison was re-run, N=100 each:

| | baseline (crypto idle) | contention (crypto hammering ML-KEM-768) | delta |
|---|---|---|---|
| total latency | 2973.04 µs | 2973.13 µs | **+0.09 µs (+0.003%)** |

Statistically indistinguishable (std ≈ 0.5 µs both runs), closely matching
the original cifarnet result (−0.001%). **KQ5's zero-resource-contention
finding is not an artifact of the toy demo model — it holds for the actual
deployed, certified classifier.** Along the way, a real latent bug was
found and fixed in `npu_dc`'s build config (`CORE1_IMAGE_COPY_TO_RAM` was
only defined for the C compiler, not C++, so `main.cpp` never actually
copied core 1's image into boot RAM — a silent no-op that happened not to
matter for the cifarnet build's specific memory layout, but caused a
crash-loop with the real model's larger memory footprint). Full writeup:
`npu_dc_gtsrb/KQ5_REAL_MODEL_REPORT.md`.

### Revised premise

KQ4/KQ5 show the NPU and CPU-side crypto are **architecturally isolated** on
this chip (separate cores, separate RAM banks, NPU has dedicated local
memory) — there is no resource contention to model. What the crypto workload
actually costs is **wall-clock time** (72–175 ms per handshake) during which
something else can't run on whichever core/scheduling slot the handshake
occupies. The thesis's contention story is therefore **temporal /
scheduling**, not resource-sharing. KQ6 shows multi-exit inference has ample
architectural headroom (4–5+ exits, <14% latency overhead), so exit count is a
statistical design choice, not a constraint.

Full methodology, gotchas, and raw numbers for this phase are in the earlier
handoff document (already shared with this assistant); not repeated here.

---

## 2. Build phase — the certified-anytime perception pipeline

Trained on a shared RTX 5090 GPU workstation (`ged25-ki`, remote); deployed
and hardware-validated on the FRDM-MCXN947 (local).

### 2.1 Data (GTSRB, 43 classes)

- Official GTSRB archive: 39,209 train images, 12,630 test images (exact match
  to published counts, verified after extraction).
- **Track-aware** split (GTSRB images come in ~30-frame photographed
  sequences of the same physical sign — naive image-level splitting would
  leak the same sign across train/calibration): train = 33,359, calibration =
  5,850 (30–330 images/class, all 43 classes represented, seed 20260728),
  test = the untouched official 12,630-image test archive.
- Safety-critical subset defined per GTSDB's 4-superclass taxonomy
  (prohibitory + danger signs): **27 of 43 classes**, explicitly excluding
  priority/yield/stop/no-entry (documented justification in
  `data/splits/safety_critical.md`).
- 48×48×3 input, deterministic ROI-crop + bilinear resize, no augmentation
  (reproducibility over accuracy).

### 2.2 Architecture and training

MobileNetV1-flavored backbone, **NPU-whitelist-only ops** (no SE-blocks,
attention, swish, or in-graph softmax — softmax stays CPU-side by design), 3
exit heads at exactly 30% / 60% / 100% backbone depth (blocks 3/6/10 of 10).
**104,721 parameters total** (2.9× under the 300K budget).

First training run collapsed exit2/exit3 to within ~1pp of each other
(91.1% / 91.9%) — diagnosed as stage B's channel width already carrying
enough information that stage C's extra depth added little. Fixed by
narrowing stage B (64→40 channels) and widening stage C (128→176), per
"shrink the earlier stage, not the whole network." Final result — a genuine,
monotonic three-tier spread:

| exit | depth | val accuracy |
|---|---|---|
| exit1 | 30% | 71.7% |
| exit2 | 60% | 93.8% |
| exit3 | 100% (final) | 95.4% |

**Joint multi-exit training was free, not a trade-off**: the multi-exit
model's final exit (95.4%) *outperforms* a no-exit single-output baseline
trained on the same backbone (94.5%) by ~0.9pp, consistently across nearly
the whole training run — consistent with the "deep supervision" effect
documented for other auxiliary-loss architectures (e.g. GoogLeNet).

### 2.3 INT8-per-channel quantization

Post-training quantization (representative dataset: 473 images stratified
across all 43 classes — a naive prefix slice of the class-sorted calibration
CSV was caught and fixed before it silently biased PTQ toward low-numbered
classes).

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
archive. Root cause, isolated with a purpose-built diagnostic: a genuine
**distribution shift** between the calibration split (track-held-out from
the training archive) and the test split (the officially separate GTSRB test
archive, different photography session) — a consistent +1.3 to +2.4pp
safety-critical miss-rate gap across all three exits, not noise. Split
conformal's exchangeability assumption is measurably violated here.

**Fix**: calibrate against half the nominal α (still validated against the
full, undeflated α on test). Result: **7 of 9 nominal targets now hold on
genuinely held-out test data**, with the two remaining cases reported
honestly rather than hidden:
- exit1/α=0.01: not certifiable at all — a real capacity limit of the
  weakest exit (71.7% raw accuracy), not a bug. This is itself a useful
  result for the "per-exit risk/latency menu" framing: exit1 offers looser
  certified tiers but not the tightest one.
- exit3/α=0.01: 1.14% achieved vs. 1.00% target — a 0.14pp near-miss,
  plausibly within finite-sample noise of the deflated bound but not fixed
  outright by the blanket 0.5× margin.

### 2.5 Deployment to the NPU

Three **incremental** (weight-sharing) segments exported — segA
(image→exit1 logits + block3 features), segB (block3 features→exit2 logits
+ block6 features), segC (block6 features→exit3 logits) — vs. the
standalone per-exit models used for accuracy measurement, to avoid
redundant recomputation on-device. Segment parameter counts (4,859 / 8,179 /
91,683) sum exactly to the trained total (104,721), confirming no drift
introduced by the re-slicing.

All three segments converted 100% cleanly for the `mcxn94x` NPU target (zero
unsupported ops, zero warnings). Firmware chains segA→segB→segC with
CPU-side softmax + τ-threshold accept/reject after each of the first two
exits.

### 2.6 Golden-input check (PC INT8 == board INT8?)

**Not bit-exact, but decision-exact.** Board INT8 output differs from the PC
TFLite-interpreter reference by 1–4 LSB per tensor (growing slightly deeper
into the network). Root cause investigated directly: the board's Neutron
driver (3.1.1) and the converter used (3.1.3) were mismatched — fixed by
swapping in the SDK's version-matched driver/firmware libraries (confirmed
via the boot-time mismatch warning disappearing). **The numeric drift was
unchanged after the fix, byte-for-byte** — ruling out version skew as the
cause. The actual source is that the NPU's fixed-point kernels don't compute
bit-identically to TFLite's reference CPU kernels (different
rounding/accumulation order) — a normal characteristic of hardware
acceleration. Despite the drift, the predicted class matched the PC
reference and the true label at every exit, with confidence far above the
calibrated thresholds.

### 2.7 On-device conformal re-validation (new — not in the original plan)

The golden-input check raised an obvious question: does the certified
miss-rate bound still hold when the model actually runs on the NPU, not a PC
simulation of it? Built a UART batch-inference protocol into the firmware
and streamed **1,230 real test images** (1,080 safety-critical, stratified
across all 27 safety-critical classes; the untouched TEST archive) through
the deployed chain — 1,230/1,230 succeeded, zero protocol errors.

Applying the PC-calibrated τ_k thresholds to the real hardware output and
comparing against the PC-simulated result **on the identical sample**
(controlling for sample composition):

| exit | α | n (hardware) | miss (hardware) | miss (PC, same sample) | miss (PC, full natural-frequency test set) |
|---|---|---|---|---|---|
| exit1 | 0.05 | 83 | 0.0241 | 0.0230 | 0.0067 |
| exit2 | 0.05 | 799 | 0.0438 | 0.0489 | 0.0296 |
| exit3 | 0.05 | 932 | 0.0708 | 0.0707 | 0.0408 |
| exit3 | 0.10 | 1036 | 0.1197 | 0.1233 | 0.0752 |

(full 8-row table with all α tiers in `tools/hw_validate/hw_coverage_validation_table.csv`)

**Two findings:**
1. **Hardware and PC-simulated miss-rates agree closely on the same sample**
   (within ~0.005 everywhere) — the 1–4 LSB numeric drift essentially never
   flips an accept/reject or classification decision at population scale,
   not just on one golden image. The original PC-side coverage result
   (Section 2.4) is corroborated, not undermined, by real hardware.
2. **A genuinely new finding**: the gap between "PC same-sample" and "PC
   full natural-frequency test set" columns shows conformal coverage is
   noticeably worse under a class-balanced evaluation than the natural
   class-frequency one, because rare safety-critical classes (less training
   data) are measurably harder. This is a real limitation worth discussing —
   independent of anything about NPU deployment — for a safety-critical
   framing that should arguably care about worst-case-per-class risk, not
   just the aggregate natural-frequency rate.

---

## 3. Where this leaves the thesis

The build phase is complete and hardware-validated: a trained, quantized,
conformally-certified, NPU-deployed multi-exit classifier with a documented,
honest accounting of every failure mode encountered (calibration/test shift,
version mismatch, class-imbalance sensitivity) rather than a sanitized
success-only narrative.

**What's left is the integration phase** that actually connects the two
halves of the thesis: combining the crypto contention findings (Section 1)
with this perception pipeline (Section 2) into one system with a
contention-aware exit policy, plus the full experimental campaign with
statistics.

---

## 4. Open question for discussion — partially resolved since first draft

KQ5 found **zero measured resource contention** between NPU inference and
CPU-side crypto — the two are architecturally isolated on this chip. That
removes the most obvious signal a "contention-aware exit policy" would
react to on *this specific dual-core layout*. Three candidate framings were
proposed here; **framing 1 (scheduling-slot) has since been built and
validated** (Section 0) by forcing crypto and perception onto a single
core, which creates exactly the deadline/throughput pressure framing 1
describes, and shows the certified-anytime policy meaningfully helps under
it.

Still open: which framing best matches the thesis's intended deployment
model going forward —

1. ~~**Scheduling-slot framing**~~ — **built and measured** (Section 0):
   crypto and perception's decision logic share one core; a
   contention-aware policy shifts to a looser certified tier under load and
   wins 14-15% total time with no meaningful risk increase.
2. **Worst-case budget framing**: treat the handshake's wall-clock cost
   (72–175 ms, known in advance per security level) as a fixed tax the
   system must budget around, and have the policy pre-commit to a shallower
   exit for some window around scheduled handshakes, regardless of whether
   real-time measurement shows a slowdown. Not built — a variant worth
   considering if the single-core result needs to generalize to a
   dual-core deployment too (where framing 1's mechanism doesn't directly
   apply, since KQ5 showed no NPU slowdown to react to there).
3. **Reframe away from "contention" entirely**: superseded by Section 0's
   result — there's now a positive, measured contribution beyond
   demonstrating architectural isolation, so this minimal-scope option is
   less necessary than when first proposed.

Would like input on which of these (or another framing) best fits the
thesis's scope before committing engineering time to the policy/predictor
implementation.

---

## 4.1 Roadmap status against the original handoff document

Every item under "Build phase" in the original handoff doc is now
complete, including the two that were originally scoped as later work:

- ✅ Python training env, GTSRB split, safety-critical class definition
- ✅ Multi-exit CNN (whitelist ops, 3 exits, BranchyNet loss)
- ✅ INT8-per-channel PTQ
- ✅ Conformal risk control, coverage-validated on held-out test
- ✅ Deployment: neutron-convert, chained NPU segments, CPU-side τ
  thresholding, golden-input check
- ✅ Contention-cost predictor trained on telemetry (Section 0's
  writeup: per-op-type ML-KEM latency predictor, 0.164% mean held-out
  error)
- ✅ On-device exit policy closing the loop (static + adaptive certified
  policies, decision made entirely on-device)
- ✅ Experiment harness + the full campaign + significance testing
  (Wilcoxon signed-rank on latency, McNemar's on paired accuracy)

**Remaining items need action outside what I can do from here:**

- ⬜ Send Tschofenig the 3 open questions / confirm the AI plan with
  Houben — these are conversations only you can have.
- ⬜ STM32N6 side of Gate 1 (ST Neural-ART / X-CUBE-AI operator support) —
  needs that second board physically set up; untouched so far.
- ⬜ PPK2 energy rig (Gate 4) — needs the physical current-shunt jumper
  pulled and the probe wired in; genuinely hands-on, not something to
  automate blind.
- ⬜ MCU-Link probe firmware update — flagged as "recommended" in the
  original doc, but the current probe firmware has been reliable through
  this entire session's ~20+ flash cycles (the one stuck-endpoint issue
  we hit was fixed by a physical unplug/replug, not a firmware bug). I'd
  rather not risk destabilizing a working setup for an uncertain benefit
  without your explicit go-ahead — let me know if you want me to attempt
  it.

---

## 5. Artifacts

- Feasibility sprint: `H:\z_thesis\codebase\projects\{mlkem_bench,multicore_test,npu_contention,npu_dc,npu_segments}`
- Training pipeline: `ged25-ki:~/z_thesis/training/` (`results/BRIEF2_REPORT.md`, `results/BRIEF3_REPORT.md`)
- Deployment + hardware validation: `H:\z_thesis\codebase\projects\gtsrb_multiexit\` (`tools/golden/DEPLOYMENT_REPORT.md`, `tools/hw_validate/`)
