#!/usr/bin/env python3
"""Analyze a PPK2 Ampere-Meter capture of the SecureMark-TLS run on the
FRDM-MCXN947. Computes total energy and per-phase energy of the ~2-minute
benchmark window (trapz integration, assumed 3.3 V, active-window detection
via smoothed median/percentile thresholding — same methodology as the ML-KEM
eembc_style energy analysis)."""
import csv, sys, os
import numpy as np

VOLTAGE = 3.3          # assumed rail voltage (P3V3_MCU)
FS = 10000.0           # PPK2 sample rate (10 kHz)

def parse_ppk2_csv(path):
    """nRF PPK2 exported CSVs have a 'time (s)' and 'current (mA)' column
    (or 'value (mA)' / sample index). Tolerate a few layouts."""
    rows_t = []; rows_i = []
    with open(path, newline="") as f:
        rd = csv.reader(f)
        header = next(rd, None)
        if header is None:
            raise SystemExit("empty CSV")
        h = [h.strip().lower() for h in header]
        ti = next((k for k, x in enumerate(h) if "time" in x or "timestamp" in x), 0)
        ii = next((k for k, x in enumerate(h) if "current" in x), None)
        if ii is None:
            ii = next((k for k, x in enumerate(h) if "value" in x or "amp" in x), 1)
        tscale = 1000.0 if any("(ms)" in x for x in h) else 1.0
        iscale = 1000.0 if any("ua" in x for x in h) else 1.0
        for row in rd:
            if len(row) <= max(ti, ii):
                continue
            try:
                t = float(row[ti]) / tscale; cur = float(row[ii]) / iscale
            except ValueError:
                continue
            rows_t.append(t); rows_i.append(cur)
    return np.array(rows_t), np.array(rows_i)

def idle_baseline(i):
    """Idle = the lowest substantial current level (the board idles before
    and/or after the run). Find it as the lowest peak of the current
    histogram (robust even when the active window dominates the trace)."""
    lo, hi = np.percentile(i, 0.5), np.percentile(i, 99.5)
    hist, edges = np.histogram(np.clip(i, lo, hi), bins=200)
    peaks = []
    for b in range(1, len(hist) - 1):
        if hist[b] > hist[b - 1] and hist[b] >= hist[b + 1] and hist[b] > len(i) * 0.003:
            peaks.append((b, hist[b]))
    if peaks:
        b, _ = min(peaks, key=lambda p: edges[p[0]])
        return float((edges[b] + edges[b + 1]) / 2)
    return float(np.percentile(i, 10))

def active_window(t, i, min_run_s=60.0):
    """Find the main active window: the contiguous region above the idle
    baseline, lasting at least min_run_s. Returns (i0, i1) sample indices."""
    base = idle_baseline(i)
    thr = base + 0.30 * max(np.percentile(i, 99.9) - base, 1.0)  # 30% of the swing
    above = i > thr
    # find longest contiguous run of 'above'
    best = (0, 0); cur_start = None
    for idx, a in enumerate(above):
        if a and cur_start is None:
            cur_start = idx
        elif not a and cur_start is not None:
            if idx - cur_start > best[1] - best[0]:
                best = (cur_start, idx)
            cur_start = None
    if cur_start is not None and len(above) - cur_start > best[1] - best[0]:
        best = (cur_start, len(above))
    i0, i1 = best
    dur = (t[i1 - 1] - t[i0]) if i1 > i0 else 0
    if dur < min_run_s:
        print(f"  WARNING: active window only {dur:.0f} s (expected ~120 s)")
    return i0, i1, base

def main():
    if len(sys.argv) < 2:
        print("usage: analyze_securemark_energy.py <ppk2.csv>")
        return
    path = sys.argv[1]
    print(f"Analyzing {os.path.basename(path)}")
    t, i = parse_ppk2_csv(path)
    dt = np.diff(t)
    fs = 1.0 / np.median(dt) if dt.size else 0
    print(f"  samples: {len(t)} | median dt: {1.0/fs*1e3:.2f} ms ({fs:.0f} Hz)" if fs else "  samples: 0")
    if len(t) < 10:
        print("  too few samples"); return

    i0, i1, base = active_window(t, i)
    dur_s = t[i1 - 1] - t[i0]
    seg_i = i[i0:i1] - base                 # active current above idle
    seg_t = t[i0:i1]
    charge_mC = np.trapz(seg_i, seg_t)                # mA*s = mC
    energy_mJ = VOLTAGE * charge_mC                   # 3.3 V * mC = mJ (incremental)
    mean_ma = np.mean(seg_i)
    # full-current energy of the whole window (incl. idle baseline)
    full_mC = np.trapz(i[i0:i1], seg_t)
    full_mJ = VOLTAGE * full_mC
    power_mw = VOLTAGE * mean_ma                      # active power above idle
    print(f"  idle baseline: {base:.2f} mA")
    print(f"  active window: {t[i0]:.1f}s -> {t[i1-1]:.1f}s ({dur_s:.1f} s)")
    print(f"  mean active current (above idle): {mean_ma:.2f} mA")
    print(f"  active power (above idle): {power_mw:.2f} mW")
    print(f"  charge (incremental): {charge_mC:.1f} mC")
    print(f"  INCREMENTAL ENERGY (3.3 V): {energy_mJ:.0f} mJ")
    print(f"  FULL-CURRENT ENERGY (incl. idle {base:.2f} mA): {full_mJ:.0f} mJ")
    # ULPMark-style: energy per TLS-handshake ECC phase at the measured power.
    # Phase durations are board-specific (the ESP32 classical ECC is much slower).
    import sys as _sys
    board = "esp" if "esp32" in _sys.argv[0].lower() or any("esp32" in a for a in _sys.argv) else "mcx"
    durations = {
        "mcx": (("classical ECC", 166.1), ("PQC 768+44", 108.6), ("PQC 768+65", 164.2), ("PQC 768+87", 229.1)),
        "esp": (("classical ECC", 495.2), ("PQC 768+44", 88.8),  ("PQC 768+65", 134.0), ("PQC 768+87", 187.1)),
    }[board]
    for name, dur_ms in durations:
        print(f"  ~{name} phase ({dur_ms:.1f} ms): {power_mw*dur_ms/1000:.2f} mJ (at active power)")

    # per-component phases are visible as current plateaus; report the window
    # statistics rather than over-fitting. The ECC components dominate the
    # energy (they are >90% of the run time).
    print(f"  peak active current: {seg_i.max():.2f} mA")

if __name__ == "__main__":
    main()
