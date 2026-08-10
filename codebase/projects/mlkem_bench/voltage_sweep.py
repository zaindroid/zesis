#!/usr/bin/env python3
"""Analyze the #5 voltage sweep: ML-KEM latency vs supply voltage.

For each capture (ppk_v33/27/24/22.csv), find the benchmark's active window
(the continuous current burst = the 100-handshake ML-KEM-1024 run) and
compute its wall-time duration. Compare across voltages.

Honest checks:
- Each trace must show the benchmark signature (baseline ~14mA, active burst)
- If a trace is flat / no active window -> the board browned out at that
  voltage (itself a data point).
"""
import numpy as np, csv, os
from scipy.ndimage import uniform_filter1d

DIR = "H:/z_thesis/energy resulkts"
VOLTS = [("ppk_v33.csv", 3.3), ("ppk_v27.csv", 2.7), ("ppk_v24.csv", 2.4), ("ppk_v22.csv", 2.2)]

def load(f):
    ts, cur = [], []
    with open(os.path.join(DIR, f)) as fp:
        r = csv.reader(fp); next(r)
        for row in r:
            if len(row) >= 2:
                ts.append(float(row[0])); cur.append(float(row[1]))
    return np.array(ts), np.array(cur)

def active_window(ts, cur):
    sm = uniform_filter1d(cur, 100)
    base = np.percentile(sm, 10)
    thr = base * 1.1
    act = sm > thr
    d = np.diff(act.astype(int))
    rises = np.where(d == 1)[0]; falls = np.where(d == -1)[0]
    if not len(rises) or not len(falls):
        return None, base
    s, e = rises[0], falls[-1]
    dur_s = (ts[e] - ts[s]) / 1000.0
    return dur_s, base

print(f"{'voltage':>8}{'active_s':>12}{'baseline_uA':>14}{'ok':>6}")
results = {}
for f, v in VOLTS:
    ts, cur = load(f)
    dur, base = active_window(ts, cur)
    if dur is not None:
        results[v] = dur
        print(f"{v:>5.1f}V{dur:>12.2f}{base:>14.0f}{'OK':>6}")
    else:
        print(f"{v:>5.1f}V{'NO ACTIVE WINDOW':>12}{base:>14.0f}{'BROWN-OUT?':>12}")

print("\n--- latency vs voltage ---")
if len(results) >= 2:
    base_v = max(results)  # highest voltage captured
    for v in sorted(results, reverse=True):
        r = results[v] / results[base_v]
        print(f"  {v:>5.1f}V: {results[v]:.2f}s | x{results[base_v]/results[v]:.3f} faster than {base_v}V | {r*100:.1f}% of {base_v}V time")
