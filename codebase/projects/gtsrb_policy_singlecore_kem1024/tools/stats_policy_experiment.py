"""
Statistical significance testing for the naive/static/adaptive policy
comparison. The three runs used the IDENTICAL 1230-image sequence in the
same order (verified below), which sets up a proper PAIRED comparison:

  - Wilcoxon signed-rank test on per-frame perception latency (frame_us),
    pairwise between policies. Tests whether the latency reduction from
    exiting early is a real, consistent per-frame effect (not just a
    difference in a few outlier frames).
  - McNemar's test (paired binary correct/incorrect on safety-critical
    frames) between policies. Tests whether the small miss-rate
    differences (0.1481/0.1491/0.1500) are statistically distinguishable
    from each other at all, or just noise on top of an equivalent
    underlying error rate.

Usage: python tools/stats_policy_experiment.py
"""
import csv
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon, chi2

HERE = Path(__file__).parent


def load(policy):
    with open(HERE / f"policy_results_{policy}.csv", newline="") as f:
        return list(csv.DictReader(f))


def final_pred(row):
    exit_taken = int(row["exit_taken"])
    if exit_taken == 1:
        return int(row["pred1"])
    if exit_taken == 2:
        return int(row["pred2"])
    return int(row["pred3"])


def mcnemar(correct_a, correct_b):
    """Continuity-corrected McNemar's test on paired binary outcomes."""
    n01 = sum(1 for a, b in zip(correct_a, correct_b) if a and not b)
    n10 = sum(1 for a, b in zip(correct_a, correct_b) if not a and b)
    if n01 + n10 == 0:
        return n01, n10, float("nan"), 1.0
    stat = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
    p = chi2.sf(stat, df=1)
    return n01, n10, stat, p


def main():
    policies = ["naive", "static", "adaptive"]
    data = {p: load(p) for p in policies}

    # Verify identical frame ordering across all three runs -- required for
    # any paired test to be valid.
    ids = {p: [r["filename"] for r in data[p]] for p in policies}
    assert ids["naive"] == ids["static"] == ids["adaptive"], \
        "frame ordering differs between policy runs -- paired tests invalid"
    n = len(ids["naive"])
    print(f"verified: identical {n}-frame ordering across all three runs\n")

    frame_us = {p: np.array([int(r["frame_us"]) for r in data[p]]) for p in policies}

    print("=== Wilcoxon signed-rank test: per-frame perception latency (frame_us) ===")
    pairs = [("naive", "static"), ("naive", "adaptive"), ("static", "adaptive")]
    for a, b in pairs:
        diff = frame_us[a] - frame_us[b]
        n_nonzero = int(np.sum(diff != 0))
        stat, p = wilcoxon(frame_us[a], frame_us[b])
        median_diff = float(np.median(diff))
        print(f"{a} vs {b}: median(diff)={median_diff:.0f} us, "
              f"n_nonzero_pairs={n_nonzero}/{n}, W={stat:.1f}, p={p:.3e}")

    print("\n=== McNemar's test: paired safety-critical correctness ===")
    correct = {}
    for p in policies:
        sc_rows = [r for r in data[p] if int(r["is_safety_critical"]) == 1]
        correct[p] = [final_pred(r) == int(r["label"]) for r in sc_rows]
    n_sc = len(correct["naive"])
    print(f"(n_safety_critical={n_sc})")
    for a, b in pairs:
        n01, n10, stat, p = mcnemar(correct[a], correct[b])
        print(f"{a} vs {b}: {a}-correct/{b}-wrong={n01}, {a}-wrong/{b}-correct={n10}, "
              f"chi2={stat:.3f}, p={p:.4f}")

    print("\n=== Interpretation ===")
    print("Latency: Wilcoxon p-values test whether exiting early is a consistent,")
    print("frame-by-frame effect (expected: very small p, since NAIVE always runs")
    print("segC and static/adaptive often don't -- this is close to definitional,")
    print("included for completeness/rigor rather than as a surprising finding).")
    print("Accuracy: McNemar's p-values test whether the ~0.1pp-1pp miss-rate")
    print("differences between policies are distinguishable from chance at this")
    print("sample size, or consistent with equivalent underlying error rates.")


if __name__ == "__main__":
    main()
