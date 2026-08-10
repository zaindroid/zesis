#!/usr/bin/env python3
"""Experiment #1: Conformal latency certificates for ML-DSA signing.

Turns the fat-tailed ML-DSA signing latency into a *certified* bound:
    P(sign_latency <= tau) >= 1 - alpha
using split-conformal prediction (distribution-free, finite-sample valid,
no Gaussian/tail assumption). Same conformal machinery as the perception
risk certification — now applied to crypto latency.

Data: NXP bare-metal (150MHz) + ESP32 (240MHz) + Zephyr, 2000 samples/level,
fail=0 everywhere. tau computed as the ceil((n+1)(1-alpha))-th order
statistic with the finite-sample correction.

Also computes the deadline-budget story: for a 33ms frame deadline, how
much budget must the crypto reserve at each alpha?
"""
import numpy as np, os, csv, json

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "projects", "mldsa_bench_nxp", "results", "conformal_latency")
os.makedirs(OUT, exist_ok=True)

LEVELS = ["44", "65", "87"]
ALPHAS = [0.01, 0.05, 0.10]

def load_nxp(level):
    p = os.path.join(ROOT, "projects", "mldsa_bench_nxp", "results", f"mldsa{level}_sign_raw.csv")
    cycles = []
    with open(p) as f:
        r = csv.reader(f); next(r)
        for row in r:
            if len(row) >= 1:
                cycles.append(int(row[0]))
    return np.array(cycles, dtype=np.float64) / 150.0  # cycles -> us @150MHz

def load_esp32(level):
    p = os.path.join(ROOT, "projects", "gtsrb_multiexit_esp32s3", "results", f"mldsa{level}_sign_raw.csv")
    cycles = []
    with open(p) as f:
        r = csv.reader(f); next(r)
        for row in r:
            if len(row) >= 1:
                cycles.append(int(row[0]))
    return np.array(cycles, dtype=np.float64) / 240.0  # cycles -> us @240MHz

def conformal_tau(x, alpha):
    """Split-conformal quantile: P(X <= tau) >= 1-alpha, finite-sample valid.
    tau = the k-th order statistic, k = ceil((n+1)(1-alpha))."""
    n = len(x)
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    k = min(k, n)
    xs = np.sort(x)
    return xs[k - 1], k

def report(name, x):
    n = len(x)
    med, wc = np.median(x), x.max()
    print(f"\n=== {name} (n={n}, median={med:.1f}us, worst={wc:.1f}us, w/m={wc/med:.2f}x) ===")
    for a in ALPHAS:
        tau, k = conformal_tau(x, a)
        print(f"  alpha={a:>4}: tau={tau:9.1f} us ({tau/1000:.2f} ms) | k={k}/{n} | "
              f"empirical exceed={np.mean(x > tau)*100:.2f}%")

# NXP (primary)
print("=" * 60)
print("NXP FRDM-MCXN947 @150MHz (bare-metal)")
print("=" * 60)
nxp = {}
for lv in LEVELS:
    x = load_nxp(lv)
    nxp[lv] = x
    report(f"ML-DSA-{lv}", x)

# ESP32
print("\n" + "=" * 60)
print("ESP32-S3 @240MHz (bare-metal)")
print("=" * 60)
esp = {}
for lv in LEVELS:
    x = load_esp32(lv)
    esp[lv] = x
    report(f"ML-DSA-{lv}", x)

# ---- deadline budget story: 33ms frame, crypto must fit ---- 
print("\n" + "=" * 60)
print("DEADLINE BUDGET (33ms frame = 33000us)")
print("=" * 60)
DEADLINE_US = 33000.0
for lv in LEVELS:
    x = nxp[lv]
    print(f"\nML-DSA-{lv} @150MHz:")
    for a in ALPHAS:
        tau, _ = conformal_tau(x, a)
        frac = tau / DEADLINE_US
        print(f"  alpha={a:>4}: crypto tau={tau:8.1f}us = {frac*100:5.1f}% of 33ms deadline "
              f"| remaining for perception: {(DEADLINE_US-tau):8.1f}us")

# ---- save ----
out = {"platform": "NXP-150MHz", "method": "split-conformal quantile",
       "note": "tau = ceil((n+1)(1-alpha))-th order statistic; P(latency<=tau)>=1-alpha finite-sample",
       "levels": {}}
for lv in LEVELS:
    out["levels"][lv] = {
        "n": int(len(nxp[lv])),
        "median_us": float(np.median(nxp[lv])),
        "worst_us": float(nxp[lv].max()),
        "worst_over_median": float(nxp[lv].max() / np.median(nxp[lv])),
        "tau_us": {str(a): float(conformal_tau(nxp[lv], a)[0]) for a in ALPHAS},
    }
with open(os.path.join(OUT, "conformal_latency_certificates.json"), "w") as f:
    json.dump(out, f, indent=2)
print(f"\nsaved -> {OUT}/conformal_latency_certificates.json")
