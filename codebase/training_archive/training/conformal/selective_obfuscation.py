#!/usr/bin/env python3
"""Experiment 3: Selective / probabilistic side-channel obfuscation.

The leakage-aware scheduler (#2) showed that FULL dummy-crypto obfuscation is
infeasible at ML-KEM-768 under the 33 ms frame deadline. This experiment tests
the engineering compromise: insert dummy crypto ONLY sometimes.

Policies (all on top of the same real-crypto schedule, every 10th frame):
  - no_defense         : real crypto only (baseline, attacker = 100%)
  - fixed_dummy        : dummy after EVERY real step (the infeasible full case)
  - probabilistic_p03  : dummy after each real step with p=0.3 (random schedule
                         -> the attacker cannot rely on fixed timing)
  - exit1_selective    : dummy after a real step ONLY when the perception in
                         the next frame exits at exit1 (cheapest exit -> most
                         timing headroom). Uses the measured adaptive-policy
                         exit distribution (exit1 45%, exit2 17%, exit3 38%).
  - exit1_selective_hi : same, but an exit1-dominated workload (all exit1).

Two attacker targets are reported:
  A) real-vs-dummy crypto identification (naive 'every step is real' accuracy
     = reals/(reals+dummies); hidden = real steps with a dummy within 1 frame)
  B) exit-decision leakage (the measured RF envelope classifier was 98.3% on
     clean envelopes; a dummy in the frame contaminates the envelope, modeled
     transparently as accuracy -> 1/3 chance on dummy frames, 98.3% otherwise)

All costs from real measurements (MCXN947, same as joint_scheduler.py).
"""
import numpy as np
import os, json

EXIT_MS = {1: 0.80, 2: 1.24, 3: 2.34}
KEM_MS = {512: 72.17, 768: 115.97, 1024: 174.91}
KEM_MJ = {512: 4.20, 768: 6.63, 1024: 9.76}
STEP_MS = {k: v / 3 for k, v in KEM_MS.items()}
STEP_MJ = {k: v / 3 for k, v in KEM_MJ.items()}
CRYPTO_STEP_PERIOD = 10
DEADLINE_MS = 33.0
BUF_FRAMES = 3
N_FRAMES = 1230
N_STEPS = N_FRAMES // CRYPTO_STEP_PERIOD   # 123 real crypto steps

# measured adaptive exit distribution (interleaved experiment, ESP32 rows are
# the same shape; used here as the representative anytime-exit workload)
EXIT_DIST = {1: 0.453, 2: 0.165, 3: 0.382}
EXIT_RF_ACC = 0.983          # measured exit-decision RF accuracy (clean env)
CHANCE = 1.0 / 3.0
RNG = np.random.default_rng(20260811)

OUT = os.path.join(os.path.dirname(__file__), "..", "results", "leakage_aware")
os.makedirs(OUT, exist_ok=True)

def gen_exits(hi_exit1=False):
    r = RNG.random(N_FRAMES)
    if hi_exit1:
        return np.ones(N_FRAMES, dtype=int)
    out = np.empty(N_FRAMES, dtype=int)
    # CDF of EXIT_DIST
    cdf = {1: EXIT_DIST[1], 2: EXIT_DIST[1] + EXIT_DIST[2], 3: 1.0}
    for i, u in enumerate(r):
        out[i] = 1 if u < cdf[1] else (2 if u < cdf[2] else 3)
    return out

def sim_backlog(step_times, dummies):
    events = []
    for (fi, ms, mj) in step_times: events.append((fi, ms, mj, "real"))
    for (fi, ms, mj) in dummies:    events.append((fi, ms, mj, "dummy"))
    events.sort(key=lambda e: e[0])
    backlog = 0.0; misses = 0; total_ms = 0.0; total_mj = 0.0
    for fi, ms, mj, kind in events:
        total_ms += ms; total_mj += mj
        slot_left = DEADLINE_MS - backlog
        backlog = (ms - slot_left) if ms > slot_left else 0.0
        if backlog > BUF_FRAMES * DEADLINE_MS:
            misses += 1; backlog = 0.0
    return misses, total_ms, total_mj

def attacker_metrics(reals, dummies):
    real_set = set(reals)
    all_t = sorted(reals + dummies)
    naive_acc = len(reals) / max(1, len(all_t))
    dummy_set = set(dummies)
    hidden = sum(1 for r in reals if any(abs(r - d) <= 1 for d in dummy_set))
    return naive_acc, hidden / max(1, len(reals))

def exit_leak_accuracy(exits, dummies):
    """Model B: RF exit classifier at 98.3% on clean frames; dummy frames
    contaminate the envelope -> accuracy decays to chance."""
    dummy_frames = set(d[0] for d in dummies)
    acc = 0.0
    for i, e in enumerate(exits):
        if i in dummy_frames:
            acc += CHANCE          # contaminated envelope ~ chance
        else:
            acc += EXIT_RF_ACC     # clean envelope ~ measured RF
    return acc / len(exits)

def run(policy, level, p=0.3):
    reals = list(range(CRYPTO_STEP_PERIOD - 1, N_FRAMES, CRYPTO_STEP_PERIOD))[:N_STEPS]
    ms_r = STEP_MS[level]; mj_r = STEP_MJ[level]
    real_steps = [(fi, ms_r, mj_r) for fi in reals]
    exits = gen_exits(hi_exit1=(policy == "exit1_selective_hi"))

    if policy == "no_defense":
        dummies = []
    elif policy == "fixed_dummy":
        dummies = [(fi + 1, ms_r, mj_r) for fi in reals if fi + 1 < N_FRAMES]
    elif policy == "probabilistic_p03":
        dummies = []
        for fi in reals:
            if fi + 1 < N_FRAMES and RNG.random() < p:
                dummies.append((fi + 1, ms_r, mj_r))
    elif policy in ("exit1_selective", "exit1_selective_hi"):
        dummies = []
        for fi in reals:
            nxt = fi + 1
            if nxt < N_FRAMES and exits[nxt] == 1:
                dummies.append((nxt, ms_r, mj_r))
    else:
        raise ValueError(policy)

    misses, total_ms, total_mj = sim_backlog(real_steps, dummies)
    naive_acc, hidden = attacker_metrics(reals, [d[0] for d in dummies])
    exit_acc = exit_leak_accuracy(exits, dummies)
    return dict(policy=policy, level=level, misses=misses,
                total_ms=total_ms, total_mj=total_mj,
                n_real=len(reals), n_dummy=len(dummies),
                crypto_attacker_acc=naive_acc, hidden_frac=hidden,
                exit_leak_acc=exit_acc)

def main():
    print("=== Experiment 3: selective / probabilistic obfuscation ===")
    for level in (512, 768):
        print(f"\n--- ML-KEM-{level} ({N_FRAMES} frames, {N_STEPS} real steps, 33ms slots) ---")
        print(f"{'policy':<22}{'misses':>7}{'+time':>8}{'+energy':>9}{'dum':>5}"
              f"{'crypto_att':>11}{'hidden':>8}{'exit_leak':>10}")
        base = run("no_defense", level)
        for pol in ["no_defense", "fixed_dummy", "probabilistic_p03",
                    "exit1_selective", "exit1_selective_hi"]:
            r = run(pol, level)
            print(f"{pol:<22}{r['misses']:>7}{r['total_ms']/base['total_ms']*100-100:+7.1f}%"
                  f"{r['total_mj']/base['total_mj']*100-100:+8.1f}%{r['n_dummy']:>5}"
                  f"{r['crypto_attacker_acc']:>11.3f}{r['hidden_frac']:>8.3f}"
                  f"{r['exit_leak_acc']:>10.3f}")

    results = {l: {p: run(p, l) for p in ["no_defense", "fixed_dummy",
              "probabilistic_p03", "exit1_selective", "exit1_selective_hi"]}
               for l in (512, 768)}
    with open(os.path.join(OUT, "selective_obfuscation_summary.json"), "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nsaved -> {OUT}/selective_obfuscation_summary.json")

if __name__ == "__main__":
    main()
