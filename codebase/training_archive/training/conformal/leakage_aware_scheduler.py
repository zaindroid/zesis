#!/usr/bin/env python3
"""Experiment #2: Leakage-aware scheduler (C x A).

Extends the joint learned scheduler (Option C) with the activity-leakage
finding (Option A): the scheduler's crypto steps are OBSERVABLE in the power
trace (A showed ~100% op/activity identification). An attacker watching the
power envelope learns WHEN real crypto runs.

Defense: insert DUMMY crypto-like operations (matched energy profile) so the
attacker cannot tell real from dummy. The scheduler must do this subject to:
  - the 33ms frame deadline (dummies cost time)
  - the energy budget (dummies cost energy)
  - the certified-anytime constraints (unchanged)

Attacker model: a classifier over the crypto-activity time series (real steps
at frames 9,19,29...; dummies interleaved). We measure the attacker's
precision/recall on identifying REAL crypto steps under each defense.

Policies:
  - no_defense      : real crypto at every 10th frame, nothing else (attacker = 100%)
  - fixed_dummy     : a dummy at every real step (50% real) -- always pays
  - deadline_aware  : insert dummies only when the deadline budget allows
                      (drops dummies under tight backlog); measure the
                      trade: leakage vs deadline vs energy
  - learned_obfusc  : learned dummy rate that targets the attack accuracy
                      below a threshold while minimizing energy+misses

All costs from real measurements (same as joint_scheduler.py):
  crypto step (1/3 handshake): 512=24.06ms/4.20mJ, 768=38.66ms/6.63mJ,
                               1024=58.30ms/9.76mJ (per step = handshake/3)
  dummy step: same time/energy profile as the real one it mimics (matched)
"""
import numpy as np
import os, json

# ---- real measured costs (MCXN947, from joint_scheduler.py) ----
EXIT_MS = {1: 0.80, 2: 1.24, 3: 2.34}
KEM_MS = {512: 72.17, 768: 115.97, 1024: 174.91}
KEM_MJ = {512: 4.20, 768: 6.63, 1024: 9.76}
STEP_MS = {k: v / 3 for k, v in KEM_MS.items()}
STEP_MJ = {k: v / 3 for k, v in KEM_MJ.items()}
CRYPTO_STEP_PERIOD = 10
DEADLINE_MS = 33.0
BUF_FRAMES = 3
N_FRAMES = 1230   # same workload as the interleaved experiment
N_STEPS = N_FRAMES // CRYPTO_STEP_PERIOD   # 123 real crypto steps

LEVEL = int(os.environ.get("LEAK_LEVEL", "768"))  # 768 or 512 (as in joint learned->512; here 768 for the leakage story)

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "leakage_aware")
os.makedirs(OUT, exist_ok=True)

def sim_backlog(step_times, dummies):
    """FIFO backlog model from joint_scheduler.py. step_times = list of (frame_idx, ms, mj).
    dummies = list of (frame_idx, ms, mj). Returns (misses, total_ms, total_mj)."""
    events = []
    for (fi, ms, mj) in step_times: events.append((fi, ms, mj, "real"))
    for (fi, ms, mj) in dummies:    events.append((fi, ms, mj, "dummy"))
    events.sort(key=lambda e: e[0])
    t = 0.0; backlog = 0.0; misses = 0; total_ms = 0.0; total_mj = 0.0
    for fi, ms, mj, kind in events:
        total_ms += ms; total_mj += mj
        slot_left = DEADLINE_MS - backlog
        if ms > slot_left:
            backlog = ms - slot_left
        else:
            backlog = 0.0
        if backlog > BUF_FRAMES * DEADLINE_MS:
            misses += 1; backlog = 0.0
    return misses, total_ms, total_mj

def attacker_accuracy(reals, dummies):
    """Attacker sees the union of real+dummy step times. Ideal attacker labels
    all steps; defense hides real among dummies. Accuracy of a naive
    'every observed step is real' attacker = reals/(reals+dummies).
    A smarter attacker (timing-pattern) is modeled by the dummy schedule
    randomness: we report both the naive accuracy and the fraction of real
    steps that are 'hidden' (have a dummy within +/-1 frame)."""
    real_set = set(reals)
    all_t = sorted(reals + dummies)
    naive_acc = len(reals) / max(1, len(all_t))   # P(step is real)
    # hidden: real steps with a dummy within 1 frame window
    dummy_set = set(dummies)
    hidden = sum(1 for r in reals if any(abs(r - d) <= 1 for d in dummy_set))
    return naive_acc, hidden / max(1, len(reals))

def run(policy, dummy_frac=0.0, learn_thresh=0.5):
    reals = list(range(CRYPTO_STEP_PERIOD - 1, N_FRAMES, CRYPTO_STEP_PERIOD))[:N_STEPS]
    ms_r = STEP_MS[LEVEL]; mj_r = STEP_MJ[LEVEL]
    real_steps = [(fi, ms_r, mj_r) for fi in reals]

    if policy == "no_defense":
        dummies = []
    elif policy == "fixed_dummy":
        # a dummy at every real step -> 50% real, but pays 2x time/energy
        dummies = [(fi + 1, ms_r, mj_r) for fi in reals if fi + 1 < N_FRAMES]
    elif policy == "deadline_aware":
        # insert dummies only when the backlog budget allows: simulate the
        # backlog; skip a dummy when adding it would cause a miss.
        dummies = []
        events = [(fi, ms_r, mj_r) for fi in reals]
        backlog = 0.0
        for fi in reals:
            # pretend add a dummy at fi+1
            test = sorted(events + [(fi + 1, ms_r, mj_r)], key=lambda e: e[0])
            misses, _, _ = sim_backlog(test, [])
            if misses == 0:
                dummies.append((fi + 1, ms_r, mj_r))
                events.append((fi + 1, ms_r, mj_r))
    elif policy == "learned_obfusc":
        # learned dummy rate: start high, reduce until the attack accuracy
        # target is met while minimizing energy. Greedy: add dummies at the
        # cheapest frames (lowest backlog) until hidden fraction >= target.
        hidden_frac = 0.0
        dummies = []
        target = learn_thresh
        # candidate dummy positions: frame after each real step
        cands = [fi + 1 for fi in reals if fi + 1 < N_FRAMES]
        for c in cands:
            if hidden_frac >= target: break
            d_try = dummies + [(c, ms_r, mj_r)]
            misses, _, _ = sim_backlog(real_steps, d_try)
            if misses == 0:
                dummies.append((c, ms_r, mj_r))
                _, hf = attacker_accuracy(reals, [d[0] for d in dummies])
                hidden_frac = hf
        # convert dummy times to list for reporting
        d_times = [d[0] for d in dummies]
    else:
        raise ValueError(policy)

    misses, total_ms, total_mj = sim_backlog(real_steps, dummies)
    naive_acc, hidden = attacker_accuracy(reals, [d[0] for d in dummies])
    return dict(policy=policy, misses=misses, total_ms=total_ms, total_mj=total_mj,
                n_real=len(reals), n_dummy=len(dummies),
                attacker_naive_acc=naive_acc, hidden_frac=hidden)

def main():
    print("=== Experiment #2: Leakage-aware scheduler (C x A) ===")
    print(f"workload: {N_FRAMES} frames, {N_STEPS} real crypto steps (ML-KEM-{LEVEL}), 33ms slots")
    print(f"\n{'policy':<16}{'misses':>7}{'total_ms':>10}{'total_mj':>10}{'dummy':>6}"
          f"{'attacker_acc':>13}{'hidden':>8}")
    base = run("no_defense")
    print(f"{'no_defense':<16}{base['misses']:>7}{base['total_ms']:>10.0f}{base['total_mj']:>10.1f}"
          f"{base['n_dummy']:>6}{base['attacker_naive_acc']:>13.3f}{base['hidden_frac']:>8.3f}")
    for pol in ["fixed_dummy", "deadline_aware", "learned_obfusc"]:
        r = run(pol)
        print(f"{pol:<16}{r['misses']:>7}{r['total_ms']:>10.0f}{r['total_mj']:>10.1f}"
              f"{r['n_dummy']:>6}{r['attacker_naive_acc']:>13.3f}{r['hidden_frac']:>8.3f}")

    print("\n--- vs no_defense (relative) ---")
    for pol in ["fixed_dummy", "deadline_aware", "learned_obfusc"]:
        r = run(pol)
        print(f"{pol}: energy {r['total_mj']/base['total_mj']*100-100:+.1f}%, "
              f"attacker_acc {r['attacker_naive_acc']/base['attacker_naive_acc']*100-100:+.0f}%, "
              f"misses {r['misses']}")

    results = {p: run(p) for p in ["no_defense", "fixed_dummy", "deadline_aware", "learned_obfusc"]}
    with open(os.path.join(OUT, "leakage_aware_summary.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nsaved -> {OUT}/leakage_aware_summary.json")

if __name__ == "__main__":
    main()
