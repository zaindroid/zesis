#!/usr/bin/env python3
"""Independent verification of the TTCA Stage-1 results and the Stage-3
Pareto audit inputs.

This script recomputes EVERY number in TTCA_STAGE1_REPORT.md and
STAGE3_PARETO_AUDIT.md from the raw artifacts only (softmax arrays, label
files, prediction CSVs). It does NOT import ttca_aci.py / pareto_audit.py —
the whole pipeline is re-implemented here so a bug in the original scripts
cannot be hidden by reusing their code.

Exit code 0 = all checks PASS; 1 = any check FAILS.
"""
import csv
import os
import sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESULTS = os.path.join(ROOT, "results", "ttca")
ALPHA0, GAMMA, WINDOW = 0.05, 0.01, 50
TOL = 0.005                      # allowed deviation (rolling means)

failures = []


def check(name, got, expected, tol=TOL):
    ok = abs(got - expected) <= tol
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got {got:.4f}, "
          f"expected {expected:.4f}")
    if not ok:
        failures.append(name)


def tau_at(csm, clab, k1, alpha):
    nc = 1.0 - csm[np.arange(len(clab)), k1 - 1, clab]
    q = int(np.ceil((len(nc) + 1) * (1.0 - alpha)))
    q = min(max(q, 1), len(nc))
    return float(np.sort(nc)[q - 1])


def rolling(x, w):
    out = np.full(len(x), np.nan)
    cs = np.cumsum(x)
    for i in range(w - 1, len(x)):
        out[i] = (cs[i] - (cs[i - w] if i >= w else 0)) / w
    return out


def main():
    print("=" * 72)
    print("Independent verification of TTCA Stage-1 + Stage-3 audit inputs")
    print("=" * 72)

    # ---------- A. raw data integrity ----------
    print("\nA. raw data integrity")
    sm = np.load(f"{RESULTS}/aci_softmax.npy")           # (1000,3,43)
    csm = np.load(f"{RESULTS}/calib_softmax.npy")        # (5850,3,43)
    clab = np.load(f"{RESULTS}/calib_labels.npy")
    labs = np.array([int(r["label"]) for r in
                     csv.DictReader(open(f"{RESULTS}/aci_seq_1000.csv"))])
    assert sm.shape == (1000, 3, 43) and csm.shape[1:] == (3, 43)
    dev = float(np.abs(sm.sum(axis=2) - 1.0).max())
    print(f"  softmax sum-to-1 max deviation: {dev:.2e} "
          f"(must be < 1e-5) {'OK' if dev < 1e-5 else 'FAIL'}")
    if dev >= 1e-5:
        failures.append("softmax validity")
    if len(labs) != 1000:
        failures.append("label count"); print("  FAIL labels != 1000")

    # ---------- B. remote-run facts (from the model executions) ----------
    print("\nB. model facts (from the actual INT8 executions)")
    acc_clean = (sm[:300, 2].argmax(axis=1) == labs[:300]).mean()
    acc_shift = (sm[300:, 2].argmax(axis=1) == labs[300:]).mean()
    check("exit3 clean accuracy (remote log 0.917)", acc_clean, 0.917)
    check("exit3 shifted accuracy (remote log 0.359)", acc_shift, 0.359)

    # ---------- C. tau / slope recomputation ----------
    print("\nC. tau(0.05) and slope d(tau)/d(alpha) per exit")
    taus = {k: tau_at(csm, clab, k, ALPHA0) for k in (1, 2, 3)}
    slopes = {k: (tau_at(csm, clab, k, ALPHA0 + 0.02) -
                  tau_at(csm, clab, k, ALPHA0 - 0.02)) / 0.04 for k in (1, 2, 3)}
    for k in (1, 2, 3):
        print(f"  exit{k}: tau={taus[k]:.4f} slope={slopes[k]:.3f}")
    check("exit1 tau", taus[1], 0.9773)
    check("exit2 tau", taus[2], 0.8827)
    check("exit3 tau", taus[3], 0.8694)
    check("exit1 slope", slopes[1], -0.705)
    check("exit2 slope", slopes[2], -8.351)

    # ---------- D. static pipeline ----------
    print("\nD. static conformal (rolling coverage, window 50)")
    n = len(labs)
    cov_s = np.zeros(n, dtype=int)
    for t in range(n):
        for k in (1, 2, 3):
            C = np.where(1.0 - sm[t, k - 1] <= taus[k])[0]
            if len(C) > 0:
                cov_s[t] = int(labs[t] in C)
                break
        else:
            cov_s[t] = int(labs[t] in np.where(1.0 - sm[t, 2] <= taus[3])[0])
    rc_s = rolling(cov_s, WINDOW)
    check("static clean 0-299", np.nanmean(rc_s[0:300]), 0.958)
    check("static shift 300-699", np.nanmean(rc_s[300:700]), 0.486)
    check("static post 700-999", np.nanmean(rc_s[700:1000]), 0.439)
    check("static ALL", np.nanmean(rc_s), 0.596)

    # ---------- E. ACI pipeline ----------
    print("\nE. ACI (TTCA) (rolling coverage, window 50)")
    alpha = {1: ALPHA0, 2: ALPHA0, 3: ALPHA0}
    cov_a = np.zeros(n, dtype=int)
    ex_a = np.zeros(n, dtype=int)
    for t in range(n):
        sets = {}
        for k in (1, 2, 3):
            tau = float(np.clip(taus[k] + slopes[k] * (alpha[k] - ALPHA0),
                                1e-6, 1.0))
            sets[k] = np.where(1.0 - sm[t, k - 1] <= tau)[0]
        chosen = next((k for k in (1, 2, 3)
                       if alpha[k] <= ALPHA0 + 2.0 * GAMMA), 3)
        ex_a[t] = chosen
        cov_a[t] = int(labs[t] in sets[chosen])
        for k in (1, 2, 3):
            err = int(labs[t] not in sets[k])
            alpha[k] = float(np.clip(alpha[k] + GAMMA * (ALPHA0 - err),
                                     0.001, 0.99))
    rc_a = rolling(cov_a, WINDOW)
    check("ACI clean 0-299", np.nanmean(rc_a[0:300]), 0.958)
    check("ACI shift 300-699", np.nanmean(rc_a[300:700]), 0.939)
    check("ACI post 700-999", np.nanmean(rc_a[700:1000]), 0.949)
    check("ACI ALL", np.nanmean(rc_a), 0.947)
    # exit distributions (report: clean [241,59,0], shift [399,1,0])
    d_clean = np.bincount(ex_a[:300], minlength=4)[1:]
    d_shift = np.bincount(ex_a[300:700], minlength=4)[1:]
    print(f"  exit dist clean: {d_clean} (report [241 59 0])")
    print(f"  exit dist shift: {d_shift} (report [399 1 0])")
    check("exit dist clean[0]", d_clean[0], 241)
    check("exit dist shift[0]", d_shift[0], 399)

    # ---------- F. Pareto audit inputs ----------
    print("\nF. Stage-3 Pareto audit inputs (per-exit accuracy, calibration)")
    for k in (1, 2, 3):
        rows = list(csv.DictReader(open(os.path.join(
            ROOT, "results", f"calibration_predictions_exit{k}.csv"))))
        acc = sum(int(r["correct"]) for r in rows) / len(rows)
        print(f"  exit{k}: acc {acc:.4f}")
    check("exit1 acc", sum(int(r["correct"]) for r in
          list(csv.DictReader(open(os.path.join(
              ROOT, "results", "calibration_predictions_exit1.csv")))))
          / 5850, 0.7349)
    check("exit2 acc", sum(int(r["correct"]) for r in
          list(csv.DictReader(open(os.path.join(
              ROOT, "results", "calibration_predictions_exit2.csv")))))
          / 5850, 0.9215)
    check("exit3 acc", sum(int(r["correct"]) for r in
          list(csv.DictReader(open(os.path.join(
              ROOT, "results", "calibration_predictions_exit3.csv")))))
          / 5850, 0.9308)

    # ---------- verdict ----------
    print("\n" + "=" * 72)
    if failures:
        print(f"VERDICT: {len(failures)} CHECK(S) FAILED")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("VERDICT: ALL CHECKS PASS — the Stage-1 and Stage-3 numbers are "
          "reproduced exactly from the raw artifacts.")
    print("=" * 72)


if __name__ == "__main__":
    main()
