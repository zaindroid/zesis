"""
Removes the stratified-sample caveat attached to every on-device coverage
result so far: the validation sample capped each of the 27 safety-critical
classes at 40 images regardless of natural test-set frequency (60-750
images/class), over-representing rare/harder classes.

Every safety-critical class in the sample has natural count >= 40 (the
minimum, classes 0/19/27, is 60) -- so each class contributes EXACTLY 40
sampled images, making a clean Horvitz-Thompson-style reweighting
possible: each class's SAMPLE miss-rate is an unbiased estimate of that
class's TRUE miss-rate (40 random-ish draws from that class), and
weighting each class's estimate by its natural prevalence gives an
estimate representative of the natural class-frequency distribution --
directly comparable to the alpha targets and the PC-side full-test-set
numbers, without needing to re-run on all 8460 natural safety-critical
test images.

weighted_miss_rate = sum_c [ (natural_count_c / total_natural) *
                              (miss_count_c / sample_count_c) ]

Usage: python tools/hw_validate/compute_natural_weighted_coverage.py
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


def natural_weighted_miss_rate(rows, correct_key):
    """rows: safety-critical rows only, with a 'label' field and a
    correctness field named by correct_key (0/1 string or int)."""
    by_class = {}
    for r in rows:
        by_class.setdefault(int(r["label"]), []).append(r)

    weighted_sum = 0.0
    for cls, natural_n in NATURAL_COUNTS.items():
        sample_rows = by_class.get(cls, [])
        if not sample_rows:
            continue
        sample_n = len(sample_rows)
        miss_n = sum(1 - int(r[correct_key]) for r in sample_rows)
        class_miss_rate = miss_n / sample_n
        weight = natural_n / TOTAL_NATURAL
        weighted_sum += weight * class_miss_rate
    return weighted_sum


def main():
    with open(HERE / "hw_results.csv", newline="") as f:
        results = list(csv.DictReader(f))
    sc = [r for r in results if int(r["is_safety_critical"]) == 1]
    print(f"on-device sample: {len(results)} images ({len(sc)} safety-critical, "
          f"{len(set(int(r['label']) for r in sc))} classes)")

    with open(HERE / "conformal_tau_table.csv", newline="") as f:
        tau_table = list(csv.DictReader(f))

    print(f"\n{'exit':<7}{'alpha':<7}{'tau':<8}{'naive_sample':<14}{'naive_natural':<15}"
          f"{'diff':<8}")
    for row in tau_table:
        exit_name = row["exit"]
        alpha = float(row["alpha"])
        tau = float(row["tau"])
        idx = {"exit1": "1", "exit2": "2", "exit3": "3"}[exit_name]

        accepted = [r for r in sc if float(r[f"conf{idx}"]) >= tau]
        if not accepted:
            continue

        for r in accepted:
            r["_correct"] = str(int(int(r[f"pred{idx}"]) == int(r["label"])))

        sample_miss = sum(1 - int(r["_correct"]) for r in accepted) / len(accepted)
        natural_miss = natural_weighted_miss_rate(accepted, "_correct")

        print(f"{exit_name:<7}{alpha:<7}{tau:<8.3f}{sample_miss:<14.4f}"
              f"{natural_miss:<15.4f}{natural_miss - sample_miss:+<8.4f}")

    print("\n(naive_sample = simple mean over accepted stratified-sample images,")
    print(" same as previously reported; naive_natural = reweighted to the")
    print(" natural test-set class-frequency distribution -- compare directly")
    print(" against the target alpha and the PC full-test-set numbers)")

    print("\n--- pass/fail against target alpha, natural-frequency-weighted ---")
    n_pass = 0
    n_certifiable = 0
    for row in tau_table:
        exit_name = row["exit"]
        alpha = float(row["alpha"])
        tau = float(row["tau"])
        certifiable = row["certifiable"] == "True"
        idx = {"exit1": "1", "exit2": "2", "exit3": "3"}[exit_name]

        accepted = [r for r in sc if float(r[f"conf{idx}"]) >= tau]
        if not accepted or not certifiable:
            print(f"{exit_name} alpha={alpha}: not certifiable at calibration, skip")
            continue
        n_certifiable += 1

        for r in accepted:
            r["_correct"] = str(int(int(r[f"pred{idx}"]) == int(r["label"])))
        natural_miss = natural_weighted_miss_rate(accepted, "_correct")
        passes = natural_miss <= alpha
        n_pass += int(passes)
        print(f"{exit_name} alpha={alpha}: natural-weighted miss={natural_miss:.4f} "
              f"{'PASS' if passes else 'FAIL'}")

    print(f"\n{n_pass}/{n_certifiable} certifiable (exit, alpha) combinations pass "
          f"under natural-frequency reweighting (vs. the raw stratified-sample numbers).")


if __name__ == "__main__":
    main()
