"""
Compares the three policy runs (naive, static, adaptive) on the same
1230-image sample with identical crypto scheduling (verified: 41 handshakes
each). Metrics:
  - total device-side time to complete the fixed workload (sum of
    crypto_us + frame_us across all 1230 frames) -- the headline number.
  - exit-depth distribution per policy.
  - achieved safety-critical miss-rate (final prediction vs true label,
    restricted to safety-critical classes) -- must stay a fair comparison:
    naive's "final prediction" is always exit3; static/adaptive's is
    whichever exit it actually stopped at.
  - for adaptive, how often each certified tier (alpha=0.05 vs 0.10) was
    used, and split of miss-rate by tier.

Usage: python tools/analyze_policy_experiment.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent
SAFETY_CRITICAL = {0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16,
                    11, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31}


def load(policy):
    with open(HERE / f"policy_results_{policy}.csv", newline="") as f:
        return list(csv.DictReader(f))


def final_pred(row):
    """Whichever exit was actually taken carries the prediction used."""
    exit_taken = int(row["exit_taken"])
    if exit_taken == 1:
        return int(row["pred1"])
    if exit_taken == 2:
        return int(row["pred2"])
    return int(row["pred3"])


def main():
    policies = ["naive", "static", "adaptive"]
    data = {p: load(p) for p in policies}

    print(f"{'policy':<10}{'total_device_us':<18}{'total_ms':<10}{'crypto_us':<12}{'frame_us':<12}")
    totals = {}
    for p in policies:
        rows = data[p]
        crypto_total = sum(int(r["crypto_us"]) for r in rows)
        frame_total = sum(int(r["frame_us"]) for r in rows)
        total = crypto_total + frame_total
        totals[p] = total
        print(f"{p:<10}{total:<18}{total/1000:<10.1f}{crypto_total:<12}{frame_total:<12}")

    print()
    naive_total = totals["naive"]
    for p in policies:
        delta = naive_total - totals[p]
        pct = delta / naive_total * 100
        print(f"{p}: {'-' if p=='naive' else f'{delta/1000:.1f} ms faster than naive ({pct:.1f}%)'}")

    print("\n--- exit distribution ---")
    for p in policies:
        rows = data[p]
        n = len(rows)
        counts = {1: 0, 2: 0, 3: 0}
        for r in rows:
            counts[int(r["exit_taken"])] += 1
        print(f"{p:<10} exit1={counts[1]} ({counts[1]/n*100:.1f}%)  "
              f"exit2={counts[2]} ({counts[2]/n*100:.1f}%)  "
              f"exit3={counts[3]} ({counts[3]/n*100:.1f}%)")

    print("\n--- achieved safety-critical miss-rate (final prediction vs true label) ---")
    for p in policies:
        rows = data[p]
        sc = [r for r in rows if int(r["is_safety_critical"]) == 1]
        n = len(sc)
        n_miss = sum(1 for r in sc if final_pred(r) != int(r["label"]))
        print(f"{p:<10} n={n}  miss={n_miss}  miss_rate={n_miss/n:.4f}")

    print("\n--- adaptive: tier usage ---")
    rows = data["adaptive"]
    tier_counts = {5: 0, 10: 0}
    for r in rows:
        tier_counts[int(r["tier_used"])] += 1
    n = len(rows)
    print(f"alpha=0.05 (normal): {tier_counts[5]} ({tier_counts[5]/n*100:.1f}%)")
    print(f"alpha=0.10 (loosened, near crypto): {tier_counts[10]} ({tier_counts[10]/n*100:.1f}%)")

    for tier in (5, 10):
        tier_rows = [r for r in rows if int(r["tier_used"]) == tier]
        sc = [r for r in tier_rows if int(r["is_safety_critical"]) == 1]
        if not sc:
            continue
        n_miss = sum(1 for r in sc if final_pred(r) != int(r["label"]))
        alpha = tier / 100
        print(f"  tier alpha={alpha}: n_sc={len(sc)} miss={n_miss} "
              f"miss_rate={n_miss/len(sc):.4f} (target <= {alpha})")

    print("\n--- handshake fairness check ---")
    for p in policies:
        rows = data[p]
        n_steps = sum(1 for r in rows if int(r["crypto_us"]) > 0)
        print(f"{p:<10} crypto steps run: {n_steps} (expect 123)")


if __name__ == "__main__":
    main()
