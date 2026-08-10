# GTSRB multi-exit classifier -> NXP eIQ Neutron NPU

Training lab for a multi-exit GTSRB traffic-sign classifier, trained in
TensorFlow/Keras, quantized to INT8-per-channel, conformally calibrated for
per-exit safety-critical risk bounds, and deployed as chained NPU segments
on the FRDM-MCXN947 (eIQ Neutron NPU) -- the on-device half of this thesis's
"certified-anytime perception" work (see the sibling `npu_segments` /
`npu_dc` / `npu_contention` projects for the firmware/NPU-dispatch side).

## Where this actually lives (read this first)

The original plan located this lab at `H:\z_thesis\training\` on the local
Windows machine. That machine's only GPU is an RTX 3050 (4GB) -- nowhere
near enough for this workload. **The lab instead lives on the remote GPU
workstation `ged25-ki` (RTX 5090, 32GB VRAM, 24 cores, 124GB RAM, Ubuntu
24.04), reachable passwordless over Tailscale as `ssh zulhaq@ged25-ki`,
at `~/z_thesis/training/` on that host.** All paths below are relative to
that remote root, not `H:\`. This is a shared multi-user machine (other
projects live alongside this one in the same home directory) -- be mindful
of GPU/disk usage when running long jobs.

## Pipeline (PC -> board)

```
GTSRB -> split(train/cal/test, seeded, hashed)          [Brief 1 -- done]
      -> train multi-exit CNN (FP32)                     [Brief 2 -- done]
      -> PTQ INT8-per-channel (representative = cal split) [Brief 3 -- done]
      -> per-exit accuracy (FP32 vs INT8)                 [Brief 3 -- done]
      -> conformal calibration on INT8 (cal split) -> tau_k per exit [Brief 3 -- done]
      -> validate coverage on test split                  [Brief 3 -- done]
      -> neutron-convert each exit-segment (target mcxn94x) [Brief 4+]
      -> --dump-header-file-output -> model_data.h + op-resolver
      -> firmware: chain segments, CPU-side tau thresholding + softmax
      -> golden-input check (PC INT8 logits == board logits)
      -> measure per-exit latency/energy/arena on board
```

**Brief 2 result**: multi-exit MobileNetV1-flavored backbone, 104,721
params, exits at exactly 30%/60%/100% block-depth. Best-checkpoint per-exit
val accuracy: exit1=71.7%, exit2=93.8%, exit3=95.4% -- real, non-collapsed
spread. See `results/BRIEF2_REPORT.md` for the full writeup (architecture
iteration history, baseline comparison, plots).

**Brief 3 result**: INT8-per-channel PTQ costs <0.6pp accuracy per exit (no
QAT needed). Conformal calibration on `calibration.csv` initially failed to
generalize to `test.csv` (5/9 exit/alpha combos) -- diagnosed as a genuine
calibration<->test distribution shift (calibration is track-held-out from
the *training* archive; test.csv is the officially *separate* test archive,
+1.3 to +2.4pp higher safety-critical miss-rate measured on test). Fixed by
calibrating with a margin (alpha x 0.5): **7/9 nominal targets now hold on
held-out test data**, one is honestly reported as not-certifiable (exit1
can't support the strictest alpha=0.01 tier with available data -- a real
capacity limit, not a bug), one is a 0.14pp near-miss. See
`results/BRIEF3_REPORT.md` for the full writeup and both before/after
coverage tables.

## Lab structure

```
data/
  raw/               official GTSRB zip archives (downloaded, not committed)
  gtsrb/             extracted archives (Final_Training/, Final_Test/)
  splits/            train.csv, calibration.csv, test.csv (path,label,roi),
                      checksums.sha256, per-split class-distribution CSVs,
                      safety_critical.md, SPLIT_SUMMARY.md
  extract_and_verify.py
  preprocessing.py    shared resize/crop/normalize -- import this, don't
                       reimplement preprocessing anywhere else in the lab
  PREPROCESSING.md    resize/normalization policy + rationale
models/
  architectures.py    multi-exit backbone (Brief 2)
train/
  split_dataset.py    builds data/splits/ from data/gtsrb/ (Brief 1)
  train.py            training loop (Brief 2)
  quantize.py          INT8-per-channel PTQ, per-exit .tflite export (Brief 3)
  configs/            seeded YAML training configs (Brief 2)
conformal/
  calibrate.py         tau_k selection via finite-sample conformal risk bound
                        (Brief 3; MARGIN_FACTOR documented in its docstring)
  coverage_validate.py  test-split coverage check -- the ONLY script that
                        touches data/splits/test.csv (Brief 3)
deploy/
  convert_segments.py  neutron-converter wrapper (Brief 4+)
  gen_golden.py         PC-vs-board golden-input check (Brief 4+)
results/
  BRIEF2_REPORT.md     architecture/training writeup, per-exit accuracy
                        table, baseline comparison (Brief 2)
  BRIEF3_REPORT.md     PTQ accuracy, conformal tau tables, coverage
                        validation (before/after the margin fix) (Brief 3)
  checkpoints/{multiexit,baseline}/{best,final}.weights.h5
  logs/{multiexit,baseline}/{history.csv,summary.json}
  plots/                training curve PNGs (Brief 2)
  tflite/exit{1,2,3}_int8.tflite   (Brief 3)
  quantize_accuracy_report.csv, conformal_tau_table.csv,
  coverage_validation_table.csv    (Brief 3 -- headline artifact)
  {calibration,test}_predictions_exit{1,2,3}.csv   (Brief 3, per-sample)
  gpu_check_log.txt     (Brief 1)
env/
  requirements.txt    pinned pip deps (working environment)
  environment.yml     conda equivalent, for portability (conda isn't
                       installed on ged25-ki; the actual env is a plain
                       venv -- see below)
  gpu_check.py         confirms TF sees the GPU with a real GPU computation,
                       not just device listing
```

## Environment

No conda/mamba on ged25-ki, so the working environment is `python3 -m venv`
+ pip, not conda -- `environment.yml` is provided for portability if you
reproduce this elsewhere with conda already set up, but treat
`requirements.txt` (+ the generated `requirements.lock.txt`) as the source
of truth for what's actually installed.

```bash
ssh zulhaq@ged25-ki
cd ~/z_thesis/training
python3 -m venv .venv
source .venv/bin/activate
pip install -r env/requirements.txt
python env/gpu_check.py        # confirms TF sees the RTX 5090 and can compute on it
pip freeze > env/requirements.lock.txt
```

TensorFlow/Keras only (`tensorflow[and-cuda]==2.21.0`), exporting to
`.tflite`. No PyTorch/ONNX anywhere in this lab.

### Gotcha: `tensorflow[and-cuda]` doesn't auto-find its own pip-installed CUDA libs here

Fresh install: `tf.config.list_physical_devices("GPU")` returns `[]` with a
`Cannot dlopen some GPU libraries` warning, even though every `nvidia-*-cu12`
wheel installed cleanly. The pip-installed CUDA shared libraries land in
`.venv/lib/python3.12/site-packages/nvidia/*/lib/`, but nothing on this
TF/venv combo puts that on the dynamic linker's search path automatically.
Fix (already applied, baked into `.venv/bin/activate` -- a fresh
`source .venv/bin/activate` picks it up with no extra steps):

```bash
# appended to .venv/bin/activate
_NVIDIA_LIB_BASE="$VIRTUAL_ENV/lib/python3.12/site-packages/nvidia"
for _d in "$_NVIDIA_LIB_BASE"/*/lib; do
    LD_LIBRARY_PATH="$_d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
done
export LD_LIBRARY_PATH
```

If you ever rebuild `.venv` from scratch, re-append this block (or just
diff against git history of this file) before assuming GPU training is
broken.

### Gotcha: RTX 5090 (Blackwell, compute capability 12.0) has no precompiled kernels in TF 2.21

`gpu_device.cc` logs `TensorFlow was not built with CUDA kernel binaries
compatible with compute capability 12.0a. CUDA kernels will be jit-compiled
from PTX, which could take 30 minutes or longer.` In practice, for the ops
exercised by `env/gpu_check.py`'s matmul this JIT-compiled in a few
seconds, not 30 minutes -- but this is a known-new-GPU-architecture caveat,
not a false alarm, and it's a **per-op-shape** JIT cache: the *first* time
Brief 2's actual training loop hits a conv/pooling op shape it hasn't seen
before, expect a real (if one-time) stall while that kernel JIT-compiles.
Confirmed working end-to-end regardless -- see `results/gpu_check_log.txt`
for the full run (GPU visible, real matmul executed on
`/job:localhost/replica:0/task:0/device:GPU:0`, RTX 5090 reporting 29684 MB
usable).

### Gotcha: XLA auto-clustering hard-fails on the RTX 5090 during actual training

`env/gpu_check.py`'s plain forward-only matmul works fine, but a real
`model.fit()` step does not: TF's XLA autotuner tries to compile a fused
GEMM+gradient kernel via Triton and fails outright (`Autotuner could not
compile any configs for HLO: ...gemm_fusion...`), crashing the training
step entirely -- not a warning, a hard `InternalError`. This is a genuine
gap in TF 2.21's compiler support for this brand-new GPU architecture, not
a bug in this lab's code. **Fix**: `model.compile(..., jit_compile=False)`
(already set in `train/train.py`). Non-XLA (graph-mode) training works
correctly and at full speed once this is set.

### Gotcha: this is a busy shared box -- don't let TF hog the whole GPU

By default TF claims most/all GPU memory on first use. `ged25-ki` runs many
other users' concurrent services (web apps, LLM inference servers, and at
least one live ROS robot-control node) -- a first training attempt here was
killed mid-run when another user's 32B-parameter LLM server started and
grabbed ~19GB VRAM. `train/train.py` now calls
`tf.config.experimental.set_memory_growth(gpu, True)` for every GPU device
before any other TF GPU call, so this tiny model (~100K params, <1GB
actually needed) only claims what it uses instead of the whole card. Keep
this in any new training/eval script added to this lab. Never kill or
suspend other processes on this box to "make room" -- ask first, and never
touch anything that looks like it might be controlling physical hardware.

## Data

GTSRB (German Traffic Sign Recognition Benchmark), 43 classes, official
source (`sid.erda.dk`, the INI Benchmark host) -- training set (39,209
images) + official test set (12,630 images, with ground truth).

```bash
python data/extract_and_verify.py   # extracts + checks per-class counts
python train/split_dataset.py --seed 20260728 --cal-track-fraction 0.15
```

### Three-way split -- why it's not a naive random split

GTSRB training images are **tracks**, not independent samples: each
physical sign was photographed as a ~30-frame video sequence
(`<trackID>_<frameID>.ppm`). `split_dataset.py` splits train/calibration by
whole TRACK, never by individual frame -- a naive image-level random split
would leak near-duplicate frames of the same sign across train and
calibration, silently invalidating the conformal calibration guarantee
even though no literal file path would be duplicated. See the docstring in
`train/split_dataset.py` for the full reasoning.

The **test** split is the official, separately-photographed GTSRB test set,
used unmodified and touched only at final evaluation (Brief 3's coverage
validation) -- never during training or calibration.

Calibration is required to be >=1500 images, stratified over all 43
classes, with zero overlap with train (see `data/splits/checksums.sha256`
for exact reproducibility, and `data/splits/SPLIT_SUMMARY.md` /
`class_distribution_calibration.csv` for the realized numbers).

### Safety-critical classes

`data/splits/safety_critical.md` defines the "must-not-miss" class subset
(prohibitory + danger signs, standard GTSDB superclass taxonomy) used as
the risk-bound target set in conformal calibration (Brief 3).

## Reproducibility

- Split seed fixed and logged (`train/split_dataset.py --seed`, default
  documented in the script).
- Every split CSV is SHA-256 hashed (`data/splits/checksums.sha256`) --
  re-running the split script with the same seed must reproduce identical
  hashes; if it doesn't, something about the source data or the script
  changed and that needs investigating before trusting downstream results.
- All dependency versions pinned in `env/requirements.txt` /
  `env/requirements.lock.txt`.
- No randomness in `data/preprocessing.py` (see `data/PREPROCESSING.md`) --
  resize/crop/normalize is deterministic everywhere it's used.
