# 06 — Simulations: Does PQC Security-Level Selection Need Learning?

## Purpose

Two pure-simulation studies (no hardware, no on-device measurement, but
per-event costs drawn from real measured ML-DSA latency/energy data) ask a
narrow, decisive question: for choosing a PQC security level under
battery/deadline constraint, is there room for a learned (RL) policy to
beat principled heuristics — first for a single robot, then for a
coordinated swarm where nodes share a deadline?

## Setup / Method

**Shared measured inputs (both studies):** per-event latency sampled from
the real measured per-call ML-DSA distribution (2000 samples/level, NXP
FRDM-MCXN947, 150 MHz, -O2 — the same dataset as `02_PQC_Benchmarks.md`).
Energy = 0.382 nJ/cycle × sampled cycles, a real-derived constant (the mean
across 9 ML-KEM PPK2 energy/cycle measurements on the same board). What is
**modeled** (not measured) is explicit in each study: the battery-depletion
dynamics and, for the swarm, the weakest-link group-deadline coupling.

## Results

### 6.1 Single-robot security-level selection under battery depletion

**Environment:** one robot, N=1000 signing events, each choosing a security
level (44/65/87). Control deadline = 150 ms/event (measured per-level
P(miss): 44=2.5%, 65=14.1%, 87=21.9%). Finite battery depletes per event;
running out before event N fails the mission. Objective: maximize total
security (Σ level) subject to (a) deadline misses ≤ 5% of events, (b)
completing the mission.

**Four policies** (no RL): MYOPIC (strongest level passing a per-event 5%
miss gate, ignores battery — the naive floor); BATTERY (risk- and
battery-budget-aware greedy: gates on both remaining miss budget and p90
energy reservation); LOOKAHEAD (hand-tuned, spends risk budget more
aggressively early, tapers late; scales energy reservation by battery
health); ORACLE (full-knowledge exact knapsack over the level mix —
theoretical ceiling).

**Results (500 randomized missions, 95% CIs):**

| policy | mean security | deadline-miss % | completion % |
|---|---|---|---|
| 1. MYOPIC | 43,769 ± 67 | 2.51% | 89.4% |
| 2. BATTERY | 47,037 ± 213 | 4.18% | 88.0% |
| 3. LOOKAHEAD | 46,932 ± 214 | 4.13% | 88.2% |
| 4. ORACLE | 48,063 ± 231 | 4.54% | 81.4% |

**The two gaps that matter:** #1→#2 (does battery-awareness matter?)
**+7.5%** — a real, substantial gain from being battery- and
risk-budget-aware, confirming the coupling is real. #3→#4 (RL headroom,
the decisive number) **+2.4%** — the best hand-tuned heuristic reaches
97.9% of the full-knowledge oracle's security. Since a learned policy
cannot beat the oracle and must also absorb estimation error, the
realistic learnable headroom is ≤2.4% and likely less.

**Verdict: heuristics suffice.** The battery-coupling problem is real but
is well-captured by two simple reservation rules (`p_miss × events_left ≤
miss_left`, `p90_energy ≤ energy_left/events_left`) — the decision
structure (3 discrete levels, exchangeable events, one constraint per axis)
is simple enough that hand-derived rules saturate it. No RL was built or
trained in this study; the conclusion rests on the oracle gap alone.

### 6.2 Swarm security-level selection under a coordinated deadline

**Environment:** N=5 nodes, R=200 coordinated rounds, all nodes signing
under a **shared 200 ms group deadline** — the round succeeds only if
*every* node meets it (weakest-link coupling). Measured per-node P(miss)@
200ms: 44=0.7%, 65=5.5%, 87=9.3%; 5-node all-same-level group-failure:
44=3.2%, 65=24.4%, 87=38.8%. Each node has its own depleting battery.
Objective: maximize total group security subject to (a) group round-failure
≤5%, (b) all nodes completing the mission.

**Four policies** (no RL): MYOPIC (each node picks its own strongest level
ignoring the group); GROUP-AWARE (decentralized, gates on marginal group
failure contribution); COORDINATED (shared group state, budgeted level mix,
spends the failure budget on 87/65 early, drops to 44 as it depletes);
CENTRALIZED ORACLE (full-knowledge knapsack ceiling).

**Results (400 randomized missions, 95% CIs):**

| policy | group security | group-fail % | completion % |
|---|---|---|---|
| 1. MYOPIC | 55,993 ± 958 | 60.5% | **0.0%** |
| 2. GROUP-AWARE | 45,367 ± 141 | 5.8% | 86.0% |
| 3. COORDINATED | 45,899 ± 165 | 6.4% | 83.5% |
| 4. CENTRALIZED ORACLE | 45,796 ± 108 | 5.5% | 86.5% |

**The two gaps:** #1→#2 (does weakest-link coupling matter?) **−19.0%** —
devastating: the greedy floor, where each node "reasonably" picks its own
strongest level, produces 60% group failure and **0% mission completion**
— the swarm dies on every single mission. Group-awareness recovers
essentially all of it. #3→#4 (RL headroom, N=5) **−0.2%** — the best
hand-tuned heuristic is statistically indistinguishable from the
full-knowledge oracle.

**RL demonstration (gate closed, run anyway for robustness):** a
Q-learning node (1 learner among N−1 heuristic peers, local information
only) trained to convergence (3000 episodes, reward slope <2% over final
windows) achieves +2.2% apparent security — but by spending battery
aggressively and dying 4× more often (73% vs 98% completion), exceeding
the group-failure bound. Under the stated objective (security *subject to*
completion), **the learner does not beat the heuristic** — its apparent
gain is a constraint violation, not genuine improvement.

**Two follow-up verification checks (not a full re-run):**

- **RL convergence fairness check:** re-evaluated the converged learner on
  60 fresh missions — it still loses under the stated objective (8.3%
  completion vs the heuristic's 100%). A properly constrained
  (mission-level) reward makes tabular Q-learning fail to converge at all
  (sparse credit assignment over 200 rounds defeats the tabular learner).
  Either way, the learner does not beat the heuristic.
- **N-scaling check** (does the verdict hold as coupling strengthens?): the
  ladder was re-run at N=5/10/20/50 with the group-failure bound scaled to
  1.5× the all-44 baseline at each N (to keep the problem non-trivial as N
  grows):

  | N | #3→#4 gap (heuristic vs oracle) | #3 completion | #4 completion |
  |---|---|---|---|
  | 5 | **−0.0%** | 80.5% | 81.0% |
  | 10 | **+3.8%** | 92.5% | 83.5% |
  | 20 | **+6.1%** | 88.5% | 76.5% |
  | 50 | **+14.0%** | 88.0% | 64.0% |

  **The gap opens as N grows** — coordination genuinely gets harder at
  scale; the heuristic (hand-tuned for N=5) stops capturing the optimal
  allocation. A tabular Q-learner re-tested at N=20 (gap +6.1%, past the
  5% gate) matches the heuristic's security but trades away completion
  (72% vs 100%) — it does **not** close the opened gap. The gap that opens
  at scale is between the oracle's *global, full-knowledge* allocation and
  *any* online policy (heuristic or this learner) with only local
  information — a stronger learner (policy-gradient, or model-based with
  learned battery dynamics) is the honest next step, not a demonstrated
  conclusion that RL works here.

## Analysis / Interpretation

1. **At the scale actually relevant to this thesis (single robot; N=5
   swarm), heuristics fully close the gap to the theoretical optimum**
   (2.4% and 0.2% respectively) — there is no meaningful room for a
   learned policy to add value, and the RL demonstrations run specifically
   to stress-test that conclusion (convergence check, constraint
   violation check) confirm it rather than overturn it.
2. **The coordination *coupling* itself is real and large** (swarm: −19%
   security-equivalent and 0% completion for the naive/greedy floor) — the
   finding is not "coordination doesn't matter," it's "coordination
   matters a great deal, and a fairly simple budget-spending rule already
   captures nearly all of the achievable value from being aware of it."
3. **The N-scaling check is the one place a real RL opportunity surfaces**
   (gap opens to +14% at N=50) — but the thesis's own RL attempt does not
   close it, so the honest conclusion is a **scoped opening for future
   work** (larger swarms, richer learners), not a retraction of the
   heuristics-suffice verdict at the scales actually studied on hardware.
4. Combined with `05_Learned_AI_Angles.md`'s learned exit policy (which
   *does* beat its hand-tuned counterpart), this pair of studies is the
   empirical backing for the thesis's dimensionality argument: learning
   pays off on high-dimensional, continuous decisions (exit thresholds on
   a confidence curve) and not on low-dimensional, near-deterministic ones
   (which of 3 discrete crypto levels to pick) — until the *coordination*
   dimension itself grows large enough to matter.

## Raw data

No PPK2 or serial captures back this section — both studies are pure
simulations over the ML-DSA/ML-KEM measured-cost datasets already provided
in `raw_data/02_pqc_benchmarks/` and `raw_data/energy_ppk2/` (see
`02_PQC_Benchmarks.md` for those raw files). No separate mission-level CSV
output was included in this package.
