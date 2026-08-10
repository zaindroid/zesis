# Experiment #5 — Battery-Voltage-Aware Security Level: MEASURED

**Date:** 2026-08-10
**Hardware:** FRDM-MCXN947, ML-KEM-1024 benchmark (100 handshakes)
**Method:** PPK2 Power Supply mode + USB (debugger powered), J24 bridged,
voltage sweep 3.3V → 2.7V → 2.4V → 2.2V. Each capture = full benchmark run.

## The question
Does crypto latency (and energy) change with supply voltage, as a battery
sags? Should the scheduler be voltage-aware?

## Measured results (real PPK2 readings)

| Voltage | Active time (100 handshakes) | Energy | Mean power |
|---|---|---|---|
| 3.3V | 18.46 s | 972.2 mJ | 52.7 mW |
| 2.7V | 18.46 s | 860.4 mJ | 46.6 mW |
| 2.4V | 18.46 s | 729.8 mJ | 39.5 mW |
| 2.2V | 18.46 s | 645.6 mJ | 35.0 mW |

*(Active-window detection validated: each trace shows the benchmark signature
— ~14mA baseline, ~16-17mA active burst, 1 rising edge = single continuous
run. Energy = ∫V·I·dt over the active window with the actual supply V.)*

## Findings (honest)

1. **Latency is CONSTANT from 3.3V down to 2.2V (18.46s, ±0.01s).** The CPU
   clock holds across the sweep; ML-KEM crypto does NOT slow as voltage
   drops — until the board would brown out below 2.2V. 
   
   **Implication for the scheduler:** a voltage/battery-state input for
   *latency* is NOT needed — the certified τ (Exp #1) stays valid across the
   operating voltage range. This is the "simpler outcome" (a), measured.

2. **Energy drops 33.6% (972 → 646 mJ) from 3.3V → 2.2V** at the same
   latency. Lower supply voltage = less power per crypto op, because power
   ∝ V·I and the current stays roughly constant (~16mA) while V drops.

   **Implication (non-obvious):** a *low battery is more energy-efficient
   per handshake*. The scheduler could even prefer running crypto at lower
   voltage (if the system had voltage control) — a genuinely novel angle.

## Honest interpretation for the thesis

- The feared scenario ("crypto slows as the battery sags, breaking the
  deadline") **does not occur** on this hardware in 3.3→2.2V: latency is
  flat, so the conformal latency certificates (#1) hold unchanged.
- The real voltage effect is **energy, not time**: 34% less energy per
  handshake at 2.2V. This connects to the battery-aware scheduling story:
  the scheduler's energy model should use the voltage-dependent per-op
  energy, while the latency model stays voltage-independent.
- **Caveat:** the MCU's internal regulators may hold the core voltage
  constant even as the rail drops (the rail was measured, not the core).
  The *system-level* result (what the battery sees) is what matters for
  scheduling, and that is what we measured.

## Files
- `ppk_v33.csv`, `ppk_v27.csv`, `ppk_v24.csv`, `ppk_v22.csv`
  (`H:\z_thesis\energy resulkts\`)
- `voltage_sweep.py` (analysis)
- Board restored: J24 jumpered, USB power, benchmark verified.
