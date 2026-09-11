# Stage 1 — Test-Time Conformal Adaptation (TTCA/ACI) on the Certified 3-Exit Model

**Question:** Does Adaptive Conformal Inference (Gibbs & Candès 2021) restore
the 95% safety coverage of the certified anytime classifier under an abrupt
distribution shift — and at what compute/energy cost?

**Setup (matches the proposal's Phase 1):** a 1000-frame navigation sequence
from the frozen GTSRB test archive: frames 0–299 clean, frames 300–999 under
an abrupt synthetic shift (brightness ×0.4 + Gaussian noise σ=25/255, i.e.
"tunnel + lens degradation"). The deployed INT8 per-exit tflite models (the
same binaries on the hardware) were run on the PC reference to produce full
43-class softmax per exit per frame. **No test data was used to build any
threshold** — τ(α) comes only from the calibration split (frozen protocol).

**Method:** true multi-class conformal prediction sets per exit k:
Ĉ_{t,k} = {y : 1 − f_{t,k}(y) ≤ τ_k(α_{t,k})}, with τ_k(α) the split-conformal
quantile of calibration non-conformity (linearized around α=0.05 with the
measured slope dτ/dα<0). Per-exit ACI: α_{t+1,k} = α_{t,k} + γ(α_target −
𝟙[Y_t ∉ Ĉ_{t,k}]), γ=0.01. The anytime menu uses the shallowest exit whose
running α is at/below target (band ±2γ). Static baseline: the same sets at
fixed τ(α=0.05).

## Results

### 1. Rolling set coverage (window 50) — the headline

| segment | static conformal | **ACI (TTCA)** |
|---------|------------------|----------------|
| clean 0–299 | 0.958 | 0.958 |
| **shift 300–699** | **0.486** | **0.939** |
| post 700–999 | 0.439 | **0.949** |
| **ALL** | **0.596** | **0.947** |

### 2. The transient (honest — ACI is reactive, not predictive)

| window after shift onset | static | ACI |
|--------------------------|--------|-----|
| t = 300–349 (first 50) | 0.600 | 0.860 |
| t = 300–399 | 0.510 | 0.890 |
| t = 400–499 | 0.400 | **0.950** |
| t = 500–699 | 0.455 | **0.950** |

α₁ drops from 0.061 → 0.011 within ~20 frames of the shift (the feedback
fires on the first miscoverages) and the coverage recovers to 95% within
~100 frames. Static stays at 40–51% for the rest of the sequence.

### 3. Cost and mechanism

| metric | static | ACI |
|--------|--------|-----|
| mean compute | 0.80 ms/frame | **0.83 ms/frame (+3.3%)** |
| mean set size | 4.78 classes | **26.8 classes** |
| exit distribution (clean) | all exit1 | 241 exit1 / 59 exit2 |
| exit distribution (shift) | all exit1 | 399 exit1 / 1 exit2 |

## Findings (and the three proposal-fix confirmations)

1. **Static conformal fails exactly as the proposal predicts**: coverage
   collapses 95.8% → 48.6% under shift. This is the exchangeability
   violation, measured.
2. **ACI restores coverage to 94–95%** through the shift (48.6% → 93.9%),
   with a quantified reactive lag (~86% in the first 50 frames, 95% by
   frame 400). It does **not** prevent the transient — it recovers from it
   (the Gibbs–Candès guarantee is marginal tracking, not per-point).
3. **The safety margin appears as SET INFLATION, not deeper exits** (the
   honest correction to the proposal's narrative): under shift α drops → τ
   rises → the prediction set grows (4.8 → 26.8 of 43 classes) → coverage is
   restored **at the shallow, cheap exit** (+3.3% compute). This is the
   mathematically correct ACI behavior and it is *energy-favorable*: the
   anytime menu keeps exit1. A binary accept/defer variant (defer to deeper
   exits under shift) is a separate design; the set-based one is the one the
   ACI formula in the proposal actually describes.
4. **Labels are required** (𝟙[Y_t ∈ Ĉ]): this Stage-1 evaluation is an
   offline audit with labels (the frozen test archive). On-device deployment
   needs a proxy or delayed labels — stated, not hidden.
5. **τ re-derivation confirmed necessary**: the per-exit τ(α) curve (not a
   single threshold) is what makes ACI work; the slopes are large
   (exit3: dτ/dα ≈ −12), so a continuous model would need exactly this
   curve — the Stage-2 machinery.

## Files

- `conformal/aci_shift_predict.py` — remote prediction (clean+shift through
  the INT8 reference; `--calib` dumps the calibration softmax)
- `conformal/ttca_aci.py` — the ACI simulation + plots
- `results/ttca/aci_softmax.npy`, `calib_softmax.npy`, `calib_labels.npy`,
  `aci_seq_1000.csv`, `ttca_stage1_summary.csv`, `ttca_stage1_plots.png`

## Verification (independent recomputation)

Every number above is reproduced by , which
re-implements the entire pipeline from the raw artifacts ONLY (softmax
arrays, label files, prediction CSVs) and does NOT import the analysis
scripts. Run: `python conformal/verify_ttca.py` → **ALL CHECKS PASS**:

- softmax validity: sum-to-1 within 3e-7
- model facts: exit3 clean 0.9167 / shifted 0.3586 (matches the remote log)
- tau(0.05): 0.9773 / 0.8827 / 0.8694; slopes -0.705 / -8.351 / -12.267
- static rolling coverage: 0.9583 / 0.4859 / 0.4387 / 0.5957
- ACI rolling coverage: 0.9583 / 0.9390 / 0.9490 / 0.9473
- ACI exit distributions: clean [241,59,0], shift [399,1,0]
- Pareto audit inputs: exit accuracies 0.7349 / 0.9215 / 0.9308
