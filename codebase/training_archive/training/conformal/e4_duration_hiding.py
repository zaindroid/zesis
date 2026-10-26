#!/usr/bin/env python3
"""E4 re-run — deadline-aware hiding, with the corrected threat model.

Two corrections against the original `leakage_aware_scheduler.py`:

1. COSTS. The original used bare-metal PQClean numbers (ML-KEM-768 handshake
   115.97 ms). September's -O2 wolfSSL harness measured a 768 handshake at
   ~21.6 ms (7.01 + 6.37 + 8.24). An 8x cheaper threat changes the answer.

2. THREAT MODEL. The activity re-audit showed the demonstrated leak is a
   DURATION leak, not a power-envelope leak: the three ML-KEM operations have
   zero cross-class duration overlap and a duration-only classifier scores
   1.000. So the countermeasure that addresses the *measured* leak is
   duration equalisation -- pad every operation to the slowest one -- not
   envelope randomisation. That also makes its cost deterministic.

Policies compared:
  no_defense    : no padding. Every op identifiable by duration.
  always_pad    : pad every op to worst case. Full hiding, full cost.
  deadline_aware: pad only while accumulated slack allows. Partial hiding.

Output: results/leakage_aware/E4_DURATION_HIDING.json + a printed table.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "E4_DURATION_HIDING.json")

N_FRAMES = 1230
CRYPTO_STEP_PERIOD = 10          # one KEM sub-step every 10 frames

# per-exit perception cost, NXP MCXN947 (ms)
EXIT_MS = {1: 0.80, 2: 1.24, 3: 2.34}

# KEM operations at -O2 (ms) and their measured energy (mJ per handshake)
KEM_OPS = {
    512:  {"kp": 4.36, "enc": 3.76, "dec": 5.08,  "mj": 4.20},
    768:  {"kp": 7.01, "enc": 6.37, "dec": 8.24,  "mj": 6.63},
    1024: {"kp": 11.07, "enc": 10.14, "dec": 12.56, "mj": 9.76},
}

# exit distribution observed on the device (fraction of frames per exit)
EXIT_DIST = {1: 0.453, 2: 0.165, 3: 0.382}

DEADLINE_MS = 33.0
CHANCE = 1.0 / 3.0               # attacker guessing op type at random


def run(level, budget_ms, policy, obf_period_frames=10):
    ops = KEM_OPS[level]
    names = ["kp", "enc", "dec"]
    worst = max(ops[n] for n in names)

    miss = 0
    pad_ms_total = 0.0
    padded_ops = 0
    total_ops = 0
    slack_bank = 0.0

    for f in range(N_FRAMES):
        # perception cost for this frame
        e = 1 if (f % 3) == 0 else (2 if (f % 7) == 0 else 3)
        perc = EXIT_MS[min(EXIT_DIST, key=lambda k: abs(k - e))] if False else EXIT_MS[3]
        # use the expected perception cost, not the worst, for the mean frame
        perc = sum(EXIT_MS[k] * v for k, v in EXIT_DIST.items())

        frame = perc
        # slack freed relative to always running the full depth
        slack_bank += EXIT_MS[3] - perc

        if f % obf_period_frames == 0:
            # one crypto operation this frame (rotating kp/enc/dec)
            op = names[(f // obf_period_frames) % 3]
            dur = ops[op]
            total_ops += 1

            if policy == "no_defense":
                frame += dur
            elif policy == "always_pad":
                frame += worst
                pad_ms_total += worst - dur
                padded_ops += 1
            elif policy == "deadline_aware":
                have = max(slack_bank, 0.0)
                need = worst - dur
                if have >= need and need > 0:
                    frame += worst
                    pad_ms_total += need
                    padded_ops += 1
                    slack_bank -= need
                else:
                    frame += dur

        if frame > budget_ms:
            miss += 1

    # energy: baseline + extra time spent padding (energy ~ time at fixed power)
    base_mj = ops["mj"] * (N_FRAMES / (3 * obf_period_frames)) * 3
    extra_mj = pad_ms_total / (sum(ops[n] for n in names)) * ops["mj"]
    energy = base_mj + extra_mj

    # attacker: identifies an op by duration unless it was padded to worst case
    identifiable = total_ops - padded_ops + (0 if policy == "always_pad" else 0)
    acc = identifiable / total_ops if total_ops else 0.0
    if policy == "always_pad":
        acc = CHANCE

    return {
        "level": level, "budget_ms": budget_ms, "policy": policy,
        "deadline_misses": miss,
        "pad_ms_total": round(pad_ms_total, 1),
        "ops_padded": padded_ops, "ops_total": total_ops,
        "energy_mj": round(energy, 1),
        "energy_overhead_pct": round(100 * (energy - base_mj) / base_mj, 1) if base_mj else 0.0,
        "attacker_acc": round(acc, 3),
    }


rows = []
for level in (512, 768, 1024):
    for pol in ("no_defense", "always_pad", "deadline_aware"):
        rows.append(run(level, DEADLINE_MS, pol))

print(f"deadline {DEADLINE_MS:.0f} ms, {N_FRAMES} frames, 1 crypto op per "
      f"{CRYPTO_STEP_PERIOD} frames\n")
print(f"{'lvl':>4} {'policy':>15} {'misses':>7} {'padded':>9} {'energy mJ':>10} "
      f"{'overhead':>9} {'attacker acc':>13}")
for r in rows:
    print(f"{r['level']:>4} {r['policy']:>15} {r['deadline_misses']:>7} "
          f"{r['ops_padded']:>4}/{r['ops_total']:<4} {r['energy_mj']:>10.1f} "
          f"{r['energy_overhead_pct']:>8.1f}% {r['attacker_acc']:>13.3f}")

print()
print("Reference: the ORIGINAL scheduler used a 115.97 ms 768 handshake and")
print("reported the allocation INFEASIBLE at level 768 (no slack fit a dummy op).")
old_handshake = 115.97
new_handshake = sum(KEM_OPS[768][n] for n in ("kp", "enc", "dec"))
print(f"  handshake then: {old_handshake:.2f} ms   now: {new_handshake:.2f} ms  "
      f"({old_handshake/new_handshake:.1f}x cheaper)")

with open(OUT, "w") as f:
    json.dump({"rows": rows, "deadline_ms": DEADLINE_MS,
               "old_handshake_ms": old_handshake,
               "new_handshake_ms": round(new_handshake, 2)}, f, indent=1)
print()
print("wrote", OUT)
