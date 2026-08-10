# Experiment #2 — Leakage-Aware Scheduler (C ∩ A)

**Date:** 2026-08-09
**Method:** trace-driven simulation on real measured costs (MCXN947), same
backlog/deadline model as the joint scheduler (Option C), with the
activity-leakage finding (Option A) as the threat model.

## The problem

Option A showed an attacker can identify crypto activity from the power
envelope (~100%). Option C's scheduler decides WHEN crypto runs. Together:
**the scheduler leaks its crypto schedule to a power-watching attacker.**

Defense: insert **dummy crypto steps** (matched energy/time profile) so the
attacker can't tell real from dummy — subject to the 33ms deadline and
energy budget.

## Threat model

Attacker = classifier over the crypto-activity timeline (naive: "every
observed step is real"). Defense reduces the attacker's accuracy by hiding
real steps among dummies. We report attacker accuracy + the fraction of real
steps hidden within ±1 frame of a dummy.

## Results (1230 frames, 123 real steps)

### ML-KEM-512 (step = 24.1ms < 33ms slot → SLACK exists)

| policy | misses | energy | attacker_acc | hidden |
|---|---|---|---|---|
| no_defense | 0 | 228.5 mJ | 100% | 0% |
| fixed_dummy | 0 | +99.2% | 50.2% | 99% |
| deadline_aware | 0 | +100% | 50.0% | 100% |
| **learned_obfusc** | **0** | **+50.4%** | **66.5%** | **50%** |

**learned_obfusc** targets 50% hidden (enough to break a confident attacker)
and pays only **+50% energy** (vs +100% for naive dummies), with **zero
deadline misses**.

### ML-KEM-768 (step = 38.7ms > 33ms slot → NO slack)

| policy | misses | energy | attacker_acc |
|---|---|---|---|
| no_defense | 6 | 271.8 mJ | 100% |
| fixed_dummy | 13 | +99.2% | 50.2% |
| deadline_aware | 6 | +0% | 100% |
| learned_obfusc | 6 | +0% | 100% |

At 768, **no dummy can be inserted without a deadline miss** (the real step
alone overruns its slot) → the defense is impossible; the attacker stays at
100%. fixed_dummy causes 13 misses (unacceptable).

## The honest headline

> **Leakage obfuscation requires crypto slack. The scheduler's security-level
> choice (C) determines whether activity-leakage defense (A) is even
> possible: at ML-KEM-512 it costs +50% energy for a 50% hidden fraction
> with zero deadline misses; at ML-KEM-768 it is infeasible.**

This is a NEW coupling discovered by combining C and A: **security level ⇒
leakability ⇒ defensibility.** It reframes the security-level choice as not
just a time/energy trade (C) but a **privacy/leakage trade** (A) — a richer
decision for the learned scheduler.

## Why SOTA-worthy

- First (to our knowledge) **deadline-aware crypto-obfuscation scheduler**
  for edge AI: the defense is *constrained by the perception deadline*, not
  free.
- The **security-level ⇒ defensibility coupling** is a new axis: you can't
  just pick the strongest crypto and add dummies — the strongest level may
  leave no room to hide, which itself leaks.
- Directly extends the thesis arc: certified anytime (risk) + certified
  latency (Exp #1) + now **leakage-aware scheduling** (privacy).

## Caveats (honest)

- Simulation (trace-driven on real costs); the dummy energy/time is modeled
  as identical to the real step — a real dummy implementation would need
  matched power profiling (firmware follow-up).
- Attacker model is naive (timing-pattern); a smarter attacker (e.g.,
  distinguishing dummy vs real by micro-architecture signature) would change
  the numbers — but the *slack constraint* (512 feasible, 768 not) is robust.

## Files
- `leakage_aware_scheduler.py` (simulation; `LEAK_LEVEL` env: 512/768)
- `results/leakage_aware/leakage_aware_summary.json`
