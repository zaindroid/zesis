# Experiment #5 — Battery-Voltage-Aware Security-Level Selection

## The idea (SOTA angle)

Real batteries sag under load and drain: the MCU's supply voltage drops from
3.3V → 2.4V over a battery's life. Question: **does crypto latency change
with supply voltage?** If ML-KEM ops slow down at lower voltage (the CPU
can't sustain its clock / marginal timing), then the **scheduler must pick
the security level from battery state** — a new input to the joint scheduler
(C) that is never considered in the literature (which assumes fixed VDD).

## Why it's SOTA

- "Battery-state-aware PQC security-level selection" with **real measured
  voltage-scaling data** on an MCU — I'm not aware of this being measured.
- It extends the joint scheduler (C): the learned security-level rule gains
  a **voltage/battery-state input** alongside deadline and energy.

## Measurement method (uses the PPK2's voltage control)

The nRF PPK2 can **supply a settable voltage** (0.8-5.0V) to the DUT via the
J24 rail. Procedure (user):

1. Flash the ML-KEM benchmark firmware (`mlkem_bench`, ML-KEM-1024, REPS=100)
2. Set PPK2 output voltage to 3.3V → arm → reset → capture the run
   (save `ppk_v33.csv`)
3. Repeat at **3.0V, 2.7V, 2.4V** (or as low as the board stays stable)
   → save `ppk_v30.csv`, `ppk_v27.csv`, `ppk_v24.csv`
4. The PPK2 trace's **active-window duration** = the wall-time latency of the
   100-handshake run at that voltage (the benchmark runs back-to-back ops;
   the trace's active burst duration scales with per-op latency)

## Analysis (I do after capture)

- Extract active-window duration per voltage from each trace
- latency(V) table + relative slowdown vs 3.3V
- Fit: does latency scale with voltage (e.g., ~1/V^2 like CMOS delay)?
- Implication: at battery-low voltage, the certified τ (Exp #1 machinery)
  must be **re-derived** (larger), OR the scheduler drops to a lower
  security level to stay within the deadline — the voltage-aware rule

## Expected honest outcome (hypothesis)

- At constant 150MHz clock, cycles stay constant but **wall time may stay
  constant too** (the clock holds until the voltage can't sustain it, then
  the chip browns out / the PLL drops). The interesting regime is the
  **marginal one**: near the brown-out threshold, either (a) the clock
  holds → no latency change (the chip runs until it dies), or (b) the
  clock/PLL degrades → latency grows sharply.
- Either outcome is a real finding: (a) means the scheduler's security-level
  rule is voltage-robust until death (simpler than feared); (b) means a
  voltage-aware rule is REQUIRED (the new angle).

## Files
- This protocol
- After capture: `voltage_sweep.py` analysis + `VOLTAGE_SWEEP_REPORT.md`
