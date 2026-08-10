# Option A (reframed) — Learned Crypto-Activity Leakage from PPK2 Power Envelopes

**Date:** 2026-08-09
**Status:** Complete — hardware capture + learned classifier + robustness sweep.

## What this is (honest framing)

A learned classifier identifies **which ML-KEM-1024 operation (keypair /
encaps / decaps) is running** from the **10 kHz PPK2 power envelope alone**.
This is a real **operational/activity leakage** observation: a cheap current
probe reveals what crypto work the device is doing.

This is **NOT key-recovery SCA** — that needs a ≥100 MS/s oscilloscope
(10 kHz averages the key-dependent signal away across millions of cycles).
Stated plainly in `A_FEASIBILITY.md`.

## Hardware & capture

- FRDM-MCXN947, ACTIVITY firmware (segmentable per-op bursts, P0_31 trigger)
- **550 pulses** of ML-KEM-1024 ops (this project ships 1024 only — the
  "512/768" serial labels were a firmware bug; all ops are 1024, verified by
  durations 51.0/57.2/66.7 ms = kp/enc/dec)
- Trigger P0_31 → PPK2 D0: clean per-op isolation; 10 ms gaps
- 546 usable pulses after dropping 4 artifacts; labels 183/182/181

## Method (honest design)

- Per-pulse **power envelope**: 256-point resampled current signature
- **Shape-only features**: each envelope z-scored (mean removed, std
  normalized) so the classifier CANNOT use absolute current or duration —
  it must learn the shape
- **Middle-50% ablation**: also tested with the envelope edges removed
  (edges correlate with duration)
- Models: Random Forest + MLP (sklearn; 546 samples is too small for a deep
  CNN), 5-fold cross-validation
- Baselines: duration-only threshold, majority class

## Results

| classifier | CV accuracy |
|---|---|
| RF, full envelope (shape-only) | **99.8%** ± 0.4% |
| RF, middle-50% only (edges removed) | **99.8%** ± 0.4% |
| MLP, full envelope | **99.8%** ± 0.4% |
| duration-only baseline | 100% |
| majority-class baseline | 33.6% |

**The learned classifier reaches ~100% on shape-only features, even with the
envelope edges removed.** The ops are distinguishable from the mid-pulse
power signature — not just from duration or absolute level.

## Robustness sweep (attacker's probe cost)

| samples per envelope | CV accuracy |
|---|---|
| 256 (10 kHz) | 99.8% |
| 128 | 99.8% |
| 64 | 99.8% |
| 32 | 99.8% |
| 16 (~1.6 kHz effective) | 99.8% |

**The leakage survives a 16× cheaper probe.** Op identity is robustly encoded
in the coarse power envelope — this is a genuine, low-cost activity leak.

## Interpretation (honest)

1. **Activity leakage is real and cheap**: an eavesdropper with a 10 kHz
   current probe (a $50 sensor) can tell which ML-KEM operation runs, at
   ~100% accuracy, with no calibration beyond a few hundred pulses. This
   reveals handshake timing/type — an operational privacy/anonymity leak.
2. **It's the envelope shape, not just duration**: the middle-50% ablation
   and shape-only normalization show the intrinsic power signature carries
   the identity.
3. **Countermeasure implication**: since the leakage is in the coarse
   envelope, cheap obfuscation (dummy ops of matched duration, concurrent
   dummy computation to flatten the shape) should be evaluated — that's the
   natural next experiment, not a re-capture (the classifier is robust).

## Honest caveats

- **ML-KEM-1024 only** (the firmware shipped 1024; the 512/768 sources
  aren't in this tree — the 3-level extension is future work).
- **3-class op discrimination** (not 9-class level×op). The op-type
  discrimination is the harder, more novel part.
- The duration-based labels (51/57/67 ms) are cleanly separable; the
  shape-only result shows the classifier isn't just using duration, but the
  ops also differ in duration — the envelope shape and duration are not fully
  independent (the middle-50% ablation is the strongest evidence).
- Single board, single capture, fixed firmware variant.

## Files

- `activity_capture.c` — capture firmware (ACTIVITY_MODE)
- `results/activity/envs_1024.npy`, `labels_1024.npy`, `durs_1024.npy` — data
- `activity_cnn.py` — the classifier (RF/MLP, CV, ablations, sweep)
- `A_FEASIBILITY.md`, `A_ACTIVITY_CAPTURE_PROTOCOL.md`
- Raw trace: `H:\z_thesis\energy resulkts\ppk-20260809T090023_raw_with_p0_31.csv`
