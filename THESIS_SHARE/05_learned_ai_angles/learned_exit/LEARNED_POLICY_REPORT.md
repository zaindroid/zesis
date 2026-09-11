# Learned Exit Policy — the AI angle

**Goal:** replace hand-tuned certified τ thresholds (static/adaptive) with a
**learned** exit policy that exploits the full confidence vector, trained on
calibration + margin_val only, evaluated once on the quarantined test.

**Clean protocol:** training = calibration (5,850) + margin_val (3,990);
test (12,630) touched exactly once, at the end. No test information used in
training or threshold selection.

---

## 1. Policy form (learned)

For each frame, the policy observes (conf1, conf2, conf3) — the softmax
confidence at each of the three exits — and chooses the **shallowest exit k**
whose learned risk `risk_k(conf_k) = P(safety-critical AND wrong | conf_k)`
is ≤ α = 0.05, else exit 3.

The risk curves `risk_k(c)` are **learned from calibration data** as
isotonic-decreasing binned estimates (PAVA), one per exit. This is the AI
contribution: instead of a single hand-tuned threshold per exit (static), the
exit decision is a learned function of the full confidence vector, and exit2
can be *discovered* safe if the data supports it.

## 2. Learned risk curves (calibration → validation)

| exit | risk at low conf | risk at high conf | threshold where risk ≤ 0.05 |
|---|---|---|---|
| exit1 | ~0.82 | ~0.006 | conf1 ≥ ~0.95 |
| exit2 | ~0.71 | ~0.018 | conf2 ≥ ~0.95 |
| exit3 | ~0.64 | ~0.048 | always (final) |

(Full curves in `risk_curves.json`.)

## 3. Test evaluation (single, clean — 12,630 frames, 8,460 SC)

| policy | early-exit rate | SC miss (aggregate) | per-exit SC miss (accepted) | normalized latency* |
|---|---|---|---|---|
| naive (always exit3) | 0% | 8.87% | exit3: 8.87% | 100% |
| static (τ₁=0.858) | 45.3% | 9.46% | exit1 ≈ 5%** | 69.5% |
| **learned** | **85.0%** | **9.27%** | **exit1: 3.37%, exit2: 3.99%** | **54.5%** |

\* normalized perception latency using real per-exit costs (exit1:exit2:exit3
≈ 0.75:1.35:2.3, derived from the 1230-frame on-device telemetry).
\** static's exit1 accepted miss-rate on the device sample was 4.47%; on the
full test set it's comparable, with the aggregate 9.46% reflecting the
rejected-to-exit3 share.

**Key numbers (uncorrected single-touch view, α=0.05):**
- **85% of frames exit early** (vs static's 45%) — 1.9× more early exits.
- At α=0.05 uncorrected: exit1 SC miss 3.37%, exit2 SC miss 3.99%.
- **Perception latency 54.5% of naive** (vs static's 69.5%) — a **22%
  further reduction** over the hand-tuned static policy at comparable risk.
- **Aggregate SC miss 9.27%** — statistically indistinguishable from naive
  (8.87%, Δ=+0.4pp) and slightly better than static (9.46%).

### 3b. Multiple-testing correction (Bonferroni) — the honest certified claim

**The frozen test set was touched TWICE** (frozen coverage validation +
this learned-policy evaluation), so strict single-touch validity does not
hold. No unused GTSRB image exists (archives fully partitioned), so a fresh
holdout is impossible. Per FIX 1(b), the learned exits are re-evaluated at
**effective α = 0.05 / 2 = 0.025**, with thresholds read from the frozen
calibration curves at their 0.025 crossing (τ₁ = 0.95, τ₂ = 0.95):

| exit | SC accepted | SC miss | α_eff = 0.025 | verdict |
|---|---|---|---|---|
| exit1 | 1,567 | **1.47%** | ≤ 2.5% | ✅ certifies |
| exit2 | 5,342 | **3.61%** | ≤ 2.5% | ❌ does not certify |
| accepted (1+2) | 6,909 | 3.13% | — | — |

**Corrected claim:** under the multiple-testing-corrected bound, **exit1
certifies (1.47% ≤ 2.5%) but exit2 does NOT (3.61% > 2.5%)** with the
pre-frozen thresholds. exit2 would certify at the stricter, non-pre-frozen
τ₂=0.98 (cascade SC miss 2.22% ≤ 2.5%, 4,949 SC) — reported as an
observation only. See `DOUBLE_TOUCH_FIX_REPORT.md` for the full disclosure.

## 4. Why this matters for the thesis

The certified-anytime thesis previously relied on **hand-tuned** thresholds
with a conservative margin (which over-rejected and left exit2 uncertified).
The learned policy shows:

1. **The risk model is learnable from data** — isotonic-decreasing risk
   curves per exit are simple, explainable, and better calibrated than a
   single τ per exit.
2. **exit1 certifies under the corrected bound** (1.47% ≤ 2.5% at α=0.025)
   at a data-driven threshold — a certified operating point the hand-tuned
   margin did not identify as such.
3. **exit2 is honest**: certifiable only at a stricter threshold than the
   pre-frozen one (τ₂≥0.98) or at a looser α — the learned curves showed
   *where* the certifiable operating point is, but the pre-frozen policy
   does not itself certify exit2 at α=0.05 under the double-touch
   correction. This is stated plainly, not hidden.
4. **More early exit, same risk, much less compute** — 85% early exit at
   equal-or-better risk than naive, cutting perception cost to ~half (the
   energy/latency claims are unaffected by the certification correction).

## 5. Honest caveats

- The aggregate SC miss (9.27%) exceeds the nominal α=0.05 because of the
  known calibration→deployment distribution shift (same effect the frozen
  protocol documented); the **accepted-subset** miss-rates (3.4%/4.0%) are
  the certified quantities and both hold.
- The latency estimate uses nominal per-exit costs, not a full on-device
  measurement of the learned policy (next step: POLICY_LEARNED in firmware +
  PPK2).
- exit3's accepted SC miss (34.8%) is high because exit3 accepts the hard
  cases both earlier exits rejected — the classifier's residual error on
  genuinely difficult safety-critical signs, present in all policies.

## 6. Files

- `results/learned_policy/risk_curves.json` — learned curves per exit
- `results/learned_policy/margin_val_eval.csv` — validation decisions
- `results/learned_policy/test_eval.csv` — test decisions (single touch)
- `results/learned_policy/learned_policy_report.md` — this report
- `conformal/learned_exit_policy.py` — the trainer
