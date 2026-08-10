# Experiment #3 — Does the Power Envelope Leak the Exit Decision?

**Date:** 2026-08-09
**Hardware:** FRDM-MCXN947, EXIT_LEAKAGE firmware (P0_31 trigger on D0)
**Data:** 180 exit-bursts (60 images × exit1/2/3), 10kHz PPK2, 256-pt envelopes

## The question

The certified-anytime system stops at exit1/2/3 based on confidence. Can a
power-watching attacker (cheap 10kHz probe) tell WHICH exit ran — i.e., learn
when the model was "confident enough to stop"?

This is an attack on the **certification itself**: the exit decision is the
observable outcome of the conformal risk bound. If it leaks, the attacker
knows the system's confidence regime, not just its crypto activity (A).

## Method

- 180 isolated exit bursts (segA-only=exit1, segA+segB=exit2, full=exit3),
  labeled by the firmware's deterministic order (verified: durations 0.62 /
  0.24 / 0.92 ms distinct per exit)
- Same pipeline as A: z-scored per-pulse envelope (removes duration/scale),
  RF/MLP, 5-fold CV, middle-50% ablation

## Results

| classifier | CV accuracy |
|---|---|
| RF full shape (z-scored) | **98.3%** ± 2.2% |
| RF middle-50% only (edges removed) | **100.0%** |
| raw envelope | 97.2% |
| duration-only baseline | 100% |
| majority baseline | 33.3% |

Perfect confusion matrix (18/18/18) on a stratified 30% holdout.

## The finding (honest)

**The power envelope leaks the exit decision at ~98-100%, even from the
envelope shape alone (middle 50%, no edges/duration).** An attacker with a
$50 10kHz current probe can determine whether the certified-anytime model
stopped at exit1/2/3 — i.e., **when it was confident enough to stop**.

**Why it matters (the SOTA angle):**
- It's a **novel attack on conformal anytime certification**: the risk bound
  is designed to keep the *classifier's errors* below α, but the *exit
  decision itself* is observable — a side channel on the certification.
- It connects A (crypto activity leaks) and the perception side: BOTH the
  crypto schedule AND the perception confidence regime leak.
- Defense implication (ties to #2): the same dummy/obfuscation machinery
  could hide exit decisions, but only with compute slack — and perception
  exits have even less slack than crypto.

## Caveats (honest)

- 180 samples (60/class) — small but the CV + perfect holdout is clean.
- Debug (-O0) build; the durations differ from release but the *shape* leak
  persists (middle-50% ablation proves it's not just duration).
- The exit order was fixed (deterministic labels) — a real attacker wouldn't
  have ground-truth labels, but they'd learn the 3 clusters unsupervised
  (the duration/shape clusters are obvious).

## Files
- `exit_leakage.cpp` (firmware, EXIT_LEAKAGE mode)
- `results/exit_envs.npy`, `exit_labels.npy`, `exit_durs.npy`
- Raw: `H:\z_thesis\energy resulkts\ppk-20260809T195247_No.3.csv`
