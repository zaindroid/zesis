# Code Index — where the working code lives

The firmware projects in this thesis are **SDK-tangled** (NXP MCUXpresso /
ESP-IDF / Zephyr build trees, board files, toolchain paths) — they are not
portable as plain copies. This index tells you what exists, where, and how to
build it. All paths are relative to `H:\z_thesis\`.

## Hardware projects

| Project | Board | What it does | Build |
|---------|-------|--------------|-------|
| `codebase/projects/gtsrb_multiexit/` | MCXN947 | 3-exit GTSRB classifier on the eIQ Neutron NPU + golden deployment validation | MCUXpresso SDK CMake |
| `codebase/projects/gtsrb_policy_singlecore/` | MCXN947 | interleaved crypto+perception policies (NAIVE/STATIC/ADAPTIVE), 1230-frame workload | MCUXpresso |
| `codebase/projects/gtsrb_policy_freerun/` | MCXN947 | free-running variants (incl. POLICY_LEARNED), split-inference, exit-leakage, PPK2-validated | MCUXpresso |
| `codebase/projects/mlkem_bench/` | MCXN947 | ML-KEM-512/768/1024 benchmark (latency, stack, energy) + activity-leakage mode | MCUXpresso |
| `codebase/projects/mldsa_bench_nxp/` | MCXN947 | ML-DSA-44/65/87 signing-latency benchmark (fat-tail, retry counting) | MCUXpresso |
| `codebase/projects/pqm4_bench_mcxn947/` | MCXN947 | pqm4 M4F-asm benchmark + the fault-register post-mortem firmware | MCUXpresso |
| `codebase/projects/securemark_tls_mcxn947/` | MCXN947 | official EEMBC SecureMark-TLS port (mbedTLS 3.6.3) + DTLS-CID model | MCUXpresso |
| `codebase/projects/gtsrb_multiexit_esp32s3/` | ESP32-S3 | ESP-IDF port: policy app + ML-DSA bench (2000 signs/level) | ESP-IDF v5.4 (`scripts/build.sh`) |
| `codebase/projects/securemark_tls_esp32s3/` | ESP32-S3 | SecureMark-TLS port (ESP-IDF mbedTLS), -O2 | ESP-IDF (`scripts/build.sh`) |
| `codebase/projects/pqc_bench_zephyr/` | both | ML-KEM-768 + ML-DSA-44/65/87 under Zephyr RTOS (the matched cross-platform dataset) | west build |
| `codebase/projects/pqc_bench_stm32n6_baremetal/` | STM32N6570 | bare-metal port (status: buildable, console silent — documented) | bare gcc |

## Training / analysis / simulation

| Path | What it contains |
|------|------------------|
| `codebase/training_archive/training/train/` | model training, the frozen four-way split (`split_dataset_fourway.py`) |
| `codebase/training_archive/training/conformal/` | conformal calibration, margin derivation, coverage validation, learned exit policy, joint scheduler, leakage-aware scheduler, selective obfuscation, **TTCA (ttca_aci.py)**, Pareto audit, **independent verification (`verify_ttca.py`)** |
| `codebase/training_archive/training/build_freerun_workload.py` | 1200-frame natural-frequency workload generator |
| `security_selection_sim/` | single-node battery-aware security-level selection (heuristics vs RL) |
| `swarm_coordination_sim/` | coordinated-deadline swarm simulation (+ RL-convergence and N-scaling verification) |

## Third-party code (vendored, not ours)

- `codebase/pqm4/` — pqm4 (M-profile optimized PQC, M4F asm)
- `codebase/securemark-tls/` — official EEMBC SecureMark-TLS source
- `codebase/wolfssl/`, `codebase/sdk/` — wolfSSL / NXP MCUX SDK (heavy, not packaged)

## The two commands that reproduce the headline analyses

```bash
# TTCA + Pareto audit (all numbers independently verified):
python codebase/training_archive/training/conformal/verify_ttca.py   # exit 0 = all pass

# SecureMark migration + energy synthesis:
python codebase/projects/securemark_tls_esp32s3/cross_platform_compare.py
```

## Note on the training data

The GTSRB dataset and the frozen split CSVs live on the training machine
(`ged25-ki:~/z_thesis/training/`); the local archive holds the splits and
results under `codebase/training_archive/training/`.
