# Certified anytime perception under post-quantum cryptographic load

M.Sc. thesis — Zain Ul Haq, Hochschule Bonn-Rhein-Sieg.

Two questions, both answered with measurements on real hardware:

1. **Can a neural network give provable risk bounds while running on a microcontroller?**
   A three-exit traffic-sign classifier where each exit carries a conformal (distribution-free)
   safety certificate, so you can stop early and still know the risk.
2. **What does post-quantum crypto cost on that same chip, and does it break the deadline?**
   ML-KEM-768 and ML-DSA-44/65/87 benchmarked in EEMBC's SecureMark-V2 harness, next to the
   classical P-256 baseline.

Boards: FRDM-MCXN947 (Cortex-M33 @ 150 MHz, eIQ Neutron NPU) and ESP32-S3 (Xtensa LX7 @ 240 MHz).

## Headline results

| Result | Number | Where |
|---|---|---|
| Three-exit model, validation accuracy | exit1 73.3% · exit2 92.3% · exit3 93.1% (single-exit control 94.5%) | `TRAINING_EVIDENCE.pdf` |
| Certified risk tiers | **6 of 9** pass the frozen protocol (safety-critical miss ≤ α on a single test touch) | `data/splits/` + `coverage_validation_table.csv` |
| Conformal coverage under distribution shift | static collapses 95.8% → 48.6%; adaptive (ACI) holds 93.9–94.9% at +3.3% compute | `results/ttca/` |
| PQC handshake vs classical (same library, `-O2`) | **+4.9%** — 99.5 ms vs 94.9 ms | `SECUREMARK_V2_TSCHOFENIG_REPORT.pdf` |
| Library choice vs algorithm choice | **2.41x** spread at identical flags (wolfSSL 6.37 ms vs PQClean 15.33 ms, ML-KEM-768 encaps) | `results/PQC_LIBRARY_CONFIG_MATRIX.csv` |
| 128 KB firmware verification | HashML-DSA-65 **24.45 ms** beats ECDSA P-256 **26.70 ms** | `task3a/results/` |
| ML-DSA signing tail | worst/median up to **6.9x** — median fits a 10 Hz budget, worst case does not | `results/task3b/` |
| Joint exit + crypto scheduling | −41% time, −39% energy, 0 deadline misses vs naive (simulation on measured costs) | `results/learned_policy/` |

## Start here

Three PDFs, written to be read in this order:

| File | What it covers |
|---|---|
| `SECUREMARK_V2_TSCHOFENIG_REPORT.pdf` | the PQC benchmarking brief: harness, scores, PQC vs classical, library matrix, and a status table of what is done and open |
| `AI_EVIDENCE_HOUBEN.pdf` | the perception side: model, training, conformal certification, adaptive conformal, and the LTC no-go decision |
| `TRAINING_EVIDENCE.pdf` | the trained model in detail: architecture, config, curves, checkpoints |

## Folder map

| Path | Contents |
|---|---|
| `codebase/training_archive/training/` | model training, four-way data split, conformal calibration, learned policies |
| `codebase/projects/securemark_v2_pqc/` | EEMBC harness port + the 20 post-quantum components we added |
| `codebase/projects/mlkem_bench/`, `mldsa_bench_nxp/` | standalone per-primitive benchmarks (clean C) |
| `codebase/projects/gtsrb_policy_freerun/` | on-device multi-exit firmware, energy captures |
| `codebase/projects/gtsrb_multiexit_esp32s3/` | ESP32-S3 port of the perception benchmark |
| `codebase/projects/pqc_bench_zephyr/` | the same PQC primitives under Zephyr, both boards |
| `MODEL_FILES/` | the trained model: `.tflite` (self-contained), weights, architecture diagram |
| `energy resulkts/` | raw PPK2 power traces (not committed — 300 MB+) |

## Reproduce one result

Training and conformal certification (needs TensorFlow):

```bash
cd codebase/training_archive/training
python train/split_dataset_fourway.py     # frozen 75/15/10 split, seed 20260728
python train/train.py --config train/configs/multiexit.yaml
python conformal/calibrate.py             # tau per (exit, alpha) on calibration only
```

The PQC benchmark has its own recipe with the exact toolchain paths:

```bash
cat codebase/projects/securemark_v2_pqc/REPRODUCE.md
```

## What was actually trained, and what was not

Worth being precise, because three of these are often described loosely:

| Component | Mechanism | Trained by gradient descent? |
|---|---|---|
| Three-exit classifier | MobileNetV1-style CNN, 104,721 params, INT8 | **yes** |
| Single-exit control | same backbone, one output | **yes** |
| Conformal thresholds (τ) | split-conformal quantile over the calibration split | no — a finite-sample quantile |
| Learned exit policy | isotonic (PAVA) risk curves from calibration | no — a curve fit |
| Adaptive conformal (ACI) | online α update from observed errors | no — an update rule |
| Joint exit + security-level scheduler | trace-driven simulation over measured costs | no — a simulator |

There is **no jointly trained PQC + perception network**. Only `train.py` and `quantize.py` do
gradient training, and both train the perception model.

## Provenance

`codebase/securemark-v2/` is EEMBC's repository (github.com/eembc/securemark-v2) and is
**not vendored here** — clone it. The harness framework, the three suite definitions and their
golden CRCs are EEMBC's. The 20 post-quantum components, the PQC shims and the `PQC_All` suite
are ours. **`PQC_All` is not an EEMBC score**: EEMBC publishes no PQC profile, so those
components report a functional round-trip check plus a synthesised regression CRC instead of a
golden CRC match.
