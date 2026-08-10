"""
Contention-cost predictor: learns expected crypto-step latency per
operation type (keypair/encap/decap) from telemetry collected during the
naive policy run (123 crypto steps, rotating keypair->encap->decap), and
validates it on a held-out split.

Uses the naive run specifically because it has zero policy-side
interference with crypto timing (static/adaptive's crypto scheduling is
identical, but naive is the cleanest reference).

Usage: python tools/predict_crypto_cost.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent
OP_NAMES = ["keypair", "encap", "decap"]


def main():
    with open(HERE / "policy_results_naive.csv", newline="") as f:
        rows = list(csv.DictReader(f))

    # Crypto steps occur every 10 frames (frame index 0, 10, 20, ...),
    # rotating keypair -> encap -> decap. Extract (op_type, cost_us) pairs
    # in the order they occurred.
    steps = []
    step_idx = 0
    for i, r in enumerate(rows):
        crypto_us = int(r["crypto_us"])
        if crypto_us > 0:
            op = OP_NAMES[step_idx % 3]
            steps.append((op, crypto_us))
            step_idx += 1

    print(f"total crypto steps observed: {len(steps)}")

    split = len(steps) // 2
    train, test = steps[:split], steps[split:]
    print(f"train: {len(train)} steps, test: {len(test)} steps\n")

    # Per-type predictor: mean of training observations.
    predictor = {}
    for op in OP_NAMES:
        vals = [c for o, c in train if o == op]
        if vals:
            predictor[op] = sum(vals) / len(vals)

    print(f"{'op':<10}{'train_mean_us':<16}{'train_std_us':<15}{'n_train':<9}{'n_test':<8}")
    for op in OP_NAMES:
        train_vals = [c for o, c in train if o == op]
        if not train_vals:
            continue
        mean = sum(train_vals) / len(train_vals)
        var = sum((v - mean) ** 2 for v in train_vals) / len(train_vals)
        std = var ** 0.5
        n_test = sum(1 for o, c in test if o == op)
        print(f"{op:<10}{mean:<16.1f}{std:<15.2f}{len(train_vals):<9}{n_test:<8}")

    print(f"\n{'op':<10}{'test_mean_us':<15}{'predicted_us':<15}{'abs_err_us':<13}{'rel_err_%':<10}")
    for op in OP_NAMES:
        test_vals = [c for o, c in test if o == op]
        if not test_vals or op not in predictor:
            continue
        test_mean = sum(test_vals) / len(test_vals)
        pred = predictor[op]
        abs_err = abs(pred - test_mean)
        rel_err = abs_err / test_mean * 100
        print(f"{op:<10}{test_mean:<15.1f}{pred:<15.1f}{abs_err:<13.1f}{rel_err:<10.3f}")

    # Per-step prediction error (using the SAME predictor, applied to each
    # individual held-out step, not just the type-level mean).
    print("\nper-step prediction error on held-out test steps:")
    errs = []
    for op, actual in test:
        if op not in predictor:
            continue
        pred = predictor[op]
        rel_err = abs(pred - actual) / actual * 100
        errs.append(rel_err)
    if errs:
        mean_err = sum(errs) / len(errs)
        max_err = max(errs)
        print(f"  mean per-step relative error: {mean_err:.3f}%")
        print(f"  max per-step relative error: {max_err:.3f}%")
        print(f"  n={len(errs)} held-out steps")


if __name__ == "__main__":
    main()
