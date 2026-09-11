# SecureMark-TLS Energy — Cross-Platform (PPK2, ULPMark-style)

Measured on **both boards** with the PPK2 (10 kHz, 3.3 V assumed, free-running
firmware, serial/USB disconnected during capture):

| Metric | MCXN947 | ESP32-S3 |
|--------|---------|----------|
| Capture | `ppk_secureMark-TLS.csv` | `ppk-esp32_power captured.csv` |
| Idle baseline | 12.73 mA | 47.39 mA |
| Benchmark active window | 188.5 s | 245.2 s |
| Mean active current (above idle) | 2.47 mA | 29.54 mA |
| **Active power (above idle)** | **8.16 mW** | **97.48 mW** (12x) |
| Incremental energy (above idle) | 1,538 mJ | 23,902 mJ |
| Full-current energy (incl. idle) | 9,459 mJ | 62,244 mJ |

The ESP32-S3 draws ~6x more current than the MCXN947 even at idle (47 vs
12.7 mA) and ~12x more active power above idle (97.5 vs 8.2 mW) — the
classical ECC stack on the ESP32 is both slower *and* much more power-hungry.

## Energy per TLS-handshake ECC phase

Energy = measured active power × phase duration (phase durations from the
canonical cross-platform latency table — matched Zephyr ML-KEM on both
boards):

| Phase | MCX duration | MCX energy | ESP32 duration | ESP32 energy |
|-------|--------------|------------|----------------|--------------|
| Classical ECC (ECDH+1 sign+2 verify) | 166.1 ms | **1.36 mJ** | 495.2 ms | **48.27 mJ** |
| PQC ML-KEM-768 + ML-DSA-44 | 108.6 ms | 0.89 mJ | 88.8 ms | **8.66 mJ** |
| PQC ML-KEM-768 + ML-DSA-65 | 164.2 ms | 1.34 mJ | 134.0 ms | 13.06 mJ |
| PQC ML-KEM-768 + ML-DSA-87 | 229.1 ms | 1.87 mJ | 187.1 ms | 18.24 mJ |

## Headline (energy, same story as latency)

| Board | PQC 768+44 vs classical | PQC 768+65 | PQC 768+87 |
|-------|------------------------|------------|------------|
| MCXN947 | **−35%** | −1% | +38% |
| ESP32-S3 | **−82%** | −73% | −62% |

Because active power is ~constant for a given board (the CPU draws the same
current whether it runs ECC or lattice math), the **energy migration delta
equals the latency delta** on each board. On the ESP32-S3 the PQC migration
is a *strict energy win* (−62 to −82%): the classical ECDH/ECDSA in ESP-IDF's
mbedTLS is both slow and power-hungry, while PQClean lattice crypto is
comparatively cheap. On the MCXN947, PQC is energy-neutral at 768+65 and
cheaper at 768+44.

## Caveats

1. One capture per board (10 kHz, deterministic workload → ~±2% repeatability;
   a second capture would tighten the estimate).
2. 3.3 V assumed for both (PPK2 current × 3.3 V).
3. Incremental (above-idle) energy is the honest "cost of the crypto"; the
   full-current numbers attribute the idle draw to the workload.
4. The ESP32-S3's absolute numbers include the whole DevKitC (PSRAM, CP2102
   powered-off, native-USB circuitry); the board-level comparison is
   therefore at the *system* level, not the bare MCU die.

## Files

- `H:\z_thesis\energy resulkts\ppk_secureMark-TLS.csv` (MCX)
- `H:\z_thesis\energy resulkts\ppk-esp32_power captured.csv` (ESP32-S3)
- `securemark_tls_mcxn947/analyze_securemark_energy.py` (analysis)
