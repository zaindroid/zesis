"""
Derive the conformal MARGIN on margin_val ONLY, from the measured
calibration -> margin_val distribution shift. FROZEN-PROTOCOL step 4.

The shift is measured as the difference in the tau=0 (accept-everything)
safety-critical miss-rate between calibration and margin_val, per exit:

    delta_k = max(0, margin_val_base_miss_k - calibration_base_miss_k)

Why this is the right quantity: split-conformal's finite-sample bound
(n*Rhat+1)/(n+1) <= alpha assumes calibration and the deployment
distribution are exchangeable. If the deployment distribution is shifted
(e.g. different photography session, as test.csv is relative to the
training-archive-derived splits), the achieved miss-rate at the calibrated
tau_k will be roughly Rhat + delta. Calibrating against a deflated
alpha_cal = alpha - delta (i.e. MARGIN_FACTOR = 1 - delta/alpha, per exit
and per alpha) buys back that measured shift.

margin_val is a same-session track-held-out slice of the training archive
(like calibration), so delta_k here measures WITHIN-session split noise --
NOT the full cross-session shift that test.csv will exhibit. That is
intentional and honest: it is the best estimate available WITHOUT touching
test.csv. If the single frozen test touch later fails a cell, that failure
is the true measured cross-session shift and is reported as-is.

This script NEVER touches test.csv. It reads:
  results/calibration_predictions_exit{1,2,3}.csv   (from train/quantize.py)
  results/margin_val_predictions_exit{1,2,3}.csv    (from conformal/predict_split.py)
It writes:
  results/margin_derivation.json  -- per-exit delta and per-alpha margin factors
  results/margin_derivation.log   -- human-readable derivation (appended)

Usage:
  python conformal/derive_margin.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results"
EXITS = ["exit1", "exit2", "exit3"]
ALPHAS = [0.01, 0.05, 0.10]


def base_safety_critical_miss(pred_path: Path) -> tuple[float, int]:
    """tau=0 (accept-everyone) safety-critical miss-rate and n."""
    with open(pred_path, newline="") as f:
        rows = list(csv.DictReader(f))
    sc = [r for r in rows if r["is_safety_critical"] == "1"]
    if not sc:
        return float("nan"), 0
    miss = sum(1 - int(r["correct"]) for r in sc) / len(sc)
    return miss, len(sc)


def main() -> None:
    derivation = {}
    log_lines = [
        "margin derivation (FROZEN protocol): calibration -> margin_val shift",
        "=" * 70,
        "method: delta_k = max(0, margin_val_base_miss_k - calibration_base_miss_k)",
        "        at tau=0 (accept-everything), safety-critical subset only.",
        "        alpha_cal(exit_k, alpha) = alpha - delta_k   (margin_factor = 1 - delta_k/alpha)",
        "",
        f"{'exit':>5} {'cal_miss':>9} {'cal_n':>6} {'margin_miss':>11} {'margin_n':>8} {'delta_k':>7}",
        "-" * 70,
    ]

    for exit_name in EXITS:
        cal_miss, cal_n = base_safety_critical_miss(RESULTS / f"calibration_predictions_{exit_name}.csv")
        mv_miss, mv_n = base_safety_critical_miss(RESULTS / f"margin_val_predictions_{exit_name}.csv")
        delta = max(0.0, mv_miss - cal_miss) if not (cal_miss != cal_miss or mv_miss != mv_miss) else 0.0

        margin_factors = {}
        for alpha in ALPHAS:
            alpha_cal = max(alpha - delta, 1e-6)
            margin_factors[str(alpha)] = {
                "alpha_calibration": alpha_cal,
                "margin_factor": alpha_cal / alpha,
            }
        derivation[exit_name] = {
            "calibration_base_miss": cal_miss,
            "calibration_n_sc": cal_n,
            "margin_val_base_miss": mv_miss,
            "margin_val_n_sc": mv_n,
            "delta_k": delta,
            "margin_factors": margin_factors,
        }
        log_lines.append(f"{exit_name:>5} {cal_miss:>9.4f} {cal_n:>6} {mv_miss:>11.4f} {mv_n:>8} {delta:>7.4f}")

    with open(RESULTS / "margin_derivation.json", "w", encoding="utf-8") as f:
        json.dump(derivation, f, indent=2)
    log_lines.append("")
    log_lines.append(json.dumps(derivation, indent=2))
    with open(RESULTS / "margin_derivation.log", "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")

    print("\n".join(log_lines))
    print(f"\nwrote {RESULTS / 'margin_derivation.json'}")


if __name__ == "__main__":
    main()
