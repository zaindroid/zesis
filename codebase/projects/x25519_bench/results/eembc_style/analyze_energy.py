"""
Energy analysis for the X25519 PPK2 current capture in results/energy/.

Same measurement point, instrument, and method as the ML-KEM energy
analysis (see mlkem_bench/results/eembc_style/analyze_energy.py and
BENCHMARK_METHODOLOGY.md for the full reasoning): PPK2 in Ampere Meter
mode across jumper J24, active window found via a smoothed-signal
threshold, charge integrated over the raw signal, energy = charge x an
assumed 3.3V supply.

X25519 has two operations, not three (keypair, shared_secret -- see
hello_world.c for why the DH paradigm doesn't have an encaps/decaps
split), so the per-operation energy split here is over 2 operations,
not 3.

Usage: python analyze_energy.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent
ENERGY_DIR = HERE / "energy"
ASSUMED_VOLTAGE = 3.3
REPS = 96  # see analyze_perf_memory.py's note on the repetition count
CORE_CLOCK_HZ = 150_000_000

CYCLES = {"keypair": 21225754.9, "shared_secret": 21225680.0}


def load(path):
    ts, cur = [], []
    with open(path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            ts.append(float(row[0]) / 1000.0)
            cur.append(float(row[1]) / 1e6)
    return ts, cur


def smooth(vals, win):
    out = [0.0] * len(vals)
    acc = 0.0
    for i, v in enumerate(vals):
        acc += v
        if i >= win:
            acc -= vals[i - win]
            out[i] = acc / win
        else:
            out[i] = acc / (i + 1)
    return out


def find_active_window(ts, cur):
    n = len(ts)
    sample_rate = (n - 1) / (ts[-1] - ts[0])
    win = max(1, int(sample_rate * 0.02))
    smoothed = smooth(cur, win)

    baseline = sorted(smoothed)[n // 20]
    peak = max(smoothed)
    thresh = baseline + 0.4 * (peak - baseline)

    best_start, best_end, run_start, best_len = None, None, None, 0
    for i, c in enumerate(smoothed):
        if c > thresh:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                if i - run_start > best_len:
                    best_len = i - run_start
                    best_start, best_end = run_start, i
                run_start = None
    if run_start is not None and n - run_start > best_len:
        best_start, best_end = run_start, n
    return best_start, best_end, baseline, peak


def main():
    path = ENERGY_DIR / "x25519_boardB_raw.csv"
    ts, cur = load(path)
    start, end, baseline, peak = find_active_window(ts, cur)
    t0, t1 = ts[start], ts[end - 1]
    duration = t1 - t0

    charge = 0.0
    for i in range(start, end - 1):
        dt = ts[i + 1] - ts[i]
        charge += 0.5 * (cur[i] + cur[i + 1]) * dt
    energy_J = charge * ASSUMED_VOLTAGE

    total_cycles = sum(CYCLES.values())
    expected_duration = REPS * total_cycles / CORE_CLOCK_HZ

    per_exchange_uJ = energy_J / REPS * 1e6
    per_op_uJ = {op: per_exchange_uJ * c / total_cycles for op, c in CYCLES.items()}

    print(f"idle baseline: {baseline*1000:.3f} mA, peak: {peak*1000:.3f} mA")
    print(f"active window: {duration:.3f}s (expected {expected_duration:.3f}s from timing measurements)")
    print(f"total energy (@ {ASSUMED_VOLTAGE}V assumed): {energy_J*1000:.4f} mJ")
    print(f"per-exchange: {per_exchange_uJ:.2f} uJ  |  "
          f"keypair {per_op_uJ['keypair']:.2f} uJ, shared_secret {per_op_uJ['shared_secret']:.2f} uJ")

    row = {
        "variant": "X25519", "board": "boardB",
        "idle_baseline_mA": baseline * 1000, "peak_mA": peak * 1000,
        "active_window_s": duration, "expected_window_s": expected_duration,
        "total_charge_mC": charge * 1000, "total_energy_mJ": energy_J * 1000,
        "mean_active_current_mA": charge / duration * 1000,
        "per_exchange_uJ": per_exchange_uJ,
        "keypair_uJ": per_op_uJ["keypair"],
        "shared_secret_uJ": per_op_uJ["shared_secret"],
    }
    out_path = HERE / "energy_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
