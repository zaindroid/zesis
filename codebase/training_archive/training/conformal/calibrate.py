"""
Conformal risk calibration: picks the smallest confidence threshold tau_k
per exit, per target alpha, such that the finite-sample risk bound
(n*Rhat+1)/(n+1) <= alpha holds, where n = accepted safety-critical
calibration samples and Rhat = their empirical miss-rate (misclassification
rate among samples the exit was confident enough to accept).

Reads results/calibration_predictions_exit{1,2,3}.csv (from train/quantize.py)
and, if present, results/margin_derivation.json (from conformal/derive_margin.py,
the FROZEN four-way protocol). Writes results/conformal_tau_table.csv. Device
gets only the tau_k values.

MARGIN (frozen protocol, NOT tuned on test): derived by conformal/derive_margin.py
from the measured calibration -> margin_val distribution shift (delta_k at
tau=0, safety-critical miss-rate, per exit). Calibration uses alpha_cal =
alpha - delta_k per (exit, alpha). This replaces the old hardcoded
MARGIN_FACTOR=0.5, which was a first guess never re-derived on a clean
held-out slice. margin_val is a same-session holdout, so delta_k here is
within-session split noise; the cross-session shift against test.csv is
measured exactly once, at the end, by conformal/coverage_validate.py, and its
result stands regardless of PASS or FAIL. If margin_derivation.json is absent,
falls back to MARGIN_FACTOR=1.0 (no margin) rather than to any test-influenced
value.
"""
import csv
import json
from pathlib import Path

RESULTS = Path(__file__).parent.parent / "results"
EXITS = ["exit1", "exit2", "exit3"]
ALPHAS = [0.01, 0.05, 0.10]
MARGIN_FACTOR = 1.0  # fallback only; frozen protocol uses margin_derivation.json
TAU_GRID = [i / 1000 for i in range(1001)]  # 0.000, 0.001, ..., 1.000


def load_margin_derivation() -> dict | None:
    path = RESULTS / "margin_derivation.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def alpha_calibration_for(exit_name: str, alpha: float, margin: dict | None) -> float:
    """alpha_cal per (exit, alpha). If margin_derivation.json is present, use
    the derived per-exit delta_k: alpha_cal = alpha - delta_k (never below
    1e-6). Otherwise fall back to MARGIN_FACTOR (default 1.0, i.e. no margin)."""
    if margin is not None:
        delta = margin.get(exit_name, {}).get("delta_k", 0.0)
        return max(alpha - delta, 1e-6)
    return alpha * MARGIN_FACTOR


def margin_factor_for(exit_name: str, alpha: float, margin: dict | None) -> float:
    if margin is not None:
        alpha_cal = alpha_calibration_for(exit_name, alpha, margin)
        return alpha_cal / alpha
    return MARGIN_FACTOR


def find_tau(rows: list[dict], alpha: float) -> dict:
    sc = [r for r in rows if r["is_safety_critical"]]
    for tau in TAU_GRID:
        accepted = [r for r in sc if r["confidence"] >= tau]
        n = len(accepted)
        if n == 0:
            continue
        r_hat = sum(1 - r["correct"] for r in accepted) / n
        bound = (n * r_hat + 1) / (n + 1)
        if bound <= alpha:
            return {"tau": tau, "n": n, "r_hat": r_hat, "bound": bound, "certifiable": True}
    return {"tau": 1.0, "n": 0, "r_hat": float("nan"), "bound": 1.0, "certifiable": False}


def main() -> None:
    margin = load_margin_derivation()
    if margin is not None:
        print("using margin_derivation.json (frozen protocol): "
              "alpha_cal = alpha - delta_k per exit/alpha")
    else:
        print(f"WARNING: margin_derivation.json absent; using fallback "
              f"MARGIN_FACTOR={MARGIN_FACTOR} (no margin)")
    out_rows = []
    for exit_name in EXITS:
        with open(RESULTS / f"calibration_predictions_{exit_name}.csv", newline="") as f:
            rows = [{"confidence": float(r["confidence"]), "correct": int(r["correct"]),
                      "is_safety_critical": int(r["is_safety_critical"])} for r in csv.DictReader(f)]
        for alpha in ALPHAS:
            alpha_calibration = alpha_calibration_for(exit_name, alpha, margin)
            mf = margin_factor_for(exit_name, alpha, margin)
            result = find_tau(rows, alpha_calibration)
            print(f"{exit_name} alpha={alpha} (calibrated against {alpha_calibration:.4f}, "
                  f"margin_factor={mf:.4f}): tau={result['tau']:.3f} "
                  f"n={result['n']} r_hat={result['r_hat']:.4f} bound={result['bound']:.4f} "
                  f"certifiable={result['certifiable']}")
            out_rows.append({"exit": exit_name, "alpha": alpha,
                              "alpha_calibration": alpha_calibration,
                              "margin_factor": mf, **result})

    out_path = RESULTS / "conformal_tau_table.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
