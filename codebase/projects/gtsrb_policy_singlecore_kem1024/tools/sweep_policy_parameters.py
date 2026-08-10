"""
Trace-driven sensitivity analysis: tests whether the headline 14-15%
time-savings result is robust to the CRYPTO_STEP_PERIOD and adaptive
tier-switch window choices, WITHOUT new hardware runs.

Uses three real, hardware-measured inputs (no invented numbers):
  - Per-image conf1/conf2/conf3 from the NAIVE run (ground truth -- naive
    always runs the full chain, so every image has all three confidences
    populated, regardless of what any policy would actually choose).
  - Per-exit-depth mean latency, pooled from the STATIC + ADAPTIVE runs'
    actual measured frame_us grouped by exit_taken (consistent to within
    ~3us between the two runs at every depth -- confirms these are
    policy-independent hardware constants, not run-specific noise).
  - Per-op-type crypto cost, from predict_crypto_cost.py's validated
    predictor (0.164% mean held-out error).

This is standard trace-driven simulation: the mechanism (exit decision
logic, tier-shift rule) is unchanged from the real firmware, only the
schedule parameters are swept. The single (period=10, window=4) operating
point in the main experiment IS still the one validated directly on
hardware; this sweep checks whether that result generalizes.

Usage: python tools/sweep_policy_parameters.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent

TAU1_A05, TAU2_A05 = 0.957, 0.926
TAU1_A10, TAU2_A10 = 0.918, 0.725
OP_NAMES = ["keypair", "encap", "decap"]
OP_COST_US = {"keypair": 32635.8, "encap": 37958.1, "decap": 45396.6}


def load_naive_confidences():
    with open(HERE / "policy_results_naive.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    return [(float(r["conf1"]), float(r["conf2"]), float(r["conf3"])) for r in rows]


def pooled_depth_latency():
    latencies = {1: [], 2: [], 3: []}
    for p in ("static", "adaptive"):
        with open(HERE / f"policy_results_{p}.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            latencies[int(r["exit_taken"])].append(int(r["frame_us"]))
    return {depth: sum(vals) / len(vals) for depth, vals in latencies.items()}


def simulate(confidences, depth_latency_us, period, window, adaptive):
    """Replays the frame sequence under given (period, window), returns
    total device time in us. adaptive=False => static policy (always
    alpha=0.05). window is only used when adaptive=True; it's the number
    of frames on EACH side of a crypto step that count as "imminent"
    (matches the real firmware's `(pos<=1)||(pos>=period-2)` rule, which
    is window=2 in this convention: 2 frames before + 2 after = 4 total,
    i.e. 40% of a period=10 cycle)."""
    total_us = 0.0
    op_idx = 0
    n = len(confidences)
    for i, (c1, c2, c3) in enumerate(confidences):
        pos = i % period
        if pos == 0:
            total_us += OP_COST_US[OP_NAMES[op_idx % 3]]
            op_idx += 1

        if adaptive:
            imminent = (pos <= window - 1) or (pos >= period - window)
            tau1, tau2 = (TAU1_A10, TAU2_A10) if imminent else (TAU1_A05, TAU2_A05)
        else:
            tau1, tau2 = TAU1_A05, TAU2_A05

        if c1 >= tau1:
            total_us += depth_latency_us[1]
        elif c2 >= tau2:
            total_us += depth_latency_us[2]
        else:
            total_us += depth_latency_us[3]
    return total_us


def simulate_naive(n_frames, period):
    total_us = 0.0
    op_idx = 0
    full_chain_us = FULL_CHAIN_US
    for i in range(n_frames):
        if i % period == 0:
            total_us += OP_COST_US[OP_NAMES[op_idx % 3]]
            op_idx += 1
        total_us += full_chain_us
    return total_us


def main():
    global FULL_CHAIN_US
    confidences = load_naive_confidences()
    depth_latency = pooled_depth_latency()
    FULL_CHAIN_US = depth_latency[3]  # naive always runs the full chain
    n = len(confidences)
    print(f"n_frames={n}")
    print(f"pooled depth latency (us): exit1={depth_latency[1]:.1f} "
          f"exit2={depth_latency[2]:.1f} exit3={depth_latency[3]:.1f}")
    print(f"crypto op costs (us): {OP_COST_US}\n")

    periods = [5, 10, 20, 40]
    windows = [1, 2, 3, 4]

    print("=== STATIC vs NAIVE, swept over CRYPTO_STEP_PERIOD ===")
    print(f"{'period':<10}{'naive_ms':<12}{'static_ms':<12}{'savings_%':<10}")
    for period in periods:
        naive_us = simulate_naive(n, period)
        static_us = simulate(confidences, depth_latency, period, window=0, adaptive=False)
        savings = (naive_us - static_us) / naive_us * 100
        print(f"{period:<10}{naive_us/1000:<12.1f}{static_us/1000:<12.1f}{savings:<10.2f}")

    print("\n=== ADAPTIVE vs NAIVE, swept over (period, window) ===")
    print(f"{'period':<8}{'window':<8}{'naive_ms':<12}{'adaptive_ms':<13}{'savings_%':<10}"
          f"{'vs_static_ms':<14}")
    for period in periods:
        naive_us = simulate_naive(n, period)
        static_us = simulate(confidences, depth_latency, period, window=0, adaptive=False)
        for window in windows:
            if window * 2 > period:
                continue  # window can't exceed half the period
            adaptive_us = simulate(confidences, depth_latency, period, window, adaptive=True)
            savings = (naive_us - adaptive_us) / naive_us * 100
            vs_static = (static_us - adaptive_us) / 1000
            print(f"{period:<8}{window:<8}{naive_us/1000:<12.1f}{adaptive_us/1000:<13.1f}"
                  f"{savings:<10.2f}{vs_static:<14.2f}")

    print("\n=== reference: hardware-validated operating point (period=10, window=2) ===")
    naive_us = simulate_naive(n, 10)
    static_us = simulate(confidences, depth_latency, 10, window=0, adaptive=False)
    adaptive_us = simulate(confidences, depth_latency, 10, window=2, adaptive=True)
    print(f"simulated:  naive={naive_us/1000:.1f}ms static={static_us/1000:.1f}ms "
          f"adaptive={adaptive_us/1000:.1f}ms")
    print(f"measured:   naive=7633.6ms static=6542.4ms adaptive=6476.2ms")
    print("(simulated vs measured should match closely -- this validates the")
    print(" simulation methodology against the real hardware run before trusting")
    print(" the swept, never-hardware-tested parameter combinations above)")


if __name__ == "__main__":
    main()
