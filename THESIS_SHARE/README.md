# THESIS SHARE — Certified Anytime Perception under Post-Quantum Cryptographic Load

*Zain — M.Sc. Autonomous Systems, Hochschule Bonn-Rhein-Sieg.
Supervisors: Prof. Tschofenig, Prof. Houben.*

This package contains the **reports, results, and raw measurement data** of
the thesis, organized by experiment → board → results. Everything here is
either **hardware-measured** (PPK2 energy, serial captures from the boards) or
**reproducible from the raw files** (analysis scripts in `codebase/`, indexed
in `code/README.md`).

## The thesis in one paragraph

A multi-exit neural traffic-sign classifier (GTSRB, 3 exits at 30/60/100%
depth) with **provably bounded risk** (split-conformal certification) shares
an MCU with post-quantum cryptography (ML-KEM, ML-DSA). An anytime controller
adapts both decisions — how deep to perceive and how much crypto to run —
under a 33 ms real-time deadline. The PQC cost that drives this is benchmarked
EEMBC-style against the classical baseline it replaces (SecureMark-TLS),
measured on two platforms in latency **and** energy, and extended with
life-cycle (DTLS Connection-ID), portability (M4F→M33), and side-channel
(leakage, obfuscation, TTCA) experiments.

## Package layout

```
THESIS_SHARE/
├── 00_thesis_overview/        the narrative documents (start here)
├── 01_anytime_perception/     the core: certified 3-exit model + interleaved
│                              crypto+perception + free-running energy
├── 02_pqc_benchmarks/         ML-KEM / ML-DSA / pqm4, per board (mcxn947,
│                              esp32s3, zephyr, stm32n6570)
├── 03_classical_baseline/     EEMBC SecureMark-TLS (both boards) + the
│                              classical→PQC migration comparison
├── 04_security_side_channels/ activity/exit leakage, obfuscation,
│                              split-inference, DTLS Connection-ID
├── 05_learned_ai_angles/      learned exit policy, joint scheduler, TTCA
│                              (Stage-1 result + Stage-3 Pareto audit)
├── 06_simulations/            pure-simulation studies (heuristics vs RL)
├── data/
│   ├── energy_ppk2/           ALL PPK2 captures, renamed descriptively
│   └── serial_captures/       ALL serial logs from the boards, renamed
├── code/README.md             index of the working codebase (what/where/how)
└── MANIFEST.json              source→destination map for every file
```

## How to read this (recommended order)

1. **`00_thesis_overview/MILESTONE_REPORT.md`** — the master document: the
   full arc with all key result tables.
2. **`00_thesis_overview/THREE_EXPERIMENTS_THESIS_REPORT.md`** — the
   amortization/portability/obfuscation layer, with the thesis significance.
3. **`00_thesis_overview/MEETING_HANDOUT_CORRECTIONS.md`** — the
   LNN+TTCA corrections, meeting-ready.
4. Then per experiment folder: `report/` first, `results/` second, and the
   raw captures under `data/` for the energy/serial numbers.

## The key numbers (quick reference)

| Result | Value | Where |
|--------|-------|-------|
| Certified early-exit savings (interleaved) | −14–15% time vs naive, no risk increase | 01/ |
| Frozen conformal certification | 6/9 tiers certified (honest, single-touch test) | 01/ (MILESTONE §2) |
| Joint learned scheduler | −41% time, −39% energy, 0 deadline misses | 05/joint_scheduler |
| ML-DSA fat tail | worst/median 6–8×, identical across boards | 02/ |
| SecureMark-TLS | 5472 marks (MCXN947), 1895 (ESP32-S3), 14/14 CRC both | 03/ |
| PQC migration (TLS ECC phase) | MCX −35…+38%; ESP32 −62…−82% | 03/migration |
| PQC 768+87 handshake energy | 1.87 mJ (MCX) / 18.24 mJ (ESP32) | 03/migration + data |
| DTLS CID battery gain | up to 19× (ESP32, 1/min wake-ups) | 04/dtls_cid |
| M4F→M33 fault | CFSR=0x00100000 (UNSTKERR), HFSR FORCED | 02/mcxn947 |
| Crypto-activity leakage | 99.8% RF classification | 04/activity_leakage |
| Exit-decision leakage | 98.3% RF classification | 04/exit_leakage |
| Selective obfuscation @768 | attacker 100% → 75.5% (p=0.3), +32.5% energy | 04/obfuscation |
| TTCA under shift | static 95.8→48.6%; ACI 93.9% at +3.3% compute | 05/ttca |
| LTC Pareto audit | NO-GO (exit2 = 99% of exit3 accuracy at 53% cost) | 05/ttca |

## Data naming conventions

- `data/energy_ppk2/energy_<experiment>_<detail>_<board>.csv` — PPK2 Ampere
  Meter / supply-mode captures (10 kHz, 3.3 V assumed).
- `data/serial_captures/serial_<experiment>_<detail>_<board>.txt` — raw serial
  logs from the boards (115200 baud, USB-Serial console).

## Reproducibility

Every table in the reports is recomputable:
- analysis scripts live in `codebase/` (see `code/README.md` for the index);
- the TTCA results are independently verified by
  `codebase/training_archive/training/conformal/verify_ttca.py`
  (exit code 0 = all checks pass).

*Boards: FRDM-MCXN947 (Cortex-M33 @150 MHz + eIQ Neutron NPU), ESP32-S3
(Xtensa LX7 @240 MHz). Instruments: nRF PPK2 (10 kHz energy), LinkServer /
esptool (flashing), serial consoles.*
