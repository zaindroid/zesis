# Brief 3 report: quantization + conformal certification

**Note (superseding the original version of this report): the coverage
section below was rewritten after discovering the original calibration
was invalid -- MARGIN_FACTOR and, separately, the training checkpoint had
both been selected while observing test-set coverage, which contaminates
split-conformal's finite-sample guarantee. The full protocol was redone
under a frozen, four-way split with test touched exactly once. See
`data/splits/FROZEN_PROTOCOL.md` for the complete rationale and
execution order. The quantization section (Section 1) is unaffected and
unchanged.**

## 1. INT8-per-channel PTQ (`train/quantize.py`)

Each exit sliced from the trained multi-exit graph into a standalone
Keras model, quantized independently: `TFLiteConverter`, `Optimize.DEFAULT`,
representative dataset = stratified sample from `calibration.csv`, INT8
input/output.

| exit | FP32 acc (calibration) | INT8 acc (calibration) | drop |
|---|---|---|---|
| exit1 | 73.66% | 73.06% | +0.60pp |
| exit2 | 92.85% | 92.80% | +0.05pp |
| exit3 | 94.87% | 94.74% | +0.14pp |

All three well within the 1-2pt drop normal range -- no QAT fallback needed.

## 2. Frozen four-way calibration protocol

**Why this changed**: the original calibration used a two-way
train/calibration split plus the official test split, applied a
MARGIN_FACTOR=0.5 chosen by observing test-set pass/fail and iterating,
and (separately) had re-selected the training checkpoint after observing
test-set coverage. Both practices leak test-set information into
decisions that are supposed to be fixed before test is touched, which
invalidates split-conformal's finite-sample guarantee even though no
single number was literally copied from test into training.

**Fix**: re-split into four disjoint, track-aware, stratified,
seed-fixed (seed=20260728) partitions -- train (75% of training-archive
tracks) / calibration (15%) / margin_val (10%) / test (official GTSRB
test archive, unchanged, quarantined). Checkpoint selection uses only
train + an internal monitoring slice of train (never test). The
MARGIN is derived from the calibration -> margin_val shift only (a
same-session holdout), never from test. Full execution order, and the
non-negotiable rules, are in `data/splits/FROZEN_PROTOCOL.md`.

Margin derivation (`conformal/derive_margin.py`, calibration vs
margin_val base safety-critical miss-rate at tau=0):

| exit | calibration base miss | margin_val base miss | delta_k |
|---|---|---|---|
| exit1 | 32.06% | 32.78% | 0.72pp |
| exit2 | 10.51% | 9.81% | 0.00pp (negative, floored to 0) |
| exit3 | 9.92% | 8.30% | 0.00pp (negative, floored to 0) |

Calibration (`conformal/calibrate.py`) then finds tau_k on
`calibration.csv` only, targeting alpha_cal = alpha - delta_k per
(exit, alpha) -- full table in `results/conformal_tau_table.csv`.

## 3. Coverage validation on TEST -- the single frozen touch

**This is the only time `test.csv` was read for this protocol.**
`conformal/coverage_validate.py` applied the frozen tau_k to test and
reported the result once, unmodified, whatever it was. It was
independently re-verified by recomputing miss-rates directly from the
raw `test_predictions_exit{1,2,3}.csv` files, which matches
`results/coverage_validation_table.csv` exactly, cell for cell.

**Final certified menu** (`results/BRIEF3_FINAL_certified_menu.csv`):

| exit | alpha | tau_k | n (test) | achieved miss | status |
|---|---|---|---|---|---|
| exit1 | 0.01 | -- | 0 | -- | **NOT CERTIFIABLE** |
| exit1 | 0.05 | 0.858 | 2928 | 0.0447 | PASS |
| exit1 | 0.10 | 0.723 | 4303 | 0.0904 | PASS |
| exit2 | 0.01 | 0.995 | 5795 | 0.0112 | **FAIL** |
| exit2 | 0.05 | 0.815 | 7530 | 0.0517 | **FAIL** |
| exit2 | 0.10 | 0.402 | 8399 | 0.0985 | PASS |
| exit3 | 0.01 | 1.000 | 2616 | 0.0027 | PASS |
| exit3 | 0.05 | 0.912 | 7730 | 0.0450 | PASS |
| exit3 | 0.10 | 0.000 | 8460 | 0.0887 | PASS |

**6 of 9 nominal (exit, alpha) targets hold under the clean, single-touch
protocol.** This is a genuinely different, and in places worse, result
than the original (contaminated) 7/9: exit2 now fails at both alpha=0.01
and alpha=0.05, which the original margin=0.5 (applied uniformly to all
three exits, including exit2, which the honest within-session estimate
says needed none) was inadvertently masking.

**Certified deployment menu, per exit:**
- **exit1**: certified at alpha in {0.05, 0.10}. Not certifiable at
  alpha=0.01 -- this is the weakest/cheapest exit (71-73% base accuracy)
  and cannot reach the tightest safety tier regardless of thresholding.
- **exit2**: certified at alpha=0.10 only. Fails the guarantee at
  alpha=0.01 and alpha=0.05 on the real, single-touch test split -- do
  not deploy exit2 as a certified stop point for those tiers.
- **exit3**: certified at alpha in {0.01, 0.05, 0.10} -- all three.

## Known limitations / honest caveats

- margin_val is a same-session holdout (delta_k measures within-session
  split noise); the true cross-session shift is exactly what the single
  test touch measured, and for exit2 it exceeded what the calibration-side
  evidence predicted. This is expected and is the entire point of running
  a genuine single-touch test: it can, and here did, disagree with what
  same-session evidence alone would suggest.
- No further tuning is permitted against this test result. exit2's
  failures at alpha in {0.01, 0.05} stand as reported. A future
  improvement (more calibration/margin_val data, a better distribution-
  shift estimator, or model changes) would need to be validated against a
  freshly quarantined test split, not this one.

## Artifacts

- `results/tflite/exit{1,2,3}_int8.tflite`
- `results/quantize_accuracy_report.csv`
- `results/calibration_predictions_exit{1,2,3}.csv`, `margin_val_predictions_exit{1,2,3}.csv`, `test_predictions_exit{1,2,3}.csv`
- `results/margin_derivation.json`, `margin_derivation.log`
- `results/conformal_tau_table.csv`
- `results/coverage_validation_table.csv`
- `results/BRIEF3_FINAL_certified_menu.csv` -- **the headline artifact**
- `data/splits/FROZEN_PROTOCOL.md`, `SPLIT_SUMMARY.md`, `checksums.sha256`
