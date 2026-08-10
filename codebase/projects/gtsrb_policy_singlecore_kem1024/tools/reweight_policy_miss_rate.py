"""
Same natural-frequency reweighting as
gtsrb_multiexit/tools/hw_validate/compute_natural_weighted_coverage.py,
applied to the three policy experiment results (naive/static/adaptive).
Same sample (same manifest), same clean reweighting since every
safety-critical class has natural count >= 40 = the sample's per-class cap.

Usage: python tools/reweight_policy_miss_rate.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent

NATURAL_COUNTS = {
    0: 60, 1: 720, 2: 750, 3: 450, 4: 660, 5: 630, 7: 450, 8: 450, 9: 480,
    10: 660, 11: 420, 15: 210, 16: 150, 18: 390, 19: 60, 20: 90, 21: 90,
    22: 120, 23: 150, 24: 90, 25: 480, 26: 180, 27: 60, 28: 150, 29: 90,
    30: 150, 31: 270,
}
TOTAL_NATURAL = sum(NATURAL_COUNTS.values())


def final_pred(row):
    exit_taken = int(row["exit_taken"])
    if exit_taken == 1:
        return int(row["pred1"])
    if exit_taken == 2:
        return int(row["pred2"])
    return int(row["pred3"])


def natural_weighted_miss_rate(sc_rows):
    by_class = {}
    for r in sc_rows:
        by_class.setdefault(int(r["label"]), []).append(r)

    weighted_sum = 0.0
    for cls, natural_n in NATURAL_COUNTS.items():
        rows = by_class.get(cls, [])
        if not rows:
            continue
        miss_n = sum(1 for r in rows if final_pred(r) != int(r["label"]))
        class_miss_rate = miss_n / len(rows)
        weight = natural_n / TOTAL_NATURAL
        weighted_sum += weight * class_miss_rate
    return weighted_sum


def main():
    policies = ["naive", "static", "adaptive"]
    print(f"{'policy':<10}{'raw_sample_miss':<18}{'natural_weighted_miss':<22}")
    for p in policies:
        with open(HERE / f"policy_results_{p}.csv", newline="") as f:
            rows = list(csv.DictReader(f))
        sc = [r for r in rows if int(r["is_safety_critical"]) == 1]
        raw_miss = sum(1 for r in sc if final_pred(r) != int(r["label"])) / len(sc)
        natural_miss = natural_weighted_miss_rate(sc)
        print(f"{p:<10}{raw_miss:<18.4f}{natural_miss:<22.4f}")


if __name__ == "__main__":
    main()
