# SecureMark-TLS PPK2 Energy Capture Protocol (FRDM-MCXN947)

Goal: measure the **total energy** of a full SecureMark-TLS benchmark run on
the FRDM-MCXN947 (classical TLS crypto), so it can be compared ULPMark-style
against the existing ML-KEM/ML-DSA energy numbers
(`mlkem_bench/results/eembc_style/energy_summary.csv`).

## Firmware state (already prepared)

- The MCXN947 currently runs the free-running SecureMark-TLS firmware
  (`debug/securemark_tls_mcxn947_cm33_core0.bin`, 14/14 CRC build, score
  5472). It starts the benchmark automatically at boot and idles afterwards.
- The full run takes ~2 minutes (fixed iterations, 14 components).
- **No debugger and no serial terminal may be connected during capture.**

## Physical setup (same as previous PPK2 runs)

1. Remove the J24 jumper so the MCU rail (P3V3_MCU) is powered through the
   PPK2.
2. PPK2 in **Ampere Meter mode** (VIN/VOUT across the J24 break).
3. nRF Connect / PPK2 software: sample rate **10 kHz**, log to CSV.
4. USB of the MCU-LINK debugger: keep it connected ONLY if the board needs
   external power; the previous captures used "USB connected + PPK2 ammeter"
   on J24 (do NOT use PPK2 power-supply mode — that failed on this board).

## Capture procedure

1. Start the PPK2 recording.
2. Press the board **reset button** (or power-cycle) so the benchmark starts
   at a known time.
3. Wait for the run to finish: **~130 s** (you can also stop at ~150 s; the
   benchmark idles after completion — the active window is the first ~2 min).
4. Stop the recording and export the CSV.

Expected signature: a ~2-minute high-current window (~15-17 mA mean with
per-component steps) followed by a drop to the idle baseline.

## Deliverable

- Save the CSV to `H:\z_thesis\energy resulkts\ppk_securemark_<timestamp>.csv`
- Tell the assistant the filename; it will run
  `analyze_securemark_energy.py` (trapz integration, active-window detection,
  per-phase energy) and produce the ULPMark-style energy table.
