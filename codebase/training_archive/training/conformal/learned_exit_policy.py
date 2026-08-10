#!/usr/bin/env python3
"""Train a LEARNED exit policy for the certified-anytime multi-exit classifier.

Clean protocol: train on calibration + margin_val ONLY. Test is quarantined
(touched exactly once, at the end, by this script's final evaluation).

Policy form: a per-exit decision rule on the full confidence vector.
  - Features per frame: conf1 (exit1 confidence), conf2, conf3.
  - The policy chooses the SHALLOWEST exit k such that the estimated
    safety-critical miss risk of stopping at exit k is <= alpha, else
    continues to exit 3 (always available as the final certifiable exit).
  - Risk estimates are learned as isotonic/calibrated curves:
    risk_k(c) = P(safety-critical AND wrong | conf_k = c)
    trained on calibration data, smoothed, then thresholded.

This is the "AI angle": instead of hand-tuned tau thresholds (static) or
hand-tuned tier shifts (adaptive), the exit decision is a learned
function of the full confidence vector and the risk curves are learned
from data — then validated on margin_val, then evaluated once on test.

Outputs (results/learned_policy/):
  - risk_curves.json       : learned risk_k(c) curves + thresholds
  - margin_val_eval.csv    : policy decisions on margin_val
  - test_eval.csv          : policy decisions on test (final, once)
  - learned_policy_report.md
"""
import csv, json, os, sys
import numpy as np

ALPHA = 0.05
RESULTS = os.path.join(os.path.dirname(__file__), "..",
                       "results", "learned_policy")
RESULTS = os.path.abspath(RESULTS)
os.makedirs(RESULTS, exist_ok=True)

def load_split(name, ex):
    p = os.path.join(os.path.dirname(__file__), "..",
                     "results", f"{name}_predictions_exit{ex}.csv")
    p = os.path.abspath(p)
    rows = []
    with open(p) as f:
        for r in csv.DictReader(f):
            rows.append({
                "conf": float(r["confidence"]),
                "correct": int(r["correct"]),
                "sc": int(r["is_safety_critical"]),
            })
    return rows

def risk_curve(rows, nbins=20, min_bin=20):
    """Learned risk_k(c) = P(SC AND wrong | conf bin), isotonic-decreasing."""
    confs = np.array([r["conf"] for r in rows])
    scwrong = np.array([1 if (r["sc"] and not r["correct"]) else 0 for r in rows])
    edges = np.linspace(0.0, 1.0, nbins + 1)
    bin_risk, bin_n, bin_c = [], [], []
    for i in range(nbins):
        m = (confs >= edges[i]) & (confs < edges[i + 1])
        n = int(m.sum())
        if n >= min_bin:
            bin_risk.append(float(scwrong[m].mean()))
            bin_n.append(float(n))
            bin_c.append(float(edges[i + 1]))
    if not bin_risk:
        return {"edges": [1.0], "risk": [0.0]}
    # PAVA decreasing (pool adjacent violators where risk[i] < risk[i+1] on reversed)
    r = np.array(bin_risk, dtype=float)[::-1]
    w = np.array(bin_n, dtype=float)[::-1]
    out_r, out_w = list(r), list(w)
    i = 0
    while i < len(out_r) - 1:
        if out_r[i] > out_r[i + 1]:
            tw = out_w[i] + out_w[i + 1]
            merged = (out_r[i] * out_w[i] + out_r[i + 1] * out_w[i + 1]) / tw
            out_r[i] = merged; out_w[i] = tw
            del out_r[i + 1]; del out_w[i + 1]
            if i > 0: i -= 1
        else:
            i += 1
    mono = np.array(out_r[::-1])
    edges_out = np.array(bin_c, dtype=float)
    return {"edges": edges_out.tolist(), "risk": mono.tolist()}

def risk_at(curve, c):
    """Interpolate risk at confidence c from the learned curve."""
    xs, ys = np.array(curve["edges"]), np.array(curve["risk"])
    if c >= xs[-1]:
        return float(ys[-1])
    i = np.searchsorted(xs, c, side="right")
    if i == 0:
        return float(ys[0])
    return float(ys[i - 1])

def policy_decision(conf1, conf2, conf3, curves, alpha):
    """Choose shallowest exit whose learned risk <= alpha."""
    if risk_at(curves[1], conf1) <= alpha:
        return 1
    if risk_at(curves[2], conf2) <= alpha:
        return 2
    return 3  # exit3 always available (its own curve may exceed alpha, but it's final)

def main():
    cal = {ex: load_split("calibration", ex) for ex in (1, 2, 3)}
    val = {ex: load_split("margin_val", ex) for ex in (1, 2, 3)}
    test = {ex: load_split("test", ex) for ex in (1, 2, 3)}

    # Train risk curves on calibration
    curves = {ex: risk_curve(cal[ex]) for ex in (1, 2, 3)}
    with open(os.path.join(RESULTS, "risk_curves.json"), "w") as f:
        json.dump({str(k): v for k, v in curves.items()}, f, indent=2)

    # Evaluate on margin_val (validation)
    val_decisions = []
    for i in range(len(val[1])):
        d = policy_decision(val[1][i]["conf"], val[2][i]["conf"], val[3][i]["conf"],
                            curves, ALPHA)
        sc = val[1][i]["sc"]
        correct_at_exit = val[d][i]["correct"]
        val_decisions.append({"idx": i, "exit": d, "sc": sc, "correct": correct_at_exit,
                              "conf1": val[1][i]["conf"], "conf2": val[2][i]["conf"]})
    with open(os.path.join(RESULTS, "margin_val_eval.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "exit", "sc", "correct", "conf1", "conf2"])
        w.writeheader(); w.writerows(val_decisions)

    # Margin-val summary
    exits = {1: 0, 2: 0, 3: 0}
    sc_miss = 0; sc_total = 0
    for d in val_decisions:
        exits[d["exit"]] += 1
        if d["sc"]:
            sc_total += 1
            if not d["correct"]:
                sc_miss += 1
    sc_miss_rate = sc_miss / sc_total if sc_total else 0
    n_early = (exits[1] + exits[2]) / len(val_decisions)

    # Evaluate on test (single, final, clean touch)
    test_decisions = []
    for i in range(len(test[1])):
        d = policy_decision(test[1][i]["conf"], test[2][i]["conf"], test[3][i]["conf"],
                            curves, ALPHA)
        sc = test[1][i]["sc"]
        correct_at_exit = test[d][i]["correct"]
        test_decisions.append({"idx": i, "exit": d, "sc": sc, "correct": correct_at_exit,
                               "conf1": test[1][i]["conf"], "conf2": test[2][i]["conf"]})
    with open(os.path.join(RESULTS, "test_eval.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "exit", "sc", "correct", "conf1", "conf2"])
        w.writeheader(); w.writerows(test_decisions)

    t_exits = {1: 0, 2: 0, 3: 0}; t_sc_miss = 0; t_sc_total = 0
    for d in test_decisions:
        t_exits[d["exit"]] += 1
        if d["sc"]:
            t_sc_total += 1
            if not d["correct"]:
                t_sc_miss += 1
    t_sc_miss_rate = t_sc_miss / t_sc_total if t_sc_total else 0
    t_n_early = (t_exits[1] + t_exits[2]) / len(test_decisions)

    # Report
    rep = f"""# Learned Exit Policy — validation (margin_val) + single test evaluation

Alpha target: {ALPHA}
Training data: calibration (5,850) — learned risk curves per exit
Validation: margin_val (3,990); Test: quarantined 12,630 (touched once)

## margin_val (validation)
- exit distribution: {exits}
- early-exit fraction (exit1+exit2): {n_early:.3f}
- SC miss-rate: {sc_miss}/{sc_total} = {sc_miss_rate:.4f}  (target <= {ALPHA})
- SC miss-rate on FULL (accepted+rejected): see below

## test (single evaluation)
- exit distribution: {t_exits}
- early-exit fraction: {t_n_early:.3f}
- SC miss-rate: {t_sc_miss}/{t_sc_total} = {t_sc_miss_rate:.4f}  (target <= {ALPHA})

## Learned risk curves (edges, risk)
{json.dumps({str(k): v for k, v in curves.items()}, indent=1)}
"""
    with open(os.path.join(RESULTS, "learned_policy_report.md"), "w") as f:
        f.write(rep)
    print(f"margin_val: exits={exits} early={n_early:.3f} SCmiss={sc_miss_rate:.4f}")
    print(f"test      : exits={t_exits} early={t_n_early:.3f} SCmiss={t_sc_miss_rate:.4f}")
    print(f"written to {RESULTS}")

if __name__ == "__main__":
    main()
