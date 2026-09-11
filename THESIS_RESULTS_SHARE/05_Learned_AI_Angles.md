# 05 — Learned / Adaptive AI Angles: Learned Exit Policy, Joint Scheduler, Test-Time Conformal Adaptation

## Purpose

Three experiments push the certified-anytime system from hand-tuned rules
toward learned, data-driven ones, and honestly audit where learning does
and does not pay off: (1) can a learned exit policy beat the hand-tuned
certified menu without breaking certification; (2) can a joint
learned scheduler that picks both crypto security level and perception
exit beat treating them separately; (3) does the certified system's safety
coverage survive a real-world distribution shift, and is it worth building
a continuous-depth (LTC) model to squeeze out more efficiency.

## Setup / Method

**Protocol discipline (shared across all three):** training uses only the
calibration (5,850 images) and margin_val (3,990 images) splits; the
12,630-image test archive is touched only at final evaluation. The GTSRB
archives are fully partitioned (train+calibration+margin_val = the entire
39,209-image training archive; test = the entire separate test archive) —
there is no unused image anywhere to carve a second fresh holdout from.

## Results

### 5.1 Learned exit policy

For each frame, the policy observes the full confidence vector
(conf1,conf2,conf3) and picks the shallowest exit k whose **learned risk**
`risk_k(conf_k) = P(safety-critical AND wrong | conf_k)` is ≤ α=0.05, else
exit3. Risk curves are learned from calibration data as isotonic-decreasing
(PAVA) binned estimates per exit — replacing a single hand-tuned τ with a
data-driven function of confidence.

**Test evaluation (12,630 frames, 8,460 safety-critical), uncorrected
α=0.05 view:**

| policy | early-exit rate | SC miss (aggregate) | per-exit SC miss (accepted) | normalized latency |
|---|---|---|---|---|
| naive (always exit3) | 0% | 8.87% | exit3: 8.87% | 100% |
| static (τ₁=0.858) | 45.3% | 9.46% | exit1 ≈ 5% | 69.5% |
| **learned** | **85.0%** | **9.27%** | **exit1: 3.37%, exit2: 3.99%** | **54.5%** |

85% of frames exit early (1.9× more than static's 45%); perception latency
drops to 54.5% of naive (a further 22% reduction beyond static's 69.5%);
aggregate SC miss is statistically indistinguishable from naive
(8.87%→9.27%, Δ=+0.4pp).

**The double-touch correction (honest, not hidden):** the frozen 12,630-
image test set was used for two final evaluations — the frozen coverage
validation and this learned-policy evaluation — violating strict
single-touch conformal validity. Since no fresh holdout exists, the
Bonferroni correction is applied: effective α = 0.05/2 = **0.025**, with
thresholds read from the frozen calibration risk curves at their 0.025
crossing (τ₁=0.95, τ₂=0.95):

| exit | SC accepted | SC miss | α_eff = 0.025 | verdict |
|---|---|---|---|---|
| exit1 | 1,567 | **1.47%** | ≤ 2.5% | ✅ **certifies** |
| exit2 | 5,342 | **3.61%** | ≤ 2.5% | ❌ **does not certify** |

exit2 would certify at a stricter, non-pre-frozen τ₂=0.98 (2.22% ≤ 2.5%) —
reported only as an observation, not a certified claim, since that
threshold was never frozen in advance. **This does not contradict** the
earlier frozen-protocol finding that τ₂=0.815 fails at 5.17% — these are
different operating points on the same risk curve; the learned curves
located a *certifiable stricter* threshold, not a refutation. The
energy/latency numbers above are unaffected by this correction — they
measure compute, not certification.

### 5.2 Joint learned scheduler (security level + exit)

A single system decides, per unit of work, both which ML-KEM security
level to use for the next handshake (512/768/1024) and which perception
exit to stop at per frame, under a deadline+energy budget. The
security-level side uses the measured per-level cost directly (pick the
strongest level whose per-step cost still fits the deadline slot); the exit
side reuses the learned isotonic risk curves from §5.1. Trace-driven
simulation on real measured MCXN947 costs (exit 0.80/1.24/2.34 ms; ML-KEM-
512/768/1024 handshake 72.2/116.0/174.9 ms; per-handshake energy
4.20/6.63/9.76 mJ; 33 ms frame slot; crypto step every 10 frames; 3-slot
FIFO backlog), evaluated over the full 12,630-frame test + 3,990 margin_val:

| policy | security level | total time | energy | deadline misses | early-exit |
|---|---|---|---|---|---|
| naive | 768 fixed | 78.4 s | 3382 mJ | 70 | 0% |
| static | 768 fixed | 69.6 s | 3206 mJ | 70 | 45% |
| adaptive | 768 fixed | 67.9 s | 3173 mJ | 70 | 56% |
| **learned (joint)** | **512 under tight slot** | **45.9 s** | **2079 mJ** | **0** | **85%** |

**Time −41.4%, energy −38.5%, deadline misses 70→0**, with SC risk
unchanged (exit1 3.37%, exit2 3.99% — identical exit decisions to §5.1,
since the security-level change doesn't affect perception risk). The
dominant gain is the security-level decision: ML-KEM-768's per-step cost
(38.7 ms) exceeds the 33 ms slot, causing systematic misses; dropping to
512 (24.1 ms/step) fits the slot, eliminating all 70 misses and cutting
crypto time/energy ~1.6×. Exit-only learning (§5.1) cut energy ~8%; the
joint policy cuts 39% — the security-level decision is the larger lever
here. Caveats: trace-driven, not yet hardware-measured for the
level-switching side (the exit side is hardware-validated, see
`01_Anytime_Perception.md`); the 512-drop is a deliberate security-level
downgrade under deadline pressure, a policy choice the thesis states
explicitly rather than hiding.

### 5.3 Reconciling the two learning findings

| Finding | Domain | Result |
|---|---|---|
| RL gates (single-node + multi-node simulations, `06_Simulations.md`) | PQC security-level selection | Learning does NOT beat principled heuristics (gap ≈ 2.4%) |
| Learned exit policy (this document, hardware-evaluated) | Perception exit thresholds | Learning DOES beat the hand-tuned menu (85% vs 45% early exit; exit1 certifies at α_eff=0.025) |

**Why they differ:** crypto security-level selection is low-dimensional
with near-deterministic, measured costs — 3 discrete levels, each with a
known repeatable latency; the optimal choice (pick the lightest level that
fits the remaining budget) is analytically obvious, so a hand-rule
replicates the oracle and there is essentially nothing for learning to
discover. Exit thresholds are operating points on a rich, continuous
confidence distribution — the risk curve is smooth and non-obvious, and the
hand-tuned protocol approximated it with a single conservative margin;
learning has room to find a better operating point (as §5.1 shows). **The
coherent claim: learn the perception exit thresholds; a lookup over
measured costs suffices for crypto-level selection.**

### 5.4 Test-Time Conformal Adaptation (ACI) under distribution shift

**Question:** does Adaptive Conformal Inference (Gibbs & Candès 2021)
restore the certified classifier's coverage under an abrupt shift, and at
what cost? **Setup:** 1000-frame sequence from the frozen test archive,
frames 0–299 clean, 300–999 under an abrupt synthetic shift (brightness
×0.4 + Gaussian noise σ=25/255 — "tunnel + lens degradation"), run through
the deployed INT8 per-exit models on the PC reference. No test data was
used to build any threshold — τ(α) comes only from the calibration split.
Full multi-class conformal prediction sets per exit; per-exit ACI update
α_{t+1,k} = α_{t,k} + γ(α_target − 𝟙[miscovered]), γ=0.01. This is
explicitly framed as a **label-available offline audit** — real-time
on-device deployment has no labels; a proxy or delayed labels would be
needed there, stated as future work, not claimed as solved.

**Rolling set coverage (window 50):**

| segment | static conformal | **ACI (TTCA)** |
|---------|------------------|-----------------|
| clean 0–299 | 0.958 | 0.958 |
| **shift 300–699** | **0.486** | **0.939** |
| post 700–999 | 0.439 | **0.949** |
| **ALL** | **0.596** | **0.947** |

**The transient (honest — ACI is reactive, not predictive):**

| window after shift onset | static | ACI |
|--------------------------|--------|-----|
| t = 300–349 (first 50) | 0.600 | 0.860 |
| t = 400–499 | 0.400 | **0.950** |

α₁ drops from 0.061→0.011 within ~20 frames of the shift and coverage
recovers to 95% within ~100 frames; static stays at 40–51% for the rest of
the sequence.

**Cost and mechanism:**

| metric | static | ACI |
|--------|--------|-----|
| mean compute | 0.80 ms/frame | **0.83 ms/frame (+3.3%)** |
| mean set size | 4.78 classes (of 43) | **26.8 classes** |
| exit distribution (shift) | all exit1 | 399 exit1 / 1 exit2 |

**The safety margin under shift appears as prediction-set inflation, not
deeper exits**: α drops → τ rises → the prediction set grows (4.8→26.8 of
43 classes) → coverage is restored *at the shallow, cheap exit* (+3.3%
compute only). This is energy-favorable and is the mathematically correct
ACI behavior — a different mechanism than a binary "defer to deeper exits
under uncertainty" design would produce.

**Independently re-verified**: every number above is reproduced by a
from-scratch recomputation working only from the raw softmax/label
artifacts (no shared code with the original analysis) — all checks pass,
including softmax validity, the static/ACI rolling-coverage sequences, and
the Pareto-audit input accuracies below.

### 5.5 LTC Pareto go/no-go audit — is a continuous-depth model worth building?

**Question:** would a continuous Liquid-Time-Constant (LTC) model's
fine-grained anytime granularity justify the cost of a new training
pipeline, INT8 quantization of an ODE loop, a continuous certification
curve τ(k), and a second hardware port? The audit bounds the LTC's
*maximum possible* advantage using only measured data (no LTC was
trained).

**The measured discrete frontier:**

| exit | depth | compute (ms) | top-1 accuracy |
|------|-------|-------------|----------------|
| exit1 | 30% | 0.80 | 73.5% |
| exit2 | 60% | 1.24 | 92.2% |
| exit3 | 100% | 2.34 | 93.1% |

**Saturation fact:** exit2 captures **99.0% of exit3's accuracy at 53% of
the cost** — only +0.9pp of accuracy remains in the entire exit2→exit3
region. The LTC's only theoretical gain (reaching exit2-level accuracy
earlier than exit2's own cost) is conditional on unproven LTC
accuracy-per-MAC superiority, against a multi-week, high-risk investment
(new training pipeline, INT8 ODE quantization, τ(k) certification curve,
full hardware re-port).

**Verdict: NO-GO on training the LTC for efficiency.** The discrete 3-exit
model is the Pareto-optimal certified-anytime choice for this workload. A
cheaper alternative for finer granularity — adding 1–2 discrete exits
(e.g. 45%/75% depth) reusing the existing certification pipeline — is
available at days, not weeks, of effort, with every threshold certified by
the frozen protocol. The continuous-time τ(k) machinery remains a valid
theoretical contribution, demonstrable on the discrete model's exits,
without requiring the LTC itself to be built.

## Analysis / Interpretation

1. **Learning finds real, certifiable improvements on the perception
   side** (85% vs 45% early exit, a stricter-than-hand-tuned exit1
   threshold that actually certifies under correction) — but the honest
   double-touch correction downgrades exit2 from "certified" to "certified
   only at a stricter, non-pre-frozen threshold," which is reported
   plainly rather than as a clean win.
2. **The joint scheduler's biggest win comes from the low-dimensional
   crypto-level decision, not the learned exit side** — reinforcing §5.3's
   reconciliation with a concrete number (39% vs 8% energy reduction).
3. **TTCA/ACI is a genuine, quantified fix for exchangeability violation
   under shift** (coverage 48.6%→93.9%) at negligible compute cost, with
   its actual mechanism (set inflation at the cheap exit, not deeper
   exits) and its actual limitation (reactive lag, label-availability
   assumption) both stated explicitly.
4. **The Pareto audit is a disciplined "don't build it" result** — it
   uses only measured data to close off an entire planned research
   direction (the LTC), which is itself a useful, publishable finding: the
   discrete model already sits at the efficiency frontier for this task.

## Raw data

- `raw_data/05_learned_ai_angles/risk_curves.json` — learned isotonic per-exit risk curves (§5.1)
- `raw_data/05_learned_ai_angles/joint_scheduler_summary.csv` — full joint-scheduler results table (§5.2)
- `raw_data/05_learned_ai_angles/aci_softmax.npy`, `calib_softmax.npy`, `calib_labels.npy` — raw softmax/label arrays behind the TTCA/ACI analysis and its independent re-verification (§5.4)
- `raw_data/05_learned_ai_angles/ttca_stage1_summary.csv`, `ttca_stage1_plots.png` — TTCA Stage-1 summary table and coverage plots (§5.4)
- `raw_data/05_learned_ai_angles/stage3_pareto_audit.png` — the accuracy/compute frontier plot backing the go/no-go verdict (§5.5)
