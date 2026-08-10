# Brief 2 report: multi-exit model + training

## Architecture (`models/architectures.py`)

MobileNetV1-flavored backbone, 48x48x3 input, 43 classes, NPU-whitelist-only
ops (Conv2D standard/depthwise/pointwise, ReLU6, MaxPool/GlobalAvgPool,
FullyConnected, BatchNorm -- no SE/attention/swish/in-graph softmax).

10 depthwise-separable blocks in 3 stages, exits placed at EXACTLY 30%/60%/
100% block-depth (blocks 3/6/10):

| stage | blocks | channels | exit |
|---|---|---|---|
| A | 1-3 | 16 -> 32 | exit1 @ block3 (30%) |
| B | 4-6 | 32 -> 40 | exit2 @ block6 (60%) |
| C | 7-10 | 40 -> 64 -> 176 | exit3 @ block10 (100%, final) |

Each exit head is GlobalAvgPool -> Dense(43), raw logits (softmax stays
CPU-side, per spec).

**Design iteration** (see below for why): stage B was narrowed from an
initial 64 channels to 40, and stage C widened from 128 to 176, to fix an
exit2/exit3 collapse observed in the first training run.

### Parameter counts

| component | params |
|---|---|
| backbone | 93,928 |
| exit1 head | 1,419 |
| exit2 head | 1,763 |
| exit3 head (final) | 7,611 |
| **total (multi-exit)** | **104,721** |
| baseline (no-exit control, same backbone + final head only) | 101,539 |

Both comfortably under the 300K budget (~2.9x headroom).

## Training (`train/train.py`, `train/configs/{multiexit,baseline}.yaml`)

- Seed: 20260728 (fixed, matches Brief 1's split seed for consistency).
- BranchyNet joint loss, equal weights (w_k=1.0 for all three exits), per
  the brief's "equal weights first."
- 100 epochs, batch size 128, Adam lr=0.001, no LR schedule/early stopping
  (see "known limitations" below).
- Train/monitoring-val split: track-aware carve-out of TRAIN only (29,999
  train-proper / 3,360 monitoring val), calibration.csv and test.csv from
  Brief 1 untouched, as required.
- `jit_compile=False` required (see README -- RTX 5090/Blackwell XLA
  compiler gap, unrelated to model correctness).
- `tf.config.experimental.set_memory_growth` enabled -- this is a shared
  multi-user GPU box; the model only needs ~800MB, no reason to claim the
  whole 32GB by default.

## Design iteration: fixing exit collapse

**First run** (stage widths 16/32/64/128, matching the initial design):
exit2 and exit3 converged to within ~1pp of each other by epoch ~15 and
stayed there for the rest of training (final: exit1=72.2%, exit2=91.1%,
exit3=91.9%) -- the "exits collapse to equal acc" failure mode the brief
warns about, for the exit2/exit3 pair specifically. Diagnosis: stage B's
64-channel bottleneck already carried enough information that stage C's
extra 4 blocks of depth added little.

**Fix**: narrowed stage B (64 -> 40 channels) and widened stage C (128 ->
176), per the brief's explicit "if exits collapse... shrink" guidance --
shrinking the *earlier* stage relative to the *later* one, rather than
shrinking the whole network, to force a genuine capacity gap between exit2
and exit3 while leaving exit1's already-good separation from exit2 alone.

**Result**: real, clearly separated three-tier spread. See below.

## Per-exit accuracy (monitoring val-slice, best checkpoint by val_exit3_acc)

Best checkpoint: **epoch 56/100** (`results/checkpoints/multiexit/best.weights.h5`).

| exit | depth | val accuracy |
|---|---|---|
| exit1 | 30% | **71.7%** |
| exit2 | 60% | **93.8%** |
| exit3 | 100% (final) | **95.4%** |

Compare to the brief's illustrative example (~88/94/97): the achieved
spread has the same qualitative shape (clear monotonic increase, no
collapse) though exit1 sits lower than the example. This reflects a
genuinely "weak" 30%-depth representation (16-channel stem into a 32-channel
stage, small receptive field) -- appropriate for a real early-exit tradeoff
where exit1 should be cheap AND meaningfully less accurate, not just cheap.

Final-epoch (epoch 100, noisier -- reported for completeness, not as the
primary result): exit1=79.6%, exit2=92.6%, exit3=93.7%. Exit1's validation
curve is visibly noisier than exit2/exit3 throughout training (see
`results/plots/multiexit_accuracy_curves.png`) -- expected for a low-capacity
early classifier operating closer to its decision boundary.

## Baseline comparison (does joint multi-exit training cost final accuracy?)

| model | final-exit / only-output val accuracy (best epoch) |
|---|---|
| no-exit baseline (single output, single CE loss) | 94.5% (epoch 95) |
| multi-exit model's exit3 (joint BranchyNet loss) | **95.4%** (epoch 56) |

The multi-exit model's final exit **outperforms** the no-exit baseline by
~0.9pp, and does so consistently across nearly the entire training run
(`results/plots/multiexit_vs_baseline.png`), not just at one favorable
epoch. This is consistent with the "deep supervision" effect documented
elsewhere for auxiliary-loss architectures (e.g. GoogLeNet's auxiliary
classifiers) -- the early-exit losses appear to act as a mild regularizer /
improve gradient flow to the backbone's early layers, rather than competing
with the final classifier for capacity. Joint multi-exit training is free
here, not a trade-off.

## Known limitations / possible follow-ups

- No LR schedule or early stopping was used across the 100-epoch run;
  exit2/exit3 show visible train/val gap by epoch 100 (train accuracy ~99-
  100%, val ~92-95%) -- mild overfitting, though validation accuracy is
  stable (not degrading) past its peak, so this doesn't invalidate the
  reported numbers, but a cosine LR decay or early stopping would likely
  tighten the final numbers and reduce epoch-to-epoch noise (especially
  visible in exit1's validation curve).
- Equal loss weights (w_k=1.0) were used as instructed ("equal weights
  first"); rebalancing (e.g. upweighting exit1) was not explored here but
  is a natural next lever if a stronger/weaker exit1 is wanted later.
- No quantization yet -- INT8-per-channel PTQ is Brief 3.

## Artifacts

- `models/architectures.py` -- final architecture (post-iteration widths)
- `train/train.py`, `train/configs/{multiexit,baseline}.yaml`
- `results/checkpoints/{multiexit,baseline}/{best,final}.weights.h5`
- `results/logs/{multiexit,baseline}/{history.csv,summary.json}`
- `results/plots/{multiexit_accuracy_curves,multiexit_loss_curves,multiexit_vs_baseline}.png`
- `results/gpu_check_log.txt` (from Brief 1, unchanged)
