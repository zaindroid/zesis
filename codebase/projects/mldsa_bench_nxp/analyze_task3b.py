#!/usr/bin/env python3
"""Task 3B: ML-DSA signing latency distribution over the raw capture.

Parses a mldsa_bench_nxp capture (SIGN rows are cycles,retries,fail between
SIGN_BEGIN and SIGN_END) and reports p50/p90/p95/p99/max plus the 10 Hz
telemetry budget check. 150 MHz clock.

Usage: python analyze_task3b.py <raw.txt> <label>
"""
import csv
import sys
import numpy as np

CPU_HZ = 150_000_000
FRAME_HZ = 10.0           # D2I telemetry frame rate required by Task 3B

raw, label = sys.argv[1], sys.argv[2]
rows, in_sign = [], False
with open(raw, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.strip()
        if line == "SIGN_BEGIN":
            in_sign = True
            continue
        if line == "SIGN_END":
            break
        if in_sign and line and line[0].isdigit():
            parts = line.split(",")
            rows.append((int(parts[0]), int(parts[1]), int(parts[2])))

cyc = np.array([r[0] for r in rows], dtype=float)
retry = np.array([r[1] for r in rows])
fail = np.array([r[2] for r in rows])
ms = cyc / CPU_HZ * 1000.0

if len(ms)==0:
    print(f"{label}: no SIGN rows parsed (capture incomplete?)"); sys.exit(2)
print(f"{label}: n={len(ms)}  fails={int(fail.sum())}  max_retries={int(retry.max())}")
for name, v in [("min", ms.min()), ("p50", np.percentile(ms, 50)),
                ("p90", np.percentile(ms, 90)), ("p95", np.percentile(ms, 95)),
                ("p99", np.percentile(ms, 99)), ("max", ms.max())]:
    print(f"  {name:>4}: {v:8.2f} ms")
budget = 1000.0 / FRAME_HZ
print(f"  worst/median: {ms.max()/np.median(ms):.1f}x")
print(f"  10 Hz budget: {budget:.0f} ms per frame -> median fits: "
      f"{np.median(ms) <= budget}, worst fits: {ms.max() <= budget}")
print(f"  telemetry throughput: {1000.0/ms.mean():.1f} frames/s (mean-based)")

out = raw.replace(".txt", "_dist.csv")
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ms", "cycles", "retries", "fail"])
    for i in range(len(ms)):
        w.writerow([f"{ms[i]:.4f}", int(cyc[i]), int(retry[i]), int(fail[i])])
print(f"  wrote {out}")
