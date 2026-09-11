# Verification Checks on the Coordinated-Deadline Swarm Result

Two targeted checks on the existing heuristics-suffice (N=5) finding. The
full experiment was NOT re-run — these verify two specific threats to the
conclusion. Per-node costs remain the REAL measured ML-DSA latency + energy
(unchanged from the main run).

---

## CHECK 1 — RL convergence (fairness check)

**Question:** is the "RL loses" conclusion valid, or did the Q-learner simply
run out of training?

**Procedure:** trained a tabular Q-learner (1 node among N-1 policy-#3 peers,
seeing only its own battery + observed group-failure rate + rounds remaining)
for 3000 episodes with the full training curve logged. Convergence = reward
slope over the last two 10%-windows < 2%.

**Training curve (reward, binned):**
```
ep    0- 200: reward 42473 | completion  6.0%
ep  200- 400: reward 40818 | completion  0.0%
...
ep 2800-3000: reward 38439 | completion  0.0%
```
slope over last two windows: +0.5% -> **CONVERGED** (curve flattens after
~ep 800, well before evaluation).

**Re-evaluation of the converged learner (60 missions, varied battery):**
| node | sec | fail % | compl % |
|---|---|---|---|
| Q-learning learner | 40,349 | 8.22% | **8.3%** |
| heuristic (#3) same slot | 36,086 | 4.42% | **100.0%** |

**Plain verdict: the learner CONVERGED and STILL lost under the stated
objective.** Its apparent +11.8% security comes from **violating the
completion/failure constraint** (dies 92% of the time; exceeds the failure
bound 8.2% vs 4.4%), not from genuine improvement. Re-confirmed.

**Robustness:** a properly-constrained reward (mission-level: security only
if the mission completes AND failures <= bound) makes tabular Q-learning
FAIL to converge (completion stuck ~3%, reward mostly negative) — the sparse,
non-Markovian credit assignment over 200 rounds defeats the tabular learner.
Either way, the learner does not beat the heuristic under the constraint.

---

## CHECK 2 — scaling in N (does the verdict hold as coupling strengthens?)

**Mechanism:** weakest-link coupling intensifies with N: group failure per
round = 1-(1-p)^N. Re-ran the ladder (myopic / group-aware / coordinated /
oracle) at N = 5, 10, 20, 50 with matched draws, 200 missions each, same
real costs.

**Design note (stated explicitly):** with the original fixed 5%-of-rounds
bound, N>=10 becomes infeasible (all-44 group failure alone exceeds the
bound), squeezing ALL policies to level 44 (trivial gap = 0). To test
whether coordination gets genuinely HARDER (not just infeasible), the
group-fail bound was scaled to 1.5x the all-44 baseline at each N (50%
headroom), preserving the upgrade budget structure. At N=5 this reproduces
the original 10-round bound exactly.

**Results (200 missions each):**
| N | fail bound | #3→#4 gap | #3 fail% | #3 compl% | #4 compl% |
|---|---|---|---|---|---|
| 5 | 10 rnd (5%) | **-0.0%** | 6.9% | 80.5% | 81.0% |
| 10 | 18 rnd (9%) | **+3.8%** | 7.0% | 92.5% | 83.5% |
| 20 | 36 rnd (18%) | **+6.1%** | 12.3% | 88.5% | 76.5% |
| 50 | 83 rnd (42%) | **+14.0%** | 28.6% | 88.0% | 64.0% |

**THE ANSWER: the #3→#4 gap OPENS as N grows.** At N=5 the coordinated
heuristic equals the oracle (-0.0%); at N=50 the oracle achieves +14.0% more
group security. The coordination problem genuinely gets harder with scale —
the hand-tuned budget-spending rule (tuned for N=5) no longer captures the
optimal allocation when group-failure probabilities are high and the budget
is large.

**Follow-up required by the brief:** the gap opened at N>=10, so the RL
learner was re-tested at N=20 (gap +6.1%, past the 5% gate). Tabular
Q-learner, 1 node among N-1 coordinated peers, constrained mission-level
reward:
| node | sec | fail % | compl % |
|---|---|---|---|
| Q-learning learner | 182,569 | 18.0% | 72.0% |
| heuristic (#3) same slot | 182,803 | 18.0% | 100.0% |

**The learner does NOT close the opened gap** (-0.1% vs the heuristic; the
oracle's +6.1% remains). It matches the heuristic's security but trades away
completion (72% vs 100%). The opened gap is between the ORACLE's global
full-knowledge mix and ANY online policy (heuristic OR learner) — a single
learning node with realistic local information cannot recover the oracle's
advantage, which comes from knowing all nodes' batteries and the exact
distributions over the whole mission.

---

## Plain statement

- **CHECK 1:** learner converged; it still fails to beat the heuristic under
  the stated objective; its +security is constraint-violation, not genuine
  improvement. Original N=5 verdict stands.
- **CHECK 2:** **the verdict is NOT robust across N** — the #3→#4 gap opens
  at scale (0% at N=5 -> 3.8% at N=10 -> 6.1% at N=20 -> 14.0% at N=50).
  However, the tabular RL learner re-tested at N=20 does NOT close the gap
  (matches the heuristic, worse completion). So: there IS a gap a better
  online policy could exploit at scale, but this RL implementation does not
  exploit it — a future rung with a stronger learner (e.g., policy-gradient
  or model-based with learned battery dynamics) is the honest next step, NOT
  a conclusion that RL works.

## Files

- `verify_swarm_checks.py` — both checks
- `results/verify/check1_training_curve.csv` — RL training curve
- `results/verify/check1_rl_eval.csv` — converged-learner vs heuristic
- `results/verify/check2_scaling_summary.csv` — per-N ladder summary
