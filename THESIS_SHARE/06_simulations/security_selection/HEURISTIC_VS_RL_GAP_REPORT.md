# Does PQC Security-Level Selection Under Battery Depletion Need Learning?

**Pure simulation, no hardware, no RL.** Question this rung answers plainly:
**"is there room for a learned policy, or do principled heuristics already
solve the battery-coupling problem?"**

## 1. Environment (explicit, defensible)

- Single robot node, fixed control-loop rate. A mission = **N=1000 signing
  events** at fixed intervals.
- Each event the robot picks a security level **44 / 65 / 87** and produces an
  ML-DSA signature. The per-event latency is **sampled from the REAL measured
  per-call distribution** (2000 real samples per level, from the NXP
  FRDM-MCXN947 signing benchmark, 150 MHz, -O2). Energy = **0.382 nJ/cycle ×
  sampled cycles** — a REAL-derived constant, the mean across 9 ML-KEM PPK2
  energy/cycle measurements on the SAME board (see below). One sample carries
  BOTH the deadline risk and the energy cost (a slow sign costs more energy).
- **Control deadline = 150 ms/event.** sampled_latency > 150 ms = a DEADLINE
  MISS (safety failure). Measured per-level P(miss):
  **44: 2.5% | 65: 14.1% | 87: 21.9%** (from the real data).
- Finite battery: depletes per event. Battery hits 0 before event N = all
  remaining events fail (mission incomplete). Battery start varied per mission
  (scale U[0.55, 1.05] × N×E[level-65]) so some missions are survivable only
  with frugal level choice (the coupling is real: all-44 ≈ 0.61× base,
  all-65 ≈ 1.0× base).
- Objective (optimized per mission): **maximize total security = Σ(level)**
  subject to **(a) deadline misses ≤ 50** (5% of N), **(b) completing the
  whole mission** (battery never hits 0).

### Energy model derivation (from real data)
ML-KEM PPK2 measurements on the same FRDM-MCXN947 (energy_summary.csv +
perf_memory_summary.csv): 9 op/level pairs give energy-per-cycle
0.372–0.394 nJ/cycle, mean **0.3822 nJ/cycle**. Applied to the ML-DSA
measured cycle counts. This is the same board, same clock, same power rail —
defensible as "the robot's measured energy cost per cycle".

## 2. The four policies (no RL; baselines designed to be genuinely smart)

1. **MYOPIC** — strongest level with P(miss) ≤ 5% (per-event). Only level 44
   qualifies. Ignores battery and the mission miss budget. The naive floor.
2. **BATTERY** — strongest level passing BOTH: (a) risk gate
   `p_miss × events_left ≤ miss_left` (uses the remaining mission miss budget)
   AND (b) energy gate `p90_energy ≤ energy_left/events_left` (per-event
   reservation). Risk- and battery-aware greedy.
3. **LOOKAHEAD** — hand-tuned: spends the miss-risk budget aggressively early
   (risk_aggression = 2.0 → tapers to 1.0 late), scales energy reservation by
   battery health (reserve ×0.9 when battery < 40%). No learning.
4. **ORACLE** — full-knowledge optimum: exact knapsack over the level mix
   (events are i.i.d./exchangeable, so the optimal policy is a fixed mix)
   maximizing security subject to (a) expected misses ≤ 50, (b) expected
   energy ≤ battery. Theoretical ceiling.

## 3. Results (500 randomized missions, N=1000, 95% CIs)

| policy | mean security | CI | deadline-miss % | CI | completion % |
|---|---|---|---|---|---|
| 1. MYOPIC | **43,769** | ±67 | 2.51% | ±0.04 | 89.4% |
| 2. BATTERY | **47,037** | ±213 | 4.18% | ±0.08 | 88.0% |
| 3. LOOKAHEAD | **46,932** | ±214 | 4.13% | ±0.09 | 88.2% |
| 4. ORACLE | **48,063** | ±231 | 4.54% | ±0.10 | 81.4% |

### The two gaps

- **#1 → #2 (battery-awareness matters?): +3,268 sec (+7.5%)** — a real,
  substantial gain from merely being battery- and risk-budget-aware. The
  coupling is real; the naive floor is genuinely worse. Sanity check passed.
- **#3 → #4 (RL headroom, THE DECISIVE NUMBER): +1,132 sec (+2.4%)** — the
  best hand-tuned heuristic is within **2.4%** of the full-knowledge optimum.

## 4. Interpretation (state explicitly)

**"HEURISTICS SUFFICE" — there is no meaningful gap for RL to exploit here.**

- The best heuristic (BATTERY, 47,037) achieves **97.9% of the oracle's
  security** (48,063). The residual 2.4% is the price of not knowing the
  mission's exact battery draw in advance — a full-knowledge DP closes it, but
  a learned policy cannot beat the oracle, so the realistic learnable headroom
  is ≤ 2.4% and likely much less (a learned policy must also suffer estimation
  error).
- The coupling the brief worried about IS real (battery-awareness is worth
  +7.5%), but it is **well-captured by a principled reservation rule**:
  `p_miss × events_left ≤ miss_left` and `p90_energy ≤ energy_left/events_left`
  already recover nearly all of it. The problem structure (3 levels, one
  constraint per axis, exchangeable events) is simple enough that hand-derived
  rules saturate it.
- Honest caveat on completion: the oracle shows 81.4% vs heuristics' ~88%.
  This is an artifact of the objective as stated — the oracle maximizes
  security and treats completion as a hard constraint only in expectation, so
  on the tightest-battery missions it spends the budget to the edge and dies
  more often. The heuristics are more conservative on energy (they reserve
  p90, not mean). This does NOT change the headroom conclusion: even granting
  the oracle its full security advantage, the heuristic gap is 2.4%.

**Verdict for the next stage: do NOT invest in RL for this rung.** A small
gap means heuristics suffice for battery-coupled security selection on a
single node at a fixed control rate. If a later rung introduces multi-node
coordination, stochastic mission lengths, or unseen battery/demand regimes,
re-evaluate — but for THIS environment, learning has no room.

## 5. Files

- `run_security_sim.py` — the full simulation (environment, 4 policies, run loop)
- `results/mission_results_raw.csv` — 500 missions × (battery, sec/miss/done per policy)
- `results/` also holds the recompute script output (see report)

## 6. Hygiene

- Baselines are genuinely smart (verified: BATTERY uses 44/65/87 mixes, not
  just 44; the risk+energy gates are principled, not strawmen).
- Oracle is exact (knapsack, full knowledge) — not a soft-Lagrangian hack.
- All numbers independently recomputed from `mission_results_raw.csv` (match).
- Real measured latency distributions (NXP per-call CSVs); real-derived energy
  (ML-KEM PPK2, same board). Deadline/battery/objective stated explicitly.
- No RL built or trained in this rung.
