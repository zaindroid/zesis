# Model training — evidence pack

Everything here is reproducible from `codebase/training_archive/training/`.
Numbers below are read from the saved history files, not from memory.

---

## 0. Scope note — read this first

You asked for training curves for "the conformal logic model" and "the
interleaving joined training for PQC and conformal logic joined heads".

Two of those exist. **One does not, and it is better to know now than in the
meeting:**

| Component | What it actually is | Gradient-trained? |
|---|---|---|
| Multi-exit perception model | 3-exit MobileNetV1, Keras, 100 epochs | **Yes** — `train/train.py` |
| Baseline control model | Same backbone, single exit | **Yes** — `train/train.py` |
| Learned exit policy (conformal) | Isotonic/PAVA risk curves fitted on the calibration split | **No** — a statistical fit, `conformal/learned_exit_policy.py` |
| Joint PQC + exit scheduler | Trace-driven **simulator** over measured costs | **No** — `conformal/joint_scheduler.py` |
| ML-DSA latency tails | Measured distributions (2000 runs/level) | **No** |

**There is no jointly-trained PQC + perception neural network.** Only two
scripts in the whole tree do gradient training (`train.py`, `quantize.py`), and
both train the perception model. The scheduler that decides "which security
level + which exit" is a simulator driven by real measured numbers; the
conformal side is a curve fit, not a network.

That is defensible — a simulator over measured costs is the stronger choice when
every cost is a real measurement — but it must be described as such. If the
professor expects a joint network, better to say plainly that the joint layer is
analytical, and why.

---

## 1. The trained model

**Three-exit MobileNetV1-flavoured backbone**, built for the eIQ Neutron NPU op
whitelist.

| Property | Value |
|---|---|
| Input | 48 x 48 x 3, INT8-quantised |
| Classes | 43 (GTSRB) |
| Depth | 10 depthwise-separable blocks in 3 stages |
| Exit placement | **exactly 30% / 60% / 100%** of block-depth (blocks 3, 6, 10) |
| Stage widths | stem 16 -> A 32 -> B 40 -> C 176 |
| Ops | Conv2D (std/dw/pw), ReLU6, MaxPool, GlobalAvgPool, FC, Add, BatchNorm |
| Excluded | SE blocks, attention, swish, in-graph softmax |
| Exit heads | raw logits; softmax + tau thresholding happen CPU-side |

Two design decisions worth mentioning, because they were deliberate and are
recorded in the source:

- **Capacity is deliberately unequal across exits.** Stages narrow then widen
  (32 -> 40 -> 176) so the early exits work with genuinely weaker features. This
  was tuned: stage B was narrowed from 64 to 40 and stage C widened from 128 to
  176 *because* at 64 channels exits 2 and 3 converged to within ~1 percentage
  point by epoch 15 and stayed there — the "exits collapse" failure mode the
  brief warns about, for the exit2/exit3 pair.
- **Head placement is exact, not approximate.** Blocks 3/6/10 of 10 gives
  30/60/100% rather than "about 30%".

---

## 2. Training configuration

`train/configs/multiexit.yaml`:

```yaml
seed: 20260728
model: multiexit
batch_size: 128
epochs: 100
learning_rate: 0.001
val_track_fraction: 0.1
exit_loss_weights:
  exit1: 1.0
  exit2: 1.0
  exit3: 1.0
checkpoint_dir: results/checkpoints/multiexit
```

`train/configs/baseline.yaml` is the control: identical backbone, single final
exit, single cross-entropy — used to measure what joint multi-exit training
costs the final classifier.

**Loss: BranchyNet joint loss.** `L = Σ_k w_k · CE(exit_k)` with equal weights
`w_k = 1.0`. Equal weighting was the brief's instruction; per-exit weighting is
the documented lever if the accuracy spread needs rebalancing.

**Validation split is track-aware and taken from the training set only.**
GTSRB frames are named `<trackID>_<frameID>.ppm` with ~30 near-duplicate frames
per physical sign, so a naive random split leaks the same sign into train and
val. `val_track_fraction: 0.1` holds out whole tracks. The calibration and test
splits are untouched by training.

---

## 3. Training curves

Source data: `results/logs/multiexit/history.csv` and
`results/logs/baseline/history.csv` (one row per epoch, 100 epochs).

Plots (ready to open):

- `results/plots/multiexit_accuracy_curves.png` — per-exit train + val accuracy
- `results/plots/multiexit_loss_curves.png` — per-exit train + val loss
- `results/plots/multiexit_vs_baseline.png` — multi-exit vs single-exit control

Regenerate any time with `python make_plots.py`.

### Multi-exit model, 100 epochs

| Metric | Epoch 0 | Final (ep100) | Best | Best epoch |
|---|---|---|---|---|
| val exit1 accuracy | 0.048 | 0.727 | **0.733** | 95 |
| val exit2 accuracy | 0.048 | 0.901 | **0.923** | 94 |
| val exit3 accuracy | 0.048 | 0.909 | **0.931** | 94 |
| val loss (summed) | 10.918 | 2.093 | **1.770** | 94 |

### Baseline control, 100 epochs

| Metric | Epoch 0 | Final (ep100) | Best | Best epoch |
|---|---|---|---|---|
| val accuracy | 0.054 | 0.913 | **0.945** | 95 |
| val loss | 3.825 | 0.498 | **0.360** | 96 |

### What the curves show

- **All three exits learn**, and they stay ordered: exit3 (0.931) > exit2
  (0.923) > exit1 (0.733). The ordering is what makes the anytime behaviour
  meaningful; if the exits had collapsed together there would be nothing to
  trade off.
- **The spread is wide and stable** — ~20 points between exit1 and exit3. That
  is the capacity handicap doing its job.
- **Joint multi-exit training costs the final exit ~1.4 points** (0.931 vs 0.945
  baseline). That is the price of the anytime property, and it is the number to
  quote when asked whether early exits are free.
- Both runs peak around epoch 94-96 and then drift slightly; training to 100
  epochs is past the optimum.

### Checkpoint selection

The multi-exit run saves several checkpoints; `best_joint.weights.h5` is chosen
by a `MaxOfMinCheckpoint` callback that maximises `min(val_exit1_acc,
val_exit2_acc, val_exit3_acc)` — i.e. it protects the weakest exit rather than
the average. On this run that lands at **epoch 95** (min-of-exits = 0.733,
set by exit1).

Available: `best.weights.h5`, `best_exit3_epoch71.weights.h5`,
`best_exit3_frozen_epoch_NA.weights.h5`, `best_joint.weights.h5`,
`final.weights.h5`.

---

## 4. From trained weights to the .tflite segments

| Step | Script | Output |
|---|---|---|
| Train | `train/train.py` | `results/checkpoints/multiexit/*.weights.h5` |
| Quantise (INT8 per-channel PTQ, TFLiteConverter) | `train/quantize.py` | `results/tflite/exit{1,2,3}_int8.tflite` |
| Split into standalone per-exit segments | — | `results/segments/seg{A,B,C}_int8.tflite` |
| Quantisation accuracy check | — | `results/quantize_accuracy_report.csv` |

Segment sizes: segA 16,736 B, segB 21,168 B, segC 125,896 B. All three share one
trained graph; they are separate `.tflite` files so each can run standalone on
device.

---

## 5. The parts that are not gradient-trained

If the meeting goes toward the conformal/scheduler side, these are the honest
descriptions:

**Learned exit policy** (`conformal/learned_exit_policy.py`). Fits isotonic
(PAVA, decreasing) risk curves `risk_k(c) = P(safety-critical AND wrong | conf_k = c)`
**on the calibration split only**, then picks the shallowest exit whose risk is
under the target alpha. It is a monotone curve fit with a guarantee argument,
not a trained network. Output: `results/learned_policy/risk_curves.json`.

**Joint scheduler** (`conformal/joint_scheduler.py`). A trace-driven simulator.
State per frame: `conf1`, `conf2`, `cryptoImminent`, `budgetUsed`. Decision per
frame: which exit. Decision per handshake: which ML-KEM level (512/768/1024).
All costs are measured, not modelled:

```
exit1 = 0.80 ms, exit2 = 1.24 ms, exit3 = 2.34 ms     (MCXN947, on device)
ML-KEM handshake: 512 = 72.17 ms, 768 = 115.97 ms, 1024 = 174.91 ms
```

Policies compared: naive / static / adaptive / learned. Output:
`results/learned_policy/JOINT_SCHEDULER_REPORT.md`.

> Note: those ML-KEM figures are the **bare-metal PQClean** numbers. September's
> `-O2` wolfSSL harness measured the same 768 handshake at **21.62 ms** — 5.4x
> faster. The scheduler report should be re-run against the faster costs before
> it is quoted; the qualitative conclusion changes (the "infeasible at 768"
> result flips to feasible).

**Conformal certification itself** is not learned at all — it is the
split-conformal quantile calculation over the calibration split, reported in
`results/conformal_tau_table.csv` and `results/coverage_validation_table.csv`.

---

## 6. Files to have open

| Purpose | Path |
|---|---|
| Accuracy curves | `results/plots/multiexit_accuracy_curves.png` |
| Loss curves | `results/plots/multiexit_loss_curves.png` |
| vs baseline | `results/plots/multiexit_vs_baseline.png` |
| Raw per-epoch history | `results/logs/multiexit/history.csv` |
| Config | `train/configs/multiexit.yaml` |
| Model definition | `models/architectures.py` |
| Checkpoints | `results/checkpoints/multiexit/` |
| Certification results | `results/conformal_tau_table.csv` |
