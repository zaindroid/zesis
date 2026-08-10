"""
Energy analysis for the ML-KEM PPK2 captures in energy/*_raw.csv.

Measurement point: J24 ("IDD_MCU", FRDM-MCXN947 schematic page 6 / "USB &
PWR"), a normally-shorted 1x2 jumper feeding the P3V3_MCU sub-rail from
the board's main P3V3 rail. The jumper cap is removed and a Nordic PPK2
is spliced across the two pads in Ampere Meter mode (passive pass-
through -- the board's own USB-derived supply provides the voltage,
PPK2 only measures the current flowing through it). See
BENCHMARK_METHODOLOGY.md Section 6 for the full wiring procedure and the
investigation that ruled out J25/P3V3_MCU (dead flat current, wrong
rail) before arriving at J24.

Two important, explicitly-stated caveats -- read before citing these
numbers:

1. VOLTAGE IS ASSUMED, NOT MEASURED. PPK2's Ampere Meter mode is a
   passive current pass-through; it does not report the DUT's actual
   rail voltage. Energy = charge x ASSUMED_VOLTAGE, where
   ASSUMED_VOLTAGE is the board's nominal regulated P3V3 rail (3.3V).

2. PER-OPERATION SPLIT IS A MODELING ASSUMPTION, NOT A HARDWARE-VERIFIED
   BOUNDARY. The intended methodology used a GPIO trigger pin (toggled
   around each keypair/encaps/decaps call, see hello_world.c's
   ENERGY_MODE block) captured on PPK2's digital channel D0, wired to
   the board's Arduino header D2 pin (P0_29). That trigger never
   toggled in either capture on record (confirmed: the D0-D7 column is
   constant "00000000" for every sample in both raw CSVs) despite the
   firmware-side PORT-mux fix being flown and verified via a successful
   flash+reset cycle. Root cause not found before this analysis was
   written -- worth revisiting if a working trigger capture is obtained
   later, which would let per-op energy be read directly from trigger
   edges instead of modeled.

   In its absence, total energy for the whole 100-rep active window is
   divided by 100 to get per-handshake energy, then split across
   keypair/encaps/decaps in proportion to each operation's share of
   total DWT cycles (from perf_memory_summary.csv). This assumes power
   draw is roughly uniform per clock cycle across the three operations
   (plausible, since all three share the same underlying NTT/polynomial
   arithmetic building blocks) but is NOT independently verified the way
   a true trigger-bounded measurement would be.

Active-window detection: the raw current signal has fast (~10kHz-scale)
switching-regulator ripple, so a naive threshold on raw samples
fragments into many short runs instead of one contiguous block. Fixed
by boxcar-smoothing (~20ms window) before thresholding; the smoothed
signal is used only to *locate* the active window's start/end sample
indices, charge integration itself uses the raw (unsmoothed) current so
ripple isn't lost from the actual energy number.

Usage: python analyze_energy.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent
ENERGY_DIR = HERE / "energy"
ASSUMED_VOLTAGE = 3.3  # V, nominal P3V3 rail -- see caveat 1 above
REPS = 100
CORE_CLOCK_HZ = 150_000_000

# Mean DWT cycles per op per variant, from perf_memory_summary.csv
# (independently cross-validated against a separate feasibility-sprint
# run to within 0.2ms -- see PQC_BENCHMARK_REPORT.md Section 1).
CYCLES = {
    "512":  {"keypair": 2978432, "encaps": 3503918, "decaps": 4342471},
    "768":  {"keypair": 4893951, "encaps": 5692464, "decaps": 6809160},
    "1024": {"keypair": 7644704, "encaps": 8582539, "decaps": 10008989},
}

# energy/*_raw.csv files to analyze: (variant, board_label, filename)
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
    """Boxcar moving average (win in samples)."""
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
    win = max(1, int(sample_rate * 0.02))  # ~20ms smoothing window
    smoothed = smooth(cur, win)

    baseline = sorted(smoothed)[n // 20]  # ~5th percentile as idle floor
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
            print(f"skipping {filename} (not found yet)")
            continue
        r = analyze(variant, board, filename)
        rows.append(r)
        print(f"\n=== ML-KEM-{variant} ({board}) ===")
        print(f"idle baseline: {r['idle_baseline_mA']:.3f} mA, peak: {r['peak_mA']:.3f} mA")
        print(f"active window: {r['active_window_s']:.3f}s "
              f"(expected {r['expected_window_s']:.3f}s from DWT timing)")
        print(f"total energy (@ {ASSUMED_VOLTAGE}V assumed): {r['total_energy_mJ']:.4f} mJ")
        print(f"per-handshake: {r['per_handshake_uJ']:.2f} uJ  |  "
              f"keypair {r['keypair_uJ']:.2f} uJ, encaps {r['encaps_uJ']:.2f} uJ, "
              f"decaps {r['decaps_uJ']:.2f} uJ")

    if not rows:
        print("No capture files found in energy/ -- nothing to summarize.")
        return

    out_path = HERE / "energy_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
