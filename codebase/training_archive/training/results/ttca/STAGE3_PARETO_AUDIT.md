# Stage-3 Go/No-Go Gate — Pareto Efficiency Audit: is the LTC worth training?

**Question:** the discrete 3-exit anytime model is measured, certified, and
deployed. A continuous Liquid-Time-Constant (LTC) model would add fine-grained
anytime granularity — but at the cost of a new training pipeline, INT8
quantization of an ODE loop, a continuous certification curve τ(k), and a
hardware port. Does the efficiency story justify that risk?

**Method:** the Pareto audit bounds the LTC's *maximum possible* advantage
from measured data only: per-exit top-1 accuracy (calibration split, frozen
protocol) and per-exit compute (PPK2-validated EXIT_MS).

## The measured discrete frontier

| exit | depth | compute (ms) | top-1 accuracy |
|------|-------|-------------|----------------|
| exit1 | 30% | 0.80 | 73.5% |
| exit2 | 60% | 1.24 | 92.2% |
| exit3 | 100% | 2.34 | 93.1% |

**Saturation fact:** exit2 captures **99.0% of exit3's accuracy at 53% of the
cost** — only **+0.9 pp** of accuracy remains in the entire exit2→exit3
region (1.1 ms of compute).

## The bounded-gain analysis (the LTC's max possible advantage)

- **[exit1→exit2, 0.80→1.24 ms]:** at best the LTC reaches exit2 accuracy
  (92.2%) *earlier* → a theoretical 35% energy saving *on those frames* —
  but ONLY if the LTC matches exit2's accuracy at exit1's cost. That requires
  the LTC to be strictly more accurate per MAC than the discrete model, for
  which there is **no evidence** on GTSRB with a tiny LTC (the per-step MLP
  f(h,x) adds overhead every Euler step).
- **[exit2→exit3, 1.24→2.34 ms]:** only 0.9 pp of accuracy exists; nothing
  worth training for.
- **Realistic LTC headroom: a few % energy at best, conditionally.**

## Risk-adjusted cost of realising it

| item | cost |
|------|------|
| LTC training on GTSRB (new pipeline, ODE/closed-form) | weeks |
| INT8 quantization of the Euler loop + f-MLP (custom layer) | high risk |
| Continuous certification curve τ(k) (Stage-2 machinery) | new |
| Hardware port NXP + ESP32 + PPK2 re-validation | weeks |

**Cheaper alternative:** add 1–2 discrete exits (e.g. 45%/75% depth) reusing
the **existing** certification pipeline → the anytime menu gains granularity
at ~days of effort, with every threshold certified by the frozen protocol.

## GO/NO-GO VERDICT: NO-GO on the LTC for the efficiency story

1. The discrete frontier **saturates** at exit2 (99.0% of exit3's accuracy at
   53% of the cost).
2. The only theoretical gain is **conditional** on unproven LTC
   accuracy-per-MAC superiority.
3. The certification curve + INT8 ODE + hardware port is a multi-week,
   high-risk investment for a few-% bound.

**What this means for the thesis:** the discrete 3-exit model is the
**Pareto-optimal** certified-anytime choice for this workload. The
continuous-time *framing* can still appear in the thesis as the theoretical
machinery (the τ(k) certification curve, Stage 2) demonstrated on a
multi-exit discrete model — but training and deploying a real LTC is **not**
justified by the measured trade-off. This is the defensive conclusion the
staged plan anticipated: the data, not the ambition, makes the decision.

## Files

- `conformal/pareto_audit.py` — the audit (recomputes everything)
- `results/ttca/stage3_pareto_audit.png` — the frontier plot
