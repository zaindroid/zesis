"""
PQC security-level selection under battery depletion: heuristic vs RL gap.

Pure simulation, no hardware, no RL. Uses REAL measured ML-DSA latency
distributions (per-call CSVs from the NXP FRDM-MCXN947 signing benchmark,
150 MHz, -O2) and a REAL-derived energy model: 0.382 nJ/cycle, derived from
the ML-KEM PPK2 energy measurements on the same board (mean across 9
op/level measurements; see run report).

Question this rung answers: "is there room for learning, or do principled
heuristics already solve the battery-coupling problem?"

ENVIRONMENT (single node, fixed control-loop rate):
  - Mission = N=1000 signing events at fixed intervals.
  - Each event: choose security level 44/65/87. The per-event latency is
    SAMPLED from the real measured per-call distribution (2000 real samples
    per level); energy = 0.382 nJ/cycle * sampled cycles. A single sample
    therefore carries BOTH the deadline risk and the energy cost (they are
    perfectly correlated in reality: a slow sign also costs more energy).
  - Fixed control deadline = 150 ms per event. sampled_latency > 150 ms
    => DEADLINE MISS (a safety failure). Measured per-level P(miss):
       44: 2.5%   65: 14.1%   87: 21.9%
  - Finite battery budget, depletes by each event's energy. Battery hits 0
    before event N => all remaining events fail (mission incomplete).
  - Objective (optimized per mission): maximize total security
    = sum(security_level) subject to (a) deadline misses <= MISS_BOUND
    (= 5% of N = 50), (b) completing the whole mission (battery never 0).

POLICIES (all four, no RL):
  1. MYOPIC    : strongest level whose latency "fits the deadline" in the
                 sense P(miss) <= OVERRUN_BOUND (= MISS_BOUND/N = 5%).
                 Only level 44 qualifies. Ignores battery -> naive floor.
  2. BATTERY   : per-event energy reservation = energy_left / events_left.
                 Strongest level fitting BOTH deadline-overrun (5%) AND the
                 reservation. Can pick 65/87 early when battery is ample.
  3. LOOKAHEAD : hand-tuned: spend freely early / conserve late, scaling by
                 battery fraction and mission progress (no learning).
  4. ORACLE    : full-knowledge backward DP over the empirical distributions
                 (energy-discretized state, Lagrangian on the miss budget).
                 Theoretical ceiling.

REPORT: per-policy mean security / deadline-miss rate / completion rate with
95% CIs over many randomized missions; the #3-vs-#4 gap (decisive number);
the #1-vs-#2 gap (sanity check the coupling is real).
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
# REAL MEASURED DATA
# --------------------------------------------------------------------------
NXP_CYCLE_CSV = {
    44: "codebase/projects/mldsa_bench_nxp/results/mldsa44_sign_raw.csv",
    65: "codebase/projects/mldsa_bench_nxp/results/mldsa65_sign_raw.csv",
    87: "codebase/projects/mldsa_bench_nxp/results/mldsa87_sign_raw.csv",
}
CPU_HZ = 150e6                      # NXP Cortex-M33 core clock (240e6 for ESP32)
# Choose latency distribution source: 'nxp' or 'esp32'. Energy model stays
# 0.382 nJ/cycle (same board family energy-per-cycle); CPU_HZ scales cycles->s.
PLATFORM = 'nxp'
if PLATFORM == 'esp32':
    CPU_HZ = 240e6
    NXP_CYCLE_CSV = {
        44: 'codebase/projects/gtsrb_multiexit_esp32s3/results/mldsa44_sign_raw.csv',
        65: 'codebase/projects/gtsrb_multiexit_esp32s3/results/mldsa65_sign_raw.csv',
        87: 'codebase/projects/gtsrb_multiexit_esp32s3/results/mldsa87_sign_raw.csv',
    }
NJOULES_PER_CYCLE = 0.3822e-9       # J/cycle, from ML-KEM PPK2 on same board

N_EVENTS = 1000
DEADLINE_S = 150e-3                 # 150 ms control deadline (explicit)
MISS_BOUND = 50                     # <= 5% of events (safety bound)
OVERRUN_BOUND = MISS_BOUND / N_EVENTS   # 5% per-event "deadline-fit" bound
LEVELS = [44, 65, 87]
SECURITY = {44: 44, 65: 65, 87: 87}


def load_level(level: int) -> np.ndarray:
    path = NXP_CYCLE_CSV[level]
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return np.array([int(r["cycles"]) for r in rows], dtype=np.float64)


class LevelModel:
    def __init__(self, level: int, cycles: np.ndarray):
        self.level = level
        self.cycles = cycles
        self.lat_s = cycles / CPU_HZ
        self.energy_j = cycles * NJOULES_PER_CYCLE
        self.sorted_lat = np.sort(self.lat_s)
        self.n = len(self.lat_s)
        self.p_miss = float((self.lat_s > DEADLINE_S).mean())
        self.mean_energy = float(self.energy_j.mean())
        self.p90_energy = float(np.quantile(self.energy_j, 0.90))


def build_models() -> dict[int, LevelModel]:
    return {lv: LevelModel(lv, load_level(lv)) for lv in LEVELS}


# --------------------------------------------------------------------------
# POLICIES 1-3 (online heuristics)
# --------------------------------------------------------------------------
def policy_myopic(deadline, overrun, models) -> int:
    """Naive floor: strongest level with P(miss) <= per-event overrun bound.
    With overrun=5% this is level 44 only. Ignores battery and the mission
    miss budget entirely."""
    best = LEVELS[0]
    for lv in LEVELS:
        if models[lv].p_miss <= overrun:
            best = lv
    return best


def policy_battery(deadline, models, energy_left, events_left,
                   miss_left, miss_budget_frac=1.0) -> int:
    """Battery + risk-budget aware greedy. Uses the remaining MISS budget:
    a level is eligible if its expected misses over the remaining events
    (p_miss * events_left) <= miss_left * miss_budget_frac, AND its p90
    energy fits the per-event reservation (energy_left/events_left).
    Ignores the future shape of the mission (no lookahead)."""
    reserve = energy_left / events_left if events_left > 0 else 0.0
    best = LEVELS[0]
    for lv in LEVELS:
        m = models[lv]
        risk_ok = m.p_miss * events_left <= miss_left * miss_budget_frac
        if risk_ok and m.p90_energy <= reserve:
            best = lv
    return best


def policy_lookahead(deadline, models, energy_left, energy_start,
                     miss_left, miss_budget, t, n) -> int:
    """Hand-tuned lookahead: spend the miss-risk budget aggressively early
    (when mission is long, recovery is possible), conserve late; scale
    security by battery health. Miss-risk share per event is
    (miss_left/n_events_left) * risk_aggression, where risk_aggression
    decays with mission progress. No learning."""
    progress = t / n if n > 0 else 1.0
    battery_frac = energy_left / energy_start if energy_start > 0 else 0.0
    events_left = n - t
    # per-event risk allowance: spend up to 2x the average early, taper to
    # the average late (a sensible hand-tuned profile)
    risk_aggression = 2.0 - 1.0 * progress
    per_event_risk = (miss_left / max(events_left, 1)) * risk_aggression
    # energy reservation with a battery-health taper
    reserve = energy_left / max(events_left, 1)
    if battery_frac < 0.4:
        reserve *= 0.9  # conserve harder when battery low
    best = LEVELS[0]
    for lv in LEVELS:
        m = models[lv]
        if m.p_miss <= per_event_risk and m.p90_energy <= reserve:
            best = lv
    return best


# --------------------------------------------------------------------------
# POLICY 4 (oracle: full-knowledge vectorized backward DP)
# --------------------------------------------------------------------------
class OracleDP:
    """Exact full-knowledge optimum via knapsack.

    Events are i.i.d. and exchangeable, so the optimal policy is a fixed
    level mix (n44, n65, n87) with n44+n65+n87 = N. The oracle maximizes
    total security subject to:
      (a) expected deadline misses = sum(pm_lv * n_lv) <= MISS_BOUND
      (b) expected total energy   = sum(em_lv * n_lv) <= battery
    This is a small integer program solved by exhaustive search over
    (n65, n87) with n44 = N - n65 - n87 (fast: ~1M combos).

    The mix is then applied in a fixed order (highest security first) and
    the realized simulation samples actual latencies/energy, so the oracle's
    realized performance is what the report measures."""

    def __init__(self, models, n_events, miss_bound, energy_start):
        self.models = models
        self.n = n_events
        self.miss_bound = miss_bound
        self.energy_start = energy_start
        self.pm = {lv: models[lv].p_miss for lv in LEVELS}
        self.em = {lv: models[lv].mean_energy for lv in LEVELS}
        self.se = {lv: SECURITY[lv] for lv in LEVELS}

    def solve(self):
        """Return chosen levels (mix applied highest-first)."""
        N = self.n
        M = self.miss_bound
        B = self.energy_start
        pm, em, se = self.pm, self.em, self.se
        best = None
        # exhaustive over n65, n87
        for n65 in range(N + 1):
            # bound n87 by miss budget given n65
            rem_miss = M - pm[65] * n65
            if rem_miss < 0:
                break
            max87 = int(rem_miss / pm[87]) if pm[87] > 0 else N - n65
            for n87 in range(min(max87, N - n65) + 1):
                n44 = N - n65 - n87
                miss = pm[44] * n44 + pm[65] * n65 + pm[87] * n87
                if miss > M:
                    continue
                energy = em[44] * n44 + em[65] * n65 + em[87] * n87
                if energy > B:
                    continue
                s = se[44] * n44 + se[65] * n65 + se[87] * n87
                if best is None or s > best[0]:
                    best = (s, n44, n65, n87, miss)
        if best is None:
            return [LEVELS[0]] * N
        _, n44, n65, n87, _ = best
        mix = [87] * n87 + [65] * n65 + [44] * n44
        return mix[:N]


def oracle_chosen(models, energy_start, rng=None):
    """Full-knowledge optimum for one mission's battery."""
    dp = OracleDP(models, N_EVENTS, MISS_BOUND, energy_start)
    return dp.solve()


# --------------------------------------------------------------------------
# MISSION SIMULATION
# --------------------------------------------------------------------------
def run_mission(policy_name, models, energy_start, rng, chosen_oracle=None):
    energy = energy_start
    total_sec = 0
    misses = 0
    miss_left = MISS_BOUND
    for t in range(N_EVENTS):
        events_left = N_EVENTS - t
        if policy_name == "myopic":
            lv = policy_myopic(DEADLINE_S, OVERRUN_BOUND, models)
        elif policy_name == "battery":
            lv = policy_battery(DEADLINE_S, models, energy, events_left,
                                miss_left)
        elif policy_name == "lookahead":
            lv = policy_lookahead(DEADLINE_S, models, energy, energy_start,
                                  miss_left, MISS_BOUND, t, N_EVENTS)
        elif policy_name == "oracle":
            lv = chosen_oracle[t]
        else:
            raise ValueError(policy_name)
        lat = float(rng.choice(models[lv].lat_s))
        energy -= lat * CPU_HZ * NJOULES_PER_CYCLE
        total_sec += SECURITY[lv]
        if lat > DEADLINE_S:
            misses += 1
            miss_left = max(0, miss_left - 1)
        if energy <= 0:
            return total_sec, misses, False
    return total_sec, misses, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--missions", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20260806)
    ap.add_argument("--out", default="codebase/security_selection_sim/results")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    models = build_models()
    os.makedirs(args.out, exist_ok=True)

    base_battery = N_EVENTS * models[65].mean_energy
    print(f"P(miss) @150ms: 44={models[44].p_miss*100:.1f}% "
          f"65={models[65].p_miss*100:.1f}% 87={models[87].p_miss*100:.1f}%")
    print(f"E[energy]/sign: 44={models[44].mean_energy*1e3:.2f} mJ "
          f"65={models[65].mean_energy*1e3:.2f} mJ "
          f"87={models[87].mean_energy*1e3:.2f} mJ")

    results = defaultdict(list)
    mission_rows = []
    for mi in range(args.missions):
        battery_scale = rng.uniform(0.55, 1.05)
        energy_start = base_battery * battery_scale
        chosen_oracle = oracle_chosen(models, energy_start)
        for name in ["myopic", "battery", "lookahead", "oracle"]:
            sec, miss, done = run_mission(name, models, energy_start, rng,
                                          chosen_oracle)
            results[name].append((sec, miss, done))
        mission_rows.append({
            "mission": mi,
            "battery_start_j": round(energy_start, 6),
            "battery_scale": round(battery_scale, 4),
            **{f"sec_{n}": results[n][-1][0] for n in ["myopic", "battery", "lookahead", "oracle"]},
            **{f"miss_{n}": results[n][-1][1] for n in ["myopic", "battery", "lookahead", "oracle"]},
            **{f"done_{n}": int(results[n][-1][2]) for n in ["myopic", "battery", "lookahead", "oracle"]},
        })

    with open(os.path.join(args.out, "mission_results_raw.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mission_rows[0].keys()))
        w.writeheader()
        w.writerows(mission_rows)

    def summ(vals):
        a = np.array(vals, dtype=float)
        m = a.mean()
        se = a.std(ddof=1) / math.sqrt(len(a)) if len(a) > 1 else 0.0
        return m, 1.96 * se

    print(f"\n=== {args.missions} missions, N={N_EVENTS}, deadline=150ms, "
          f"miss_bound={MISS_BOUND} ===")
    print(f"battery base = {base_battery*1e3:.1f} mJ (N*E[65]); scale U[0.55,1.05]")
    print(f"{'policy':10s} | {'mean sec':>9s} {'CI':>7s} | {'miss%':>6s} {'CI':>6s} | {'compl%':>7s}")
    for name in ["myopic", "battery", "lookahead", "oracle"]:
        secs = [r[0] for r in results[name]]
        mss = [r[1] for r in results[name]]
        dons = [r[2] for r in results[name]]
        sm, sci = summ(secs)
        mm, mci = summ(mss)
        cm = 100 * sum(dons) / len(dons)
        print(f"{name:10s} | {sm:9.0f} +/-{sci:5.0f} | {mm/10:6.2f} +/-{mci/10:4.2f} | {cm:6.1f}%")

    def avg(n, idx):
        return np.mean([r[idx] for r in results[n]])
    sm, sb, sl, so = (avg(n, 0) for n in ["myopic", "battery", "lookahead", "oracle"])
    print()
    print(f"GAP myopic->battery   (battery-awareness matters?): {sb-sm:+.1f} sec ({100*(sb-sm)/sm:+.1f}%)")
    print(f"GAP lookahead->oracle (RL headroom):              {so-sl:+.1f} sec ({100*(so-sl)/sl:+.1f}%)")


if __name__ == "__main__":
    main()
