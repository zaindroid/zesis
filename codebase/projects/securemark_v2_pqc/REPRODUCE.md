# Reproducing the SecureMark-V2 PQC results

Everything here runs on the FRDM-MCXN947. No RTOS, no debugger attached.

## What is EEMBC's and what is ours

- `codebase/securemark-v2/` is the upstream EEMBC repository
  (github.com/eembc/securemark-v2): the harness framework, the three suite
  definitions and their golden CRCs.
- Everything under `codebase/projects/securemark_v2_pqc/` is ours, plus the
  files added inside the EEMBC tree (`profile/ee_pqc.c`, `profile/th_pqc_support.c`,
  `profile/wolfssl_th_api/th_mlkem.c`, `th_mldsa.c`, and the classical wolfSSL shims).

The 20 post-quantum components and the `PQC_All` suite are ours.
**`PQC_All` and `PQC_TLS1.3` are not EEMBC scores.** EEMBC publishes no PQC
profile, so those components report a functional round-trip check plus a
synthesised regression CRC instead of a golden CRC match.

## 0. Prerequisites

| Item | Value used |
|---|---|
| Arm toolchain | `arm-gnu-toolchain-14.2.rel1` (arm-none-eabi) |
| MCUXpresso SDK | `codebase/sdk/mcuxsdk` |
| Build tool | CMake 3.30 + Ninja |
| Flash tool | `LinkServer.exe` (NXP), probe serial `0V5USKFHVAZTY` |
| Board | FRDM-MCXN947, debug USB connected, J24 jumper fitted |

## 1. Build the wolfSSL library (once)

Crypto-only, Cortex-M33, `-O2`, no heap.

```bash
cd H:/z_thesis/codebase
cmake -S wolfssl -B projects/securemark_v2_pqc/wolfssl-m33/build -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=projects/securemark_v2_pqc/arm-none-eabi.cmake \
  -DWOLFSSL_USER_SETTINGS=ON -DBUILD_SHARED_LIBS=OFF \
  -DCMAKE_C_FLAGS="-mcpu=cortex-m33 -mthumb -mfloat-abi=hard -mfpu=fpv5-sp-d16 -O2 \
  -I$(pwd)/projects/securemark_v2_pqc/wolfssl-m33 -Wno-error -UHAVE_CONFIG_H -DSINGLE_THREADED"
cmake --build projects/securemark_v2_pqc/wolfssl-m33/build --target wolfssl
```

Then archive the objects (the wolfSSL target does not produce the archive itself):

```bash
cd projects/securemark_v2_pqc/wolfssl-m33/build
find CMakeFiles/wolfssl.dir/wolfcrypt -name "*.obj" > /tmp/objs.txt
arm-none-eabi-ar rcs libwolfssl_crypto.a $(cat /tmp/objs.txt)
```

Configuration lives in `projects/securemark_v2_pqc/wolfssl-m33/user_settings.h`.

## 2. Standalone bench (sanity check first)

```bash
cd H:/z_thesis/codebase/projects/securemark_v2_pqc/bench
cmake --preset release && cmake --build release
```

Flash and capture:

```bash
LinkServer.exe flash -p 0V5USKFHVAZTY auto load \
  "release/pqc_bench_wolfssl_cm33_core0.bin:0x00000000"
python ../mldsa_bench_nxp/capture_serial.py COM9 results/bench_raw.txt 180
```

Expect 7 `SELF-CHECK: PASS` lines and one `PQC-CRC` per algorithm. The CRCs are
the regression invariant: they must match across builds and optimisation levels.

## 3. Full harness

```bash
cd H:/z_thesis/codebase/projects/securemark_v2_pqc/v2harness
cmake --preset release && cmake --build release
LinkServer.exe flash -p 0V5USKFHVAZTY auto load \
  "release/securemark_v2_pqc_cm33_core0.bin:0x00000000"
python ../mldsa_bench_nxp/capture_serial.py COM9 results/run.txt 2400
```

The run takes 20-30 minutes. It ends with `Computing suite scores...` and the
full score table. Confirm `0` occurrences of `ERROR` in the capture.

## 4. Scores and LaTeX

```bash
cd H:/z_thesis/codebase/projects/securemark_v2_pqc
python scripts/evaluate_securemark_v2_pqc.py v2harness/results/run.txt
python scripts/emit_latex_tables.py
```

The first validates every PQC regression CRC and writes
`v2harness/raw/SECUREMARK_V2_PQC_SUMMARY.csv`; the second writes the six
`results/latex/*.tex` tables.

## 5. Task 3A (128 KB firmware signing)

```bash
cd H:/z_thesis/codebase/projects/securemark_v2_pqc/task3a
cmake --preset release && cmake --build release
LinkServer.exe flash -p 0V5USKFHVAZTY auto load \
  "release/task3a_fw_verify_cm33_core0.bin:0x00000000"
python ../../mldsa_bench_nxp/capture_serial.py COM9 results/task3a_dist.txt 200
```

## Things that will bite you

- **Serial port locks.** Windows holds `COM9` after a reset with no owning
  process. Wait ~5 minutes or replug the MCU-LINK USB.
- **No probe detected.** The debug probe is on the same USB as the board.
  Replug it; J24 must be fitted or the target rail is unpowered.
- **A failing component used to hang the run.** The autotune loop in
  `profile/ee_bench.c` is now bounded (24 doublings). Before that fix a single
  failing classical component spun forever and the score section never printed.
- **RSA-4096** needs `SP_INT_BITS 4096` in `user_settings.h`
  (`RSA_MAX_SIZE` derives from it) or the Heavy suite aborts.
- **P-384 ECDH** needs `wc_ecc_set_rng` on the key under
  `ECC_TIMING_RESISTANT` or it fails with `MISSING_RNG_E` (-236).

## Where the numbers land

| Result | File |
|---|---|
| score table | `v2harness/results/*.txt` (stdout capture) |
| per-component ips + CRCs | `v2harness/raw/SECUREMARK_V2_PQC_SUMMARY.csv` |
| library matrix | `results/PQC_LIBRARY_CONFIG_MATRIX.csv` |
| paper tables | `results/latex/*.tex` |
| Task 3A | `task3a/results/task3a_dist.txt` |
