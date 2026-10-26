#!/usr/bin/env python3
"""E1 — the slack-scaling gate.

The reframed architecture claims: certified early exits free deadline slack, and
that slack funds the leakage countermeasure. This script tests the arithmetic
before anything is built on it.

Two things changed since the original scheduling work:
  1. September's -O2 wolfSSL benchmarks made crypto ~8x cheaper than the
     bare-metal PQClean numbers the old scheduler used (ML-KEM-768 handshake
     115.97 ms -> ~21.6 ms for kp+enc+dec).
  2. The activity re-audit showed the demonstrated leak is a DURATION leak, not
     a power-envelope leak (zero cross-class duration overlap; a duration-only
     classifier scores 1.000). So the countermeasure that addresses the measured
     leak is duration equalisation (padding to worst case), not envelope
     randomisation. That also makes its cost deterministic rather than random.

Output: prints the gate table and a verdict. Writes SLACK_GATE.json.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "SLACK_GATE.json")

# --- measured per-exit perception cost, on device -------------------------
# NXP MCXN947: from the free-running policy firmware (joint_scheduler.py)
NXP_EXIT = {1: 0.80, 2: 1.24, 3: 2.34}

# ESP32-S3: measured by seg_timing.cpp (filled in from the hardware run)
ESP_EXIT = {1: 459.344, 2: 574.830, 3: 1005.415}  # measured by seg_timing.cpp on COM17

# --- measured crypto at -O2 (September wolfSSL harness, ms) ----------------
KEM_OP = {                 # keypair, encaps, decaps
    512:  {"kp": 4.36, "enc": 3.76, "dec": 5.08},
    768:  {"kp": 7.01, "enc": 6.37, "dec": 8.24},
    1024: {"kp": 11.07, "enc": 10.14, "dec": 12.56},
}
DSA65_SIGN_MEAN = 60.36
DSA65_SIGN_P99 = 291.54

# energy per handshake (mJ) measured on the MCXN947 (eembc_style captures)
KEM_MJ = {512: 4.20, 768: 6.63, 1024: 9.76}


def padding_cost(ops):
    """Cost of duration-equalising a KEM operation set: pad every op up to the
    slowest one. This is the countermeasure that addresses the measured leak."""
    worst = max(ops.values())
    return sum(worst - v for v in ops.values()), worst


def gate(board, exit_ms, level, budget_ms):
    p1, p2, p3 = exit_ms[1], exit_ms[2], exit_ms[3]
    slack_per_frame = p3 - p1                       # freed by always exiting early
    ops = KEM_OP[level]
    handshake = sum(ops.values())
    pad, worst = padding_cost(ops)
    # perception share of the frame at full depth
    share = p3 / budget_ms
    # how many frames of exit-slack are needed to fund one padded handshake
    frames_to_fund = pad / slack_per_frame if slack_per_frame > 0 else float("inf")
    return {
        "board": board, "level": level, "budget_ms": budget_ms,
        "perception_full_ms": round(p3, 2),
        "perception_share_pct": round(100 * share, 1),
        "exit_slack_per_frame_ms": round(slack_per_frame, 3),
        "handshake_ms": round(handshake, 2),
        "padding_cost_ms": round(pad, 2),
        "frames_of_slack_needed": round(frames_to_fund, 1),
        "handshake_fits_budget": handshake <= budget_ms,
    }


rows = []
for board, exit_ms in (("MCXN947", NXP_EXIT), ("ESP32-S3", ESP_EXIT)):
    for level in (512, 768, 1024):
        for budget in (33.0, 5.0):
            rows.append(gate(board, exit_ms, level, budget))

print(f"{'board':9} {'lvl':>4} {'budget':>7} {'perc%':>6} {'slack/frame':>11} "
      f"{'handshake':>10} {'pad cost':>9} {'frames needed':>14} {'fits':>5}")
for r in rows:
    print(f"{r['board']:9} {r['level']:>4} {r['budget_ms']:>7.1f} "
          f"{r['perception_share_pct']:>6.1f} {r['exit_slack_per_frame_ms']:>11.3f} "
          f"{r['handshake_ms']:>10.2f} {r['padding_cost_ms']:>9.2f} "
          f"{r['frames_of_slack_needed']:>14.1f} {str(r['handshake_fits_budget']):>5}")

# --- verdict logic ---------------------------------------------------------
# The architecture holds if the countermeasure can be funded *from the exit
# slack*, i.e. the slack is a meaningful fraction of what the countermeasure
# costs. If perception is a small share of the frame, early exit frees little.
print()
verdict = {}
for board, exit_ms in (("MCXN947", NXP_EXIT), ("ESP32-S3", ESP_EXIT)):
    p1, p3 = exit_ms[1], exit_ms[3]
    for budget in (33.0, 5.0):
        share = p3 / budget
        slack_frac_of_pad = (p3 - p1) / padding_cost(KEM_OP[768])[0]
        verdict[f"{board}@{budget}ms"] = {
            "perception_share_pct": round(100 * share, 1),
            "exit_slack_as_fraction_of_padding": round(slack_frac_of_pad, 3),
            "holds": bool(share > 0.25 and slack_frac_of_pad > 0.25),
        }
        tag = "HOLDS" if verdict[f"{board}@{budget}ms"]["holds"] else "does NOT hold"
        print(f"  {board:9} @ {budget:>4.1f} ms: perception {100*share:5.1f}% of frame, "
              f"exit slack = {100*slack_frac_of_pad:5.1f}% of padding cost  -> {tag}")

with open(OUT, "w") as f:
    json.dump({"rows": rows, "verdict": verdict}, f, indent=1)
print()
print("wrote", OUT)
print()
print("ESP32-S3 exit costs are measured on hardware (seg_timing.cpp, COM17).")
print()
print("Reading: on the NPU board perception is cheap (2.34 ms) and crypto is not,")
print("so early exit frees little and the architecture is not needed. On the CPU")
print("board perception is enormous (1005 ms) and dominates the frame, so early")
print("exit frees 546 ms per frame -- 176x the cost of padding a KEM handshake.")
