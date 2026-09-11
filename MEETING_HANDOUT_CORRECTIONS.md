# Meeting Handout — AI-Extension Corrections (for Prof. Tschofenig & Prof. Houben)

*Companion to the pqc-anytime proposal v5 and the Stage-1 results. Three
corrections to the LNN+TTCA proposal, each now backed by measured results.*

---

## Correction 1 — TTCA is evaluated as a label-available offline audit (the deployment claim is scoped)

**Proposal as written:** ACI updates α_{t+1} = α_t + γ(α − 𝟙[Y_t ∉ Ĉ_t]) using
the miscoverage indicator — which requires the **true label Y_t**.

**Correction:** on-device real-time autonomy has no labels; the indicator is
only computable retrospectively. The Stage-1 experiment is therefore framed
honestly as a **post-deployment audit** using the frozen test archive with
labels. On-device operation would need a proxy (e.g., set-size inflation as an
uncertainty signal) or delayed labels — stated as future work, not claimed.

**Measured result (Stage 1, 1000 frames, shift at t=300, INT8 models,
calibration-only τ):**

| segment | static conformal | ACI (TTCA) |
|---------|------------------|------------|
| clean 0–299 | 95.8% | 95.8% |
| shift 300–699 | **48.6%** | **93.9%** |
| post 700–999 | 43.9% | **94.9%** |
| ALL | 59.6% | **94.7%** |

Static conformal collapses under shift (exchangeability violation, measured);
**ACI restores coverage to 94–95% at +3.3% compute.**

## Correction 2 — the continuous model needs a re-certified τ(k), and the LTC is Pareto-inefficient here

**Proposal as written:** the LTC enables "mathematically perfect temporal
packing" by halting at any integration step.

**Correction A (certification):** the certified τ's are for the discrete
exits; a continuous model needs the **certification curve τ(k)** (per-step
split-conformal quantiles) — the Stage-2 machinery. This is required for the
thesis's safety claim to survive the model change.

**Correction B (measured Pareto audit — the Go/No-Go gate):** the discrete
frontier **saturates**:

| exit | depth | compute | accuracy |
|------|-------|---------|----------|
| 1 | 30% | 0.80 ms | 73.5% |
| 2 | 60% | 1.24 ms | 92.2% |
| 3 | 100% | 2.34 ms | 93.1% |

exit2 = **99.0% of exit3's accuracy at 53% of the cost** (only +0.9 pp
remains). The LTC's only theoretical gain (exit2-accuracy reached earlier) is
**conditional** on unproven accuracy-per-MAC superiority, against a multi-week
high-risk investment (training + INT8 ODE + τ(k) + hardware port).

**Verdict: NO-GO on training the LTC for efficiency.** The discrete 3-exit
model is the Pareto-optimal certified-anytime choice. If finer granularity is
wanted, add 1–2 discrete exits with the **existing** certification pipeline
(days, every threshold frozen-protocol-certified). The continuous-time τ(k)
machinery remains a theoretical contribution, demonstrable on the discrete
model's exits.

## Correction 3 — ACI is reactive, not predictive (and the mechanism is set inflation, not deeper exits)

**Proposal as written:** under shift, α drops → sets inflate → "forcing deeper,
safer exits" → early exits return when stable.

**Correction (measured):**
- **Reactive lag is real:** the first 50 frames after shift onset run at
  86% coverage (α₁ crashes 0.061→0.011 in ~20 frames *after* the first
  miscoverages); full 95% recovery by frame 400. ACI recovers — it does not
  prevent the transient (the Gibbs–Candès guarantee is marginal tracking).
- **The mechanism is set inflation, not deeper exits:** under shift the
  prediction sets grow **4.8 → 26.8 of 43 classes** at the shallow exit —
  coverage is restored at the *cheap* exit1 (+3.3% compute). This is the
  mathematically correct ACI behavior and it is *energy-favorable* (the
  binary accept/defer "deeper exits" variant is a different design).

## One-paragraph takeaway for the meeting

> TTCA (ACI) on the existing certified model restores the 95% safety coverage
> under an abrupt environmental shift (48.6% → 93.9%) at +3.3% compute —
> with three honest scopes: it is a label-available offline audit, the safety
> margin appears as prediction-set inflation (not deeper exits), and it
> reacts with a ~100-frame lag. The Pareto audit then closes the LTC question
> on data: the discrete 3-exit model saturates the accuracy/compute frontier
> (exit2 = 99% of exit3 at 53% cost), so training a Liquid LTC is **not**
> justified for efficiency — the staged plan's Go/No-Go gate, answered with
> measurements instead of ambition.

## Files

- `training/results/ttca/TTCA_STAGE1_REPORT.md` — full Stage-1 method+results
- `training/results/ttca/STAGE3_PARETO_AUDIT.md` — the Go/No-Go audit
- `training/results/ttca/ttca_stage1_plots.png`, `stage3_pareto_audit.png`
- `training/conformal/{ttca_aci,aci_shift_predict,pareto_audit}.py`
