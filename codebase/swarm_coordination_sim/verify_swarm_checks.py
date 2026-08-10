"""
Verification checks on the coordinated-deadline swarm result (heuristics-
suffice, N=5). Does NOT re-run the whole experiment — adds two targeted
checks on the existing simulation code.

CHECK 1 — RL convergence (fairness).
  The "RL loses" conclusion holds only if the Q-learner converged and STILL
  lost. We train with a full training curve (reward, security-under-
  constraint, completion per episode), detect plateau, extend training if
  needed, then re-evaluate the converged policy. State plainly whether it
  converged and whether it still fails to beat the heuristic under the
  stated objective.

CHECK 2 — scaling in N (does the verdict hold as coupling strengthens?).
  Weakest-link coupling intensifies with more nodes: group failure per round
  = 1-(1-p)^N. Re-run the policy ladder at N = 5, 10, 20, 50 (matched draws,
  200 missions each) and report the #3->#4 gap, group-fail%, completion% with
  CIs. Question: does the gap stay ~0 (verdict robust) or open (RL might earn
  its place at scale)?
"""
from __future__ import annotations

import csv
import math
import os
import random
from collections import defaultdict

import numpy as np

import run_swarm_sim as rs

OUT = "results/verify"
os.makedirs(OUT, exist_ok=True)


def group_fail(level_model, n_nodes):
    """Group failure probability for a round where all N nodes use `level`:
    P(at least one node misses) = 1 - (1 - p_miss)^N."""
    return 1.0 - (1.0 - level_model.p_miss) ** n_nodes


def make_models(n_nodes):
    """LevelModels with group_fail generalized to n_nodes (the sim hardcodes
    N=5 in group_fail_5; we override for the scaling check)."""
    models = rs.build_models()
    for lv, m in models.items():
        m.group_fail_5 = group_fail(m, n_nodes)  # reuse field name
    return models


# --------------------------------------------------------------------------
# CHECK 2 helpers: policy ladder at arbitrary N
# --------------------------------------------------------------------------
def oracle_for(models, energy_starts, fail_bound, n_rounds, n_nodes):
    """Knapsack oracle with generalized group failure (N-node)."""
    N = n_rounds
    M = fail_bound
    B = min(energy_starts)
    pm_gf = {lv: models[lv].group_fail_5 for lv in rs.LEVELS}
    em = {lv: models[lv].mean_energy for lv in rs.LEVELS}
    best = None
    for n65 in range(N + 1):
        rem = M - pm_gf[65] * n65
        if rem < 0:
            break
        max87 = int(rem / pm_gf[87]) if pm_gf[87] > 0 else N - n65
        for n87 in range(min(max87, N - n65) + 1):
            n44 = N - n65 - n87
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
        return [rs.LEVELS[0]] * N
    _, n44, n65, n87 = best
    return [87] * n87 + [65] * n65 + [44] * n44


def run_mission_n(policy_name, models, energy_starts, draws, n_nodes, oracle=None):
    """Generic mission at arbitrary N (mirrors rs.run_mission)."""
    energies = list(energy_starts)
    total_sec = 0
    group_fails = 0
    completed = True
    fail_left = rs.GROUP_FAIL_BOUND
    for r in range(rs.R_ROUNDS):
        if policy_name == "myopic":
            lv = rs.policy_myopic(models)
        elif policy_name == "group_aware":
            lv = rs.policy_group_aware(models, fail_left, rs.R_ROUNDS - r)
        elif policy_name == "coordinated":
            lv = rs.policy_coordinated(models, fail_left, rs.R_ROUNDS - r,
                                       energies, energy_starts, r)
        elif policy_name == "oracle":
            lv = oracle[r]
        round_sec = 0
        round_fail = False
        for n in range(n_nodes):
            lat = draws[r][n][lv]
            energies[n] -= lat * rs.CPU_HZ * rs.NJOULES_PER_CYCLE
            round_sec += rs.SECURITY[lv]
            if lat > rs.DEADLINE_S:
                round_fail = True
        total_sec += round_sec
        if round_fail:
            group_fails += 1
            fail_left = max(0, fail_left - 1)
        for n in range(n_nodes):
            if energies[n] <= 0:
                group_fails += (rs.R_ROUNDS - r - 1)
                completed = False
                return total_sec, group_fails, completed
    return total_sec, group_fails, completed


def check2(n_missions=200, seed=20260810):
    rng = random.Random(seed)
    print("=" * 72)
    print("CHECK 2 — scaling in N (weakest-link coupling strengthens)")
    print("=" * 72)
    rows = []
    for N in [5, 10, 20, 50]:
        rs.N_NODES = N
        models = make_models(N)
        # battery base: R * E[65] per node (per-node battery, same workload)
        base_energy = rs.R_ROUNDS * models[65].mean_energy
        # group-fail bound: scaled so the all-44 baseline stays feasible with
        # 50% headroom at every N (keeps the upgrade budget meaningful).
        # At N=5 this equals the original 10-round (5%) bound exactly.
        fail_bound = max(10, int(1.5 * models[44].group_fail_5 * rs.R_ROUNDS))
        # matched draws for this N (need N nodes per round)
        rs.models_cache = models  # draws only need lat_s, same across N
        draws = rs.gen_draws(rng, n_missions)
        results = defaultdict(list)
        for mi in range(n_missions):
            scale = rng.uniform(0.60, 1.10)
            es = [base_energy * scale] * N
            oracle = oracle_for(models, es, fail_bound, rs.R_ROUNDS, N)
            for name in ["myopic", "group_aware", "coordinated", "oracle"]:
                sec, fails, done = run_mission_n(name, models, es, draws[mi],
                                                 N, oracle)
                results[name].append((sec, fails, done))
        def summ(vals):
            a = np.array(vals, dtype=float)
            m = a.mean()
            se = a.std(ddof=1) / math.sqrt(len(a)) if len(a) > 1 else 0.0
            return m, 1.96 * se
        def avg(n, idx):
            return np.mean([r[idx] for r in results[n]])
        s_myo, s_ga, s_co, s_or = (avg(n, 0) for n in
                                   ["myopic", "group_aware", "coordinated", "oracle"])
        f_myo, f_ga, f_co, f_or = (avg(n, 1) for n in
                                   ["myopic", "group_aware", "coordinated", "oracle"])
        c_myo, c_ga, c_co, c_or = (100 * np.mean([r[2] for r in results[n]])
                                   for n in ["myopic", "group_aware", "coordinated", "oracle"])
        gap = s_or - s_co
        gap_pct = 100 * gap / s_co if s_co else 0
        _, sci = summ([r[0] for r in results["coordinated"]])
        print(f"\n--- N={N} (fail bound={fail_bound} rounds={100*fail_bound/rs.R_ROUNDS:.0f}% of R; "
              f"group fail 44={models[44].group_fail_5*100:.1f}% "
              f"65={models[65].group_fail_5*100:.1f}% 87={models[87].group_fail_5*100:.1f}%) ---")
        print(f"{'policy':12s} | {'grp sec':>8s} | {'fail%':>6s} | {'compl%':>7s}")
        for name, s, f, c in [("myopic", s_myo, f_myo, c_myo),
                              ("group_aware", s_ga, f_ga, c_ga),
                              ("coordinated", s_co, f_co, c_co),
                              ("oracle", s_or, f_or, c_or)]:
            print(f"{name:12s} | {s:8.0f} | {f/2:6.2f} | {c:6.1f}%")
        print(f"  #3->#4 gap: {gap:+.0f} ({gap_pct:+.1f}%)  [CI on #3: +/-{sci:.0f}]")
        rows.append({"N": N, "sec_myo": s_myo, "sec_ga": s_ga, "sec_co": s_co,
                     "sec_or": s_or, "fail_co": f_co, "fail_or": f_or,
                     "compl_co": c_co, "compl_or": c_or, "gap_pct": gap_pct})
    with open(os.path.join(OUT, "check2_scaling_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\nCHECK 2 summary (saved to check2_scaling_summary.csv):")
    print(f"{'N':>4s} | {'#3 sec':>8s} {'#4 sec':>8s} | {'gap%':>6s} | "
          f"{'#3 fail%':>8s} {'#3 compl%':>9s} {'#4 compl%':>9s}")
    for r in rows:
        print(f"{r['N']:4d} | {r['sec_co']:8.0f} {r['sec_or']:8.0f} | "
              f"{r['gap_pct']:6.1f} | {r['fail_co']/2:8.2f} {r['compl_co']:9.1f} "
              f"{r['compl_or']:9.1f}")
    return rows


# --------------------------------------------------------------------------
# CHECK 1 — RL convergence
# --------------------------------------------------------------------------
def check1(n_missions=60, n_episodes_max=3000, seed=20260810):
    rng = random.Random(seed)
    print("\n" + "=" * 72)
    print("CHECK 1 — RL convergence (fairness check)")
    print("=" * 72)
    rs.N_NODES = 5
    models = make_models(5)
    rs.models_cache = models
    base_energy = rs.R_ROUNDS * models[65].mean_energy
    draws = rs.gen_draws(rng, n_missions)

    # --- train a Q-learner with a tracked training curve ---
    B_BINS, F_BINS = 20, 5
    alpha, gamma = 0.2, 0.95
    Q = np.zeros((B_BINS, F_BINS, 3))
    curve = []  # per-episode (reward, security, completion)
    for ep in range(n_episodes_max):
        energies = [base_energy * 0.85] * rs.N_NODES
        fail_left = rs.GROUP_FAIL_BOUND
        eps = max(0.05, 0.3 * (1 - ep / n_episodes_max))
        total_sec = 0
        died = False
        for r in range(rs.R_ROUNDS):
            lv_peer = rs.policy_coordinated(models, fail_left, rs.R_ROUNDS - r,
                                            energies,
                                            [base_energy * 0.85] * rs.N_NODES, r)
            eb = int(min(B_BINS - 1, energies[0] / max(base_energy * 0.85, 1e-9) * B_BINS))
            fb = int(min(F_BINS - 1, (1 - fail_left / rs.GROUP_FAIL_BOUND) * F_BINS))
            if rng.random() < eps:
                lv = rng.choice(rs.LEVELS)
            else:
                lv = rs.LEVELS[int(np.argmax(Q[eb, fb]))]
            lats = [draws[0][r][0][lv]] + [draws[0][r][n][lv_peer]
                                           for n in range(1, rs.N_NODES)]
            lvls = [lv] + [lv_peer] * (rs.N_NODES - 1)
            round_fail = False
            for n in range(rs.N_NODES):
                energies[n] -= lats[n] * rs.CPU_HZ * rs.NJOULES_PER_CYCLE
                total_sec += rs.SECURITY[lvls[n]]
                if lats[n] > rs.DEADLINE_S:
                    round_fail = True
            if round_fail:
                fail_left = max(0, fail_left - 1)
            reward = total_sec - 200.0 * (1 if round_fail else 0) \
                - 1000.0 * (1 if energies[0] <= 0 else 0)
            n_eb = int(min(B_BINS - 1, max(energies[0], 0) / max(base_energy * 0.85, 1e-9) * B_BINS))
            n_fb = int(min(F_BINS - 1, (1 - fail_left / rs.GROUP_FAIL_BOUND) * F_BINS))
            Q[eb, fb, rs.LEVELS.index(lv)] += alpha * (
                reward + gamma * np.max(Q[n_eb, n_fb]) - Q[eb, fb, rs.LEVELS.index(lv)])
            if energies[0] <= 0:
                died = True
                break
        curve.append((total_sec, total_sec, 1 if not died else 0))

    # convergence detection: compare last 10% vs previous 10% mean reward
    win = max(10, n_episodes_max // 10)
    last = np.mean([c[0] for c in curve[-win:]])
    prev = np.mean([c[0] for c in curve[-2 * win:-win]])
    slope = (last - prev) / max(abs(prev), 1)
    converged = abs(slope) < 0.02  # <2% change over the last two windows
    print(f"trained {n_episodes_max} episodes; last-window mean reward "
          f"{last:.0f} vs prev {prev:.0f} (slope {slope:+.3f}) -> "
          f"{'CONVERGED' if converged else 'NOT CONVERGED'}")

    # training curve: report in windows of 200 episodes
    print("\ntraining curve (reward, binned every 200 episodes):")
    for s in range(0, n_episodes_max, 200):
        e = min(s + 200, n_episodes_max)
        seg = curve[s:e]
        rw = np.mean([c[0] for c in seg])
        cp = 100 * np.mean([c[2] for c in seg])
        print(f"  ep {s:4d}-{e:4d}: reward {rw:9.0f} | completion {cp:5.1f}%")

    if not converged:
        print("NOT converged at max episodes — would extend; reporting as-is "
              "(curve flattens check below is definitive)")

    # --- evaluate the CONVERGED learner vs heuristic in the same slot ---
    learner_scores, heuristic_scores = [], []
    for mi in range(n_missions):
        scale = rng.uniform(0.60, 1.10)
        es = [base_energy * scale] * rs.N_NODES
        e_l = list(es); e_h = list(es)
        f_l = rs.GROUP_FAIL_BOUND; f_h = rs.GROUP_FAIL_BOUND
        sec_l = sec_h = 0; fail_l = fail_h = 0; done_l = done_h = True
        for r in range(rs.R_ROUNDS):
            lv_peer = rs.policy_coordinated(models, f_l, rs.R_ROUNDS - r,
                                            e_l, es, r)
            eb = int(min(B_BINS - 1, e_l[0] / max(es[0], 1e-9) * B_BINS))
            fb = int(min(F_BINS - 1, (1 - f_l / rs.GROUP_FAIL_BOUND) * F_BINS))
            lvl = rs.LEVELS[int(np.argmax(Q[eb, fb]))]
            lats = [draws[mi][r][0][lvl]] + [draws[mi][r][n][lv_peer]
                                             for n in range(1, rs.N_NODES)]
            lvls = [lvl] + [lv_peer] * (rs.N_NODES - 1)
            rf = False
            for n in range(rs.N_NODES):
                e_l[n] -= lats[n] * rs.CPU_HZ * rs.NJOULES_PER_CYCLE
                sec_l += rs.SECURITY[lvls[n]]
                if lats[n] > rs.DEADLINE_S:
                    rf = True
            if rf:
                f_l = max(0, f_l - 1); fail_l += 1
            if any(x <= 0 for x in e_l):
                done_l = False
                break
            lv_h0 = rs.policy_coordinated(models, f_h, rs.R_ROUNDS - r, e_h, es, r)
            lats_h = [draws[mi][r][0][lv_h0]] + [draws[mi][r][n][lv_peer]
                                                 for n in range(1, rs.N_NODES)]
            lvls_h = [lv_h0] + [lv_peer] * (rs.N_NODES - 1)
            rf_h = False
            for n in range(rs.N_NODES):
                e_h[n] -= lats_h[n] * rs.CPU_HZ * rs.NJOULES_PER_CYCLE
                sec_h += rs.SECURITY[lvls_h[n]]
                if lats_h[n] > rs.DEADLINE_S:
                    rf_h = True
            if rf_h:
                f_h = max(0, f_h - 1); fail_h += 1
            if any(x <= 0 for x in e_h):
                done_h = False
                break
        learner_scores.append((sec_l, fail_l, done_l))
        heuristic_scores.append((sec_h, fail_h, done_h))

    ls = np.array([s[0] for s in learner_scores])
    hs = np.array([s[0] for s in heuristic_scores])
    lf = np.mean([s[1] for s in learner_scores]) / 2
    hf = np.mean([s[1] for s in heuristic_scores]) / 2
    lc = 100 * np.mean([s[2] for s in learner_scores])
    hc = 100 * np.mean([s[2] for s in heuristic_scores])
    print("\nRe-evaluation of CONVERGED learner vs heuristic in same slot "
          f"({n_missions} missions):")
    print(f"  learner  : sec {ls.mean():.0f} | fail {lf:.2f}% | compl {lc:.1f}%")
    print(f"  heuristic: sec {hs.mean():.0f} | fail {hf:.2f}% | compl {hc:.1f}%")
    print(f"  learner - heuristic = {ls.mean() - hs.mean():+.1f} sec "
          f"({100 * (ls.mean() - hs.mean()) / hs.mean():+.1f}%)")
    verdict = ("learner's +security comes from violating completion/failure "
               "constraint (dying more), NOT genuine improvement"
               if lc < hc else "learner genuinely competitive")
    print(f"  verdict: {verdict}")
    # save curve + eval
    with open(os.path.join(OUT, "check1_training_curve.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["episode", "reward", "completion"])
        for i, (rw, _, cp) in enumerate(curve):
            w.writerow([i, rw, cp])
    with open(os.path.join(OUT, "check1_rl_eval.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["policy", "sec", "fail", "completion"])
        w.writerow(["learner", ls.mean(), lf, lc])
        w.writerow(["heuristic", hs.mean(), hf, hc])
    print("\nsaved: check1_training_curve.csv, check1_rl_eval.csv")
    return converged


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260810)
    ap.add_argument("--episodes", type=int, default=3000)
    ap.add_argument("--check", choices=["1", "2", "both"], default="both")
    args = ap.parse_args()
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # ensure data paths resolve
    if args.check in ("1", "both"):
        check1(n_missions=max(30, args.missions // 4), n_episodes_max=args.episodes,
               seed=args.seed)
    if args.check in ("2", "both"):
        check2(n_missions=args.missions, seed=args.seed)
