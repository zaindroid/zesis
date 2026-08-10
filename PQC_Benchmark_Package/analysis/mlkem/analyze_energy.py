
import csv
from pathlib import Path

HERE = Path(__file__).parent
ENERGY_DIR = HERE.parent.parent / "results" / "mlkem" / "energy"
ASSUMED_VOLTAGE = 3.3  # V, nominal board supply rail
REPS = 100
CORE_CLOCK_HZ = 150_000_000

# Mean CPU cycles per operation and security level, from perf_memory_summary.csv
CYCLES = {
    "512":  {"keypair": 2978432, "encaps": 3503918, "decaps": 4342471},
    "768":  {"keypair": 4893951, "encaps": 5692464, "decaps": 6809160},
    "1024": {"keypair": 7644704, "encaps": 8582539, "decaps": 10008989},
}

CAPTURES = [
    ("512", "boardA", "mlkem512_boardA_raw.csv"),
    ("512", "boardB", "mlkem512_boardB_raw.csv"),
    ("768", "boardB", "mlkem768_boardB_raw.csv"),
    ("1024", "boardB", "mlkem1024_boardB_raw.csv"),
]


def load(path):
    ts, cur = [], []
    with open(path) as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            ts.append(float(row[0]) / 1000.0)  # ms -> s
            cur.append(float(row[1]) / 1e6)    # uA -> A
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


def analyze(variant, board, filename):
    ts, cur = load(ENERGY_DIR / filename)
    start, end, baseline, peak = find_active_window(ts, cur)
    t0, t1 = ts[start], ts[end - 1]
    duration = t1 - t0

    charge = 0.0
    for i in range(start, end - 1):
        dt = ts[i + 1] - ts[i]
        charge += 0.5 * (cur[i] + cur[i + 1]) * dt
    energy_J = charge * ASSUMED_VOLTAGE

    cycles = CYCLES[variant]
    total_cycles = sum(cycles.values())
    expected_duration = REPS * total_cycles / CORE_CLOCK_HZ

    per_handshake_uJ = energy_J / REPS * 1e6
    per_op_uJ = {op: per_handshake_uJ * c / total_cycles for op, c in cycles.items()}

    return {
        "variant": f"ML-KEM-{variant}", "board": board,
        "idle_baseline_mA": baseline * 1000, "peak_mA": peak * 1000,
        "active_window_s": duration, "expected_window_s": expected_duration,
        "total_charge_mC": charge * 1000, "total_energy_mJ": energy_J * 1000,
        "mean_active_current_mA": charge / duration * 1000,
        "per_handshake_uJ": per_handshake_uJ,
        "keypair_uJ": per_op_uJ["keypair"],
        "encaps_uJ": per_op_uJ["encaps"],
        "decaps_uJ": per_op_uJ["decaps"],
    }


def main():
    rows = []
    for variant, board, filename in CAPTURES:
        path = ENERGY_DIR / filename
        if not path.exists():
            print(f"skipping {filename} (not found)")
            continue
        r = analyze(variant, board, filename)
        rows.append(r)
        print(f"\n=== ML-KEM-{variant} ({board}) ===")
        print(f"idle baseline: {r['idle_baseline_mA']:.3f} mA, peak: {r['peak_mA']:.3f} mA")
        print(f"active window: {r['active_window_s']:.3f}s "
              f"(expected {r['expected_window_s']:.3f}s from timing measurements)")
        print(f"total energy (@ {ASSUMED_VOLTAGE}V assumed): {r['total_energy_mJ']:.4f} mJ")
        print(f"per-handshake: {r['per_handshake_uJ']:.2f} uJ  |  "
              f"keypair {r['keypair_uJ']:.2f} uJ, encaps {r['encaps_uJ']:.2f} uJ, "
              f"decaps {r['decaps_uJ']:.2f} uJ")

    if not rows:
        print("No capture files found -- nothing to summarize.")
        return

    out_path = HERE.parent.parent / "results" / "mlkem" / "energy_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
