# Reproduce the results

Run everything from the repo root. Steps marked (hardware) need a board. The
rest run on a PC from the stored data.

## 1. Migration table (report section 4.1)

```
python codebase/projects/securemark_tls_mcxn947/migration_compare.py
```

Expect: L1 -9.1%, L3 +50.9%, L5 +125.9%.
Writes `results/MIGRATION_COMPARISON.md` and `migration_summary.csv`.

This uses the bare-metal ML-KEM at -O0. The cross-platform numbers in step 2
use Zephyr at -Os, so the two do not match. Keep them separate.

## 2. Cross-platform migration (section 4.2)

```
python codebase/projects/securemark_tls_esp32s3/cross_platform_compare.py
```

Expect: ESP32-S3 -82.1%, -72.9%, -62.2%.
Writes `results/CROSS_PLATFORM_MIGRATION.md`.

## 3. DTLS Connection-ID energy (section 5.1)

```
python codebase/projects/securemark_tls_mcxn947/dtls_cid_model.py
```

Expect the ESP32-S3 row at 1440 wake-ups/day to show a +1880% gain.
Writes `results/dtls_cid/daily_energy.csv` and the hourly plot.

## 4. Joint scheduler (section 6)

```
python codebase/training_archive/training/conformal/joint_scheduler.py
```

Expect the `learned` line on the test set: 45920.7 s, 2078.9 mJ, 0 misses.
The `naive` line is 78377.6 s, 3382.3 mJ, 70 misses.
Writes `results/learned_policy/JOINT_SCHEDULER_REPORT.md`.

## 5. Check the TTCA numbers

```
python codebase/training_archive/training/conformal/verify_ttca.py
```

Expect `VERDICT: ALL CHECKS PASS` and exit code 0. This recomputes every TTCA
number from the raw files without using the analysis scripts, so it is the
strongest check in the repo.

## 6. Pareto audit on the LTC (section on the learning extension)

```
python codebase/training_archive/training/conformal/pareto_audit.py
```

Expect `NO-GO on the LTC for the efficiency story`.
Writes `stage3_pareto_audit.png`.

## 7. SecureMark-TLS score, 14/14 CRC (hardware)

Build and flash first:

```
bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh build
bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh -p COM17 flash
```

Then capture serial. Expect `SecureMark-TLS Score is 1895` (ESP32-S3, -O2) and
`crc` matching `expected_crc` on all 14 components. The MCXN947 score is 5472;
that project builds with MCUXpresso and flashes with LinkServer.

## What needs a board

Only these need hardware: the SecureMark ports (step 7), the ML-KEM and ML-DSA
benchmarks, the PPK2 energy captures, and the GTSRB policy runs. Everything in
`codebase/training_archive/training/conformal/` and the `*_compare.py`,
`dtls_cid_model.py`, and `*analyze_*.py` scripts run on a PC.

## Section to folder map

| Report section | Folder |
|---|---|
| 1, 4.1 MCX migration | `codebase/projects/securemark_tls_mcxn947/` |
| 2 methodology | `mlkem_bench/`, `mldsa_bench_nxp/`, `dwt.h`, PPK2 scripts |
| 3 SecureMark profile | `securemark_tls_mcxn947/`, `securemark_tls_esp32s3/` |
| 4.2 ESP32 migration | `securemark_tls_esp32s3/`, `pqc_bench_zephyr/` |
| 5.1 DTLS CID | `securemark_tls_mcxn947/dtls_cid_model.py` |
| 5.2 ULPMark energy | `mlkem_bench/results/eembc_style/`, `pqm4_bench_mcxn947/` |
| 6 joint scheduler | `training_archive/training/conformal/joint_scheduler.py` |
| 7 rigor, decision equivalence | `gtsrb_multiexit/tools/golden/`, `conformal/split_dataset_fourway.py` |
| 8 references | `securemark-tls/`, `PQClean/`, `pqm4/` |

## Not in this report

TTCA, power-envelope leakage, obfuscation, pqm4 fault post-mortem, split
inference, and the RL simulations have code and results but belong in a
second report. Code: `mlkem_bench/activity_cnn.py`,
`gtsrb_policy_freerun/exit_leakage.cpp`, `conformal/selective_obfuscation.py`,
`conformal/ttca_aci.py`, `pqm4_bench_mcxn947/main.c`,
`gtsrb_policy_freerun/split_inference.cpp`, `security_selection_sim/`,
`swarm_coordination_sim/`.
