"""
Swarm coordinated-deadline PQC security selection: heuristic vs RL gap.

Pure simulation, no hardware, no RL. Uses REAL measured ML-DSA latency
distributions (per-call CSVs from the NXP FRDM-MCXN947 signing benchmark,
150 MHz, -O2) and a REAL-derived energy model (0.382 nJ/cycle, from the
ML-KEM PPK2 measurements on the same board). Per-node costs are MEASURED;
only the coordination (shared group deadline) is MODELED.

Question this rung answers: "does a learning node beat principled heuristics
when swarm nodes share a COORDINATED DEADLINE?"

ENVIRONMENT (N=5 nodes, fixed control rate):
  - A mission = R=200 COORDINATED ROUNDS. In each round ALL nodes produce an
    ML-DSA signature (choosing security level 44/65/87) by a SHARED group
    deadline of 200 ms.
  - COORDINATED-DEADLINE COUPLING (the key mechanism): the round SUCCEEDS
    only if EVERY node meets the deadline. If the slowest node overruns, the
    whole round is a GROUP FAILURE (weakest-link). Measured per-node
    P(miss)@200ms: 44=0.7% 65=5.5% 87=9.3%; 5-node group failure for
    all-same-level: 44=3.2% 65=24.4% 87=38.8%.
  - Per node: latency sampled from the real measured distribution for the
    chosen level; energy = 0.382 nJ/cycle * sampled cycles; each node has its
    own depleting battery (varied start per mission).
  - Objective: maximize total GROUP security (sum of levels across
    nodes/rounds) SUBJECT TO (a) group round-failure rate <= 5% (10 rounds),
    (b) every node completing the mission without dying.

POLICIES (heuristics first, NO RL yet):
  1. MYOPIC       : each node picks strongest level fitting its OWN deadline
                    (P(miss) <= 10%). Ignores the group -> greedy floor,
                    expected to fail often (one greedy node sinks the round).
  2. GROUP-AWARE  : decentralized: each node picks the strongest level such
                    that the GROUP failure prob (1-(1-p)^5) stays <= the
                    round-failure bound. Uses only its own distribution +
                    knowledge that the round needs everyone.
  3. COORDINATED  : shared group state (remaining group-failure budget +
                    all nodes' battery) -> group targets the strongest level
                    the slowest-constrained node can safely sustain; spends
                    the budget early, conserves late. Hand-tuned, no learning.
  4. CENTRALIZED ORACLE: full-knowledge DP over the whole mission (knows the
                    empirical distributions, mission length, all batteries):
                    choose per-round group level to maximize security subject
                    to the failure budget and per-node energy. Ceiling.

Run: 200+ randomized missions, MATCHED latency draws across policies (same
per-(mission,round,node,level) samples so comparisons are fair).

RL STAGE (only if #3->#4 gap is real): one learning node among N-1 fixed
policy-#3 peers; the learner sees only its own state + realistic group signal
(remaining rounds, its battery, observed group failure rate so far) and
chooses its level; compared against a policy-#3 node in the same slot.

Deliverables: policy ladder table (group-security / failure-rate / completion
with CIs), the #3->#4 gap as the headline, the #1-vs-#2/#3 gap, RL result if
the gate opens, and a plain statement.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
from collections import defaultdict

import numpy as np

# --------------------------------------------------------------------------
# REAL MEASURED DATA (NXP)
# --------------------------------------------------------------------------
NXP_CYCLE_CSV = {
    44: "codebase/projects/mldsa_bench_nxp/results/mldsa44_sign_raw.csv",
    65: "codebase/projects/mldsa_bench_nxp/results/mldsa65_sign_raw.csv",
    87: "codebase/projects/mldsa_bench_nxp/results/mldsa87_sign_raw.csv",
}
CPU_HZ = 150e6
NJOULES_PER_CYCLE = 0.3822e-9

N_NODES = 5
R_ROUNDS = 200
DEADLINE_S = 200e-3            # shared group deadline (explicit)
GROUP_FAIL_BOUND = 0.05 * R_ROUNDS   # <= 5% of rounds fail
MYOPIC_OWN_OVERRUN = 0.10      # per-node own-deadline bound for myopic
LEVELS = [44, 65, 87]
SECURITY = {44: 44, 65: 65, 87: 87}


def load_level(level: int) -> np.ndarray:
    with open(NXP_CYCLE_CSV[level]) as f:
        rows = list(csv.DictReader(f))
    return np.array([int(r["cycles"]) for r in rows], dtype=np.float64)


class LevelModel:
    def __init__(self, level: int, cycles: np.ndarray):
        self.level = level
        self.cycles = cycles
        self.lat_s = cycles / CPU_HZ
        self.energy_j = cycles * NJOULES_PER_CYCLE
        self.p_miss = float((self.lat_s > DEADLINE_S).mean())
        self.group_fail_5 = 1.0 - (1.0 - self.p_miss) ** N_NODES
        self.mean_energy = float(self.energy_j.mean())
        self.p90_energy = float(np.quantile(self.energy_j, 0.90))


def build_models() -> dict[int, LevelModel]:
    return {lv: LevelModel(lv, load_level(lv)) for lv in LEVELS}


# --------------------------------------------------------------------------
# MATCHED DRAWS: pre-generate per (mission, round, node, level) latency so
# every policy sees identical randomness per mission.
# --------------------------------------------------------------------------
def gen_draws(rng, n_missions):
    """draws[m][r][n] = {lv: latency_s} for all levels."""
    draws = []
    for _ in range(n_missions):
        mdraws = []
        for _ in range(R_ROUNDS):
            rdraws = []
            for _ in range(N_NODES):
                d = {}
                for lv in LEVELS:
                    # index into the measured empirical distribution
                    idx = rng.randrange(2000)
                    d[lv] = float(models_cache[lv].lat_s[idx])
                rdraws.append(d)
            mdraws.append(rdraws)
        draws.append(mdraws)
    return draws


# --------------------------------------------------------------------------
# POLICIES
# --------------------------------------------------------------------------
def policy_myopic(models) -> int:
    """Strongest level with own P(miss) <= MYOPIC_OWN_OVERRUN (10%)."""
    best = LEVELS[0]
    for lv in LEVELS:
        if models[lv].p_miss <= MYOPIC_OWN_OVERRUN:
            best = lv
    return best


def policy_group_aware(models, fail_left, rounds_left) -> int:
    """Decentralized group-aware: strongest level whose MARGINAL group
    failure (above the all-44 baseline) fits the remaining budget when
    spread over the rounds it would be used. This lets the node spend the
    failure budget on higher levels instead of always settling for 44:
      allowed if (gf_5(lv) - gf_5(44)) * rounds_used <= fail_left_above_base
    where rounds_used is how many rounds it commits to that level. A simple,
    defensible spending rule."""
    base_gf = models[LEVELS[0]].group_fail_5
    # budget above the all-44 baseline
    budget = fail_left - base_gf * rounds_left
    best = LEVELS[0]
    for lv in LEVELS:
        marginal = models[lv].group_fail_5 - base_gf
        # commit to lv for as many rounds as the budget allows; if it can be
        # used for at least ~10 rounds, it's worth it
        usable_rounds = budget / marginal if marginal > 0 else rounds_left
        if usable_rounds >= 10:
            best = lv
    return best


def policy_coordinated(models, fail_left, rounds_left,
                       energies, energy_starts, round_idx) -> int:
    """Shared group state, genuinely smart: the GROUP coordinates on a
    budgeted level mix. It spends the group-failure budget on the highest
    level that is (a) affordable by every node's battery for the remaining
    rounds, and (b) within the remaining failure budget when committed for
    a meaningful number of rounds. Tracks the running budget, so it uses
    65/87 early and drops to 44 as the budget depletes. Hand-tuned."""
    base_gf = models[LEVELS[0]].group_fail_5
    budget_above = fail_left - base_gf * rounds_left
    progress = round_idx / R_ROUNDS
    best = LEVELS[0]
    for lv in LEVELS:
        marginal = models[lv].group_fail_5 - base_gf
        if marginal <= 0:
            continue
        usable_rounds = budget_above / marginal
        # spend more aggressively early, taper as progress increases;
        # a level is worth committing to if the budget allows >= 8 rounds
        # (the oracle-style observation: mixing 87 into a 44 baseline is
        # optimal when it can be used for a meaningful block)
        min_commit = 8.0 * (1.0 - 0.5 * progress)
        if usable_rounds < min_commit:
            continue
        # battery: every node must afford lv for the usable rounds
        ok = True
        for e in energies:
            if e < models[lv].p90_energy * min(usable_rounds, rounds_left):
                ok = False
                break
        if ok:
            best = lv
    return best


# --------------------------------------------------------------------------
# CENTRALIZED ORACLE (full-knowledge DP)
# --------------------------------------------------------------------------
def oracle_policy(models, energy_starts, fail_bound, n_rounds, n_nodes):
    """Full-knowledge optimum via knapsack.

    Rounds are i.i.d. and exchangeable, so the optimal policy is a fixed
    group level mix (n44, n65, n87) with n44+n65+n87 = n_rounds. The oracle
    maximizes total GROUP security subject to:
      (a) expected group failures = sum(gf_5(lv) * n_lv) <= fail_bound
      (b) per-node expected energy = sum(em(lv) * n_lv) <= battery
    (all nodes identical per mission, so one shared energy constraint;
    the binding node is the one with the smallest start battery).
    Exhaustive search over (n65, n87): fast and exact."""
    N = n_rounds
    M = fail_bound
    B = min(energy_starts)  # binding node (lowest battery)
    pm_gf = {lv: models[lv].group_fail_5 for lv in LEVELS}
    em = {lv: models[lv].mean_energy for lv in LEVELS}
    best = None
    for n65 in range(N + 1):
        rem_miss = M - pm_gf[65] * n65
        if rem_miss < 0:
            break
        max87 = int(rem_miss / pm_gf[87]) if pm_gf[87] > 0 else N - n65
        for n87 in range(min(max87, N - n65) + 1):
            n44 = N - n65 - n87
            if n44 < 0:
                continue
            miss = pm_gf[44] * n44 + pm_gf[65] * n65 + pm_gf[87] * n87
            if miss > M:
                continue
            energy = em[44] * n44 + em[65] * n65 + em[87] * n87
            if energy > B:
                continue
            sec = (44 * n44 + 65 * n65 + 87 * n87) * n_nodes
            if best is None or sec > best[0]:
                best = (sec, n44, n65, n87)
    if best is None:
        return [LEVELS[0]] * N
    _, n44, n65, n87 = best
    mix = [87] * n87 + [65] * n65 + [44] * n44
    return mix[:N]


# --------------------------------------------------------------------------
# MISSION SIMULATION (matched draws)
# --------------------------------------------------------------------------
def run_mission(policy_name, models, energy_starts, draws, oracle=None):
    """Simulate one mission. Returns (group_security, group_failures,
    completed). draws = matched per-(round,node,level) latency samples."""
    energies = list(energy_starts)
    total_sec = 0
    group_fails = 0
    completed = True
    fail_left = GROUP_FAIL_BOUND
    for r in range(R_ROUNDS):
        lv_group = None
        if policy_name == "myopic":
            lv_group = policy_myopic(models)
        elif policy_name == "group_aware":
            lv_group = policy_group_aware(models, fail_left, R_ROUNDS - r)
        elif policy_name == "coordinated":
            lv_group = policy_coordinated(models, fail_left, R_ROUNDS - r,
                                          energies, energy_starts, r)
        elif policy_name == "oracle":
            lv_group = oracle[r]
        # each node uses the group level (coordinated round)
        round_sec = 0
        round_fail = False
        for n in range(N_NODES):
            lat = draws[r][n][lv_group]
            energies[n] -= lat * CPU_HZ * NJOULES_PER_CYCLE
            round_sec += SECURITY[lv_group]
            if lat > DEADLINE_S:
                round_fail = True
        total_sec += round_sec
        if round_fail:
            group_fails += 1
            fail_left = max(0, fail_left - 1)
        # any node dead? -> mission incomplete, remaining rounds all fail
        for n in range(N_NODES):
            if energies[n] <= 0:
                # count remaining rounds as failures
                group_fails += (R_ROUNDS - r - 1)
                completed = False
                return total_sec, group_fails, completed
    return total_sec, group_fails, completed


# --------------------------------------------------------------------------
# RL STAGE (only if the #3->#4 gap is real)
# --------------------------------------------------------------------------
def rl_stage(models, energy_starts, draws, n_episodes=400, rng=None):
    """One learning node (Q-learning) among N-1 policy-#3 peers. The learner
    sees only: its own battery, rounds remaining, observed group-failure rate
    so far, and the level the group would pick (it can coordinate on the
    same signal). No oracle/global information."""
    rng = rng or random.Random(0)
    # discrete state: (own_battery_bin, rounds_left_bin, fail_rate_bin)
    B_BINS, F_BINS = 20, 5
    Q = np.zeros((B_BINS, F_BINS, 3))  # per state, per level (no rounds dim;
    # rounds handled via epsilon-decay only)
    alpha, gamma, eps = 0.2, 0.95, 0.3
    # peer policy = coordinated level choice for the OTHER nodes
    def peer_level(fail_left, rounds_left, energies, starts, r):
        return policy_coordinated(models, fail_left, rounds_left,
                                  energies, starts, r)
    rewards = []
    for ep in range(n_episodes):
        energies = list(energy_starts)
        fail_left = GROUP_FAIL_BOUND
        eps = max(0.05, 0.3 * (1 - ep / n_episodes))
        total_sec = 0
        for r in range(R_ROUNDS):
            # peers pick the coordinated level; learner decides its own
            lv_peer = peer_level(fail_left, R_ROUNDS - r, energies,
                                 energy_starts, r)
            # learner state
            eb = int(min(B_BINS - 1, energies[0] / max(energy_starts[0], 1e-9) * B_BINS))
            fb = int(min(F_BINS - 1, (1 - fail_left / GROUP_FAIL_BOUND) * F_BINS))
            if rng.random() < eps:
                lv_learner = rng.choice(LEVELS)
            else:
                lv_learner = LEVELS[int(np.argmax(Q[eb, fb]))]
            # simulate: learner is node 0, peers nodes 1..N-1
            round_sec = 0
            round_fail = False
            lats = [draws[r][0][lv_learner]] + [draws[r][n][lv_peer]
                                                for n in range(1, N_NODES)]
            lvls = [lv_learner] + [lv_peer] * (N_NODES - 1)
            for n in range(N_NODES):
                energies[n] -= lats[n] * CPU_HZ * NJOULES_PER_CYCLE
                round_sec += SECURITY[lvls[n]]
                if lats[n] > DEADLINE_S:
                    round_fail = True
            total_sec += round_sec
            if round_fail:
                fail_left = max(0, fail_left - 1)
            # reward: group security, penalize failures mildly
            reward = round_sec - 200.0 * (1 if round_fail else 0)
            # Q update toward next state (approx: no explicit next-state V,
            # use immediate + gamma * max_a Q(next))
            n_eb = int(min(B_BINS - 1, max(energies[0], 0) / max(energy_starts[0], 1e-9) * B_BINS))
            n_fb = int(min(F_BINS - 1, (1 - fail_left / GROUP_FAIL_BOUND) * F_BINS))
            best_next = float(np.max(Q[n_eb, n_fb]))
            Q[eb, fb, LEVELS.index(lv_learner)] += alpha * (
                reward + gamma * best_next - Q[eb, fb, LEVELS.index(lv_learner)])
            if any(e <= 0 for e in energies):
                break
        rewards.append(total_sec)
    return rewards, Q


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", type=int, default=250)
    ap.add_argument("--seed", type=int, default=20260806)
    ap.add_argument("--out", default="codebase/swarm_coordination_sim/results")
    ap.add_argument("--do-rl", action="store_true",
                    help="force the RL stage even if the gap is small")
    args = ap.parse_args()

    global models_cache
    models_cache = build_models()
    models = models_cache
    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)

    # battery: per-node start = scale * (R * E[65] per node); varied per mission
    base_energy = R_ROUNDS * models[65].mean_energy
    print(f"group deadline = {DEADLINE_S*1e3:.0f}ms | N={N_NODES} | R={R_ROUNDS}")
    print(f"group-fail bound = {GROUP_FAIL_BOUND:.0f} rounds (5%)")
    print(f"per-node P(miss)@200ms: 44={models[44].p_miss*100:.1f}% "
          f"65={models[65].p_miss*100:.1f}% 87={models[87].p_miss*100:.1f}%")
    print(f"5-node group fail: 44={models[44].group_fail_5*100:.1f}% "
          f"65={models[65].group_fail_5*100:.1f}% 87={models[87].group_fail_5*100:.1f}%")

    draws = gen_draws(rng, args.missions)

    results = defaultdict(list)
    rows = []
    for mi in range(args.missions):
        scale = rng.uniform(0.60, 1.10)
        e_starts = [base_energy * scale] * N_NODES  # identical per mission
        oracle = oracle_policy(models, e_starts, GROUP_FAIL_BOUND,
                               R_ROUNDS, N_NODES)
        for name in ["myopic", "group_aware", "coordinated", "oracle"]:
            sec, fails, done = run_mission(name, models, e_starts,
                                           draws[mi], oracle)
            results[name].append((sec, fails, done))
        rows.append({
            "mission": mi, "battery_scale": round(scale, 4),
            **{f"sec_{n}": results[n][-1][0] for n in ["myopic", "group_aware", "coordinated", "oracle"]},
            **{f"fail_{n}": results[n][-1][1] for n in ["myopic", "group_aware", "coordinated", "oracle"]},
            **{f"done_{n}": int(results[n][-1][2]) for n in ["myopic", "group_aware", "coordinated", "oracle"]},
        })

    with open(os.path.join(args.out, "mission_results_raw.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def summ(vals):
        a = np.array(vals, dtype=float)
        m = a.mean()
        se = a.std(ddof=1) / math.sqrt(len(a)) if len(a) > 1 else 0.0
        return m, 1.96 * se

    print(f"\n=== {args.missions} missions, N={N_NODES}, R={R_ROUNDS}, "
          f"deadline=200ms, fail_bound=5% ===")
    print(f"battery base = {base_energy*1e3:.0f} mJ/node (R*E[65]); scale U[0.60,1.10]")
    print(f"{'policy':12s} | {'grp sec':>8s} {'CI':>7s} | {'fail%':>6s} {'CI':>6s} | {'compl%':>7s}")
    for name in ["myopic", "group_aware", "coordinated", "oracle"]:
        secs = [r[0] for r in results[name]]
        fls = [r[1] for r in results[name]]
        dons = [r[2] for r in results[name]]
        sm, sci = summ(secs)
        fm, fci = summ(fls)
        cm = 100 * sum(dons) / len(dons)
        print(f"{name:12s} | {sm:8.0f} +/-{sci:5.0f} | {fm/2:6.2f} +/-{fci/2:4.2f} | {cm:6.1f}%")

    def avg(n, idx):
        return np.mean([r[idx] for r in results[n]])
    sm, sga, sc, so = (avg(n, 0) for n in ["myopic", "group_aware", "coordinated", "oracle"])
    print()
    print(f"GAP myopic->group-aware   (weakest-link coupling matters?): {sga-sm:+.1f} ({100*(sga-sm)/sm:+.1f}%)")
    print(f"GAP group-aware->coord    (coordination helps?):           {sc-sga:+.1f} ({100*(sc-sga)/sga:+.1f}%)")
    gap = so - sc
    print(f"GAP coordinated->oracle (RL headroom, DECISIVE):          {gap:+.1f} ({100*gap/sc:+.1f}%)")

    # RL gate: gap > 5% -> real headroom
    gap_pct = 100 * gap / sc if sc else 0
    print(f"\nRL gate (gap > 5%): {gap_pct:.1f}% -> {'OPEN, run RL stage' if gap_pct > 5 or args.do_rl else 'CLOSED, heuristics suffice'}")


if __name__ == "__main__":
    main()
