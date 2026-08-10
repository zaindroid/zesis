# FROZEN four-way protocol (conformal certification)

This document fixes the certification protocol. It exists because two earlier
rounds produced coverage numbers that are NOT trustworthy: the margin factor
and, later, the checkpoint were adjusted while observing test-set coverage,
which contaminates the split-conformal guarantee. From this point on, test is
touched exactly once, at the very end, with everything pre-frozen, and the
result stands regardless of PASS or FAIL.

## Data partition (fixed, hashed)

Re-split by `train/split_dataset_fourway.py` (track-aware, per-class
stratified, seed `20260728`):

| split       | fraction | role                                                       |
|-------------|----------|------------------------------------------------------------|
| train       | 75%      | training + internal monitoring-val (checkpoint selection ONLY here) |
| calibration | 15%      | conformal tau_k calibration ONLY                           |
| margin_val  | 10%      | MARGIN derivation ONLY (calibration->margin_val shift)     |
| test        | (official GTSRB test archive, QUARANTINED) | final single touch only |

- All splits are TRACK-aware (GTSRB `<trackID>_<frameID>.ppm`), never
  frame-level, to prevent near-duplicate leakage (see
  `train/split_dataset.py` docstring).
- SHA-256 of every split file, including the frozen `test.csv`, is in
  `data/splits/checksums.sha256`.
- `test.csv` is defined once, its checksum frozen, and it is NEVER written by
  any script except the final single run of `conformal/coverage_validate.py`.

## Frozen execution order (do exactly once, in order)

1. **Split**: `python train/split_dataset_fourway.py --seed 20260728
   --train-track-fraction 0.75 --cal-track-fraction 0.15
   --margin-track-fraction 0.10`  (writes train/calibration/margin_val; test
   untouched, only hashed)
2. **Train**: `python train/train.py --config train/configs/multiexit.yaml`
   -- checkpoint selection uses ONLY train + the train-internal monitoring
   val-slice (`val_track_fraction: 0.1` in the config). The `MaxOfMinCheckpoint`
   callback saves `best_joint.weights.h5` by max-of-min over the three exits'
   val accuracies. Test is NOT consulted for checkpoint choice.
3. **Quantize**: `python train/quantize.py` -- INT8 PTQ per exit using
   `calibration.csv` as representative dataset; writes
   `calibration_predictions_exit{1,2,3}.csv` (INT8 predictions on calibration).
4. **margin_val predictions**: `python conformal/predict_split.py --split margin_val`
   -- INT8 predictions on `margin_val.csv` only.
5. **Derive margin**: `python conformal/derive_margin.py` -- measures
   delta_k = max(0, margin_val_base_miss_k - calibration_base_miss_k) at tau=0
   over safety-critical classes, per exit; writes `margin_derivation.json` and
   appends the derivation to `margin_derivation.log`. Margin is derived HERE,
   on margin_val ONLY, never by iterating toward test.
6. **Calibrate**: `python conformal/calibrate.py` -- tau_k per (exit, alpha)
   with alpha_cal = alpha - delta_k from step 5, using `calibration.csv` ONLY.
7. **FREEZE** checkpoint + tau_k + margin. Do not change anything after this.
8. **Validate (the single test touch)**: `python conformal/coverage_validate.py`
   -- applies the frozen tau_k to `test.csv` EXACTLY ONCE and reports the raw
   result. If cells FAIL, report FAIL. Do NOT adjust and re-run.
9. **Independent recompute** of the coverage table from the raw
   `test_predictions_exit{1,2,3}.csv` files.

## Rules (non-negotiable)

- `test.csv` is touched by exactly one script, exactly once, at the very end,
  with everything frozen.
- No margin, tau, checkpoint, or model change may be informed by test-set
  results. If a cell fails, that failure is the result.
- The margin factor is derived from margin_val (same-session holdout); it
  measures within-session split noise, NOT the cross-session shift. The
  cross-session shift is what the final test touch measures. A clean FAIL is
  an honest, reportable result; a number tuned to pass is not.

## Why the old 8/9 is invalid

The 8/9 run used MARGIN_FACTOR=0.5 (a first guess, never re-derived on a clean
slice) and the checkpoint was re-selected after observing test coverage. Both
contaminate the guarantee. This protocol makes both impossible.
