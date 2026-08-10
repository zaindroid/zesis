"""
Analyzes the three interleaved crypto+perception policy captures (naive,
static, adaptive): frame-level CSVs from tools/run_policy_experiment.py
plus PPK2 Ampere-meter energy captures at J24.

Energy: total energy per policy is integrated directly from the raw PPK2
current trace over the whole capture's active window (board-boot dip
excluded, idle-before/after excluded) -- NOT the per-op cycle-proportional
model used elsewhere in this project. Voltage is assumed at 3.3V (PPK2
Ammeter mode does not report the DUT's actual voltage).

Deadline: no literal real-time deadline exists in this UART-batch-driven
experiment (frames are requested one at a time by the host, not captured
free-running at a fixed frame rate). A 33ms/30fps budget is used here as
an illustrative, explicitly-stated assumption, applied to
crypto_us + frame_us per frame (the actual serial, single-core cost a
frame would see in a deployed system, since the crypto step blocks the
core immediately before frame processing on frames where it runs).

Safety-critical miss-rate: computed from is_safety_critical + label +
whichever exit's prediction was actually taken (pred1/pred2/pred3
depending on exit_taken), independently from the conformal calibration
pipeline's own numbers.

Usage: python analyze_interleaved.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent
ASSUMED_VOLTAGE = 3.3
DEADLINE_MS = 33.0  # illustrative 30fps budget, explicitly assumed -- see docstring
POLICIES = ["naive", "static", "adaptive"]


def load_frames(policy):
    with open(HERE / f"policy_results_{policy}.csv", newline="") as f:
        return list(csv.DictReader(f))


def frame_pred(row):
    exit_taken = int(row["exit_taken"])
    return int(row[f"pred{exit_taken}"])


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
    """Unlike the standalone crypto benchmarks (idle is the majority of the
    capture, active is a brief minority), this interleaved workload is
    ACTIVE for the vast majority of the capture (continuous frame-by-frame
    processing for ~750+ seconds) with only a short idle tail before/after
    -- so a low-percentile "baseline" lands inside the active region itself,
    not the true idle level. Use the MEDIAN as the representative active
    level instead, and a threshold below it to catch the idle dips."""
    n = len(ts)
    sample_rate = (n - 1) / (ts[-1] - ts[0])
    win = max(1, int(sample_rate * 0.2))  # 200ms smoothing -- long, noisy capture
    smoothed = smooth(cur, win)
    sorted_vals = sorted(smoothed)
    active_level = sorted_vals[n // 2]        # median -- representative of the dominant active state
    idle_level = sorted_vals[n // 100]        # 1st percentile -- representative of the minority idle tail
    thresh = idle_level + 0.5 * (active_level - idle_level)

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
    return best_start, best_end, idle_level, max(smoothed)


def analyze_energy(policy):
    ts, cur = [], []
    with open(HERE / f"ppk_{policy}_raw.csv", newline="") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            ts.append(float(row[0]) / 1000.0)
            cur.append(float(row[1]) / 1e6)

    start, end, baseline, peak = find_active_window(ts, cur)
    t0, t1 = ts[start], ts[end - 1]
    duration = t1 - t0

    charge = 0.0
    for i in range(start, end - 1):
        dt = ts[i + 1] - ts[i]
        charge += 0.5 * (cur[i] + cur[i + 1]) * dt
    energy_J = charge * ASSUMED_VOLTAGE

    return {
        "idle_baseline_mA": baseline * 1000, "peak_mA": peak * 1000,
        "active_window_s": duration, "total_energy_mJ": energy_J * 1000,
        "mean_current_mA": charge / duration * 1000,
    }


def analyze_frames(policy):
    rows = load_frames(policy)
    n = len(rows)

    frame_latencies = [(int(r["crypto_us"]) + int(r["frame_us"])) / 1000.0 for r in rows]
    frame_us_only = [int(r["frame_us"]) / 1000.0 for r in rows]
    misses = sum(1 for lat in frame_latencies if lat > DEADLINE_MS)

    exit_dist = {"1": 0, "2": 0, "3": 0}
    for r in rows:
        exit_dist[r["exit_taken"]] += 1

    correct = sum(1 for r in rows if frame_pred(r) == int(r["label"]))
    accuracy = correct / n

    sc_rows = [r for r in rows if r["is_safety_critical"] == "1"]
    sc_n = len(sc_rows)
    sc_miss = sum(1 for r in sc_rows if frame_pred(r) != int(r["label"]))
    sc_miss_rate = sc_miss / sc_n if sc_n else float("nan")

    total_crypto_us = sum(int(r["crypto_us"]) for r in rows)
    total_frame_us = sum(int(r["frame_us"]) for r in rows)

    return {
        "n_frames": n,
        "mean_latency_ms": sum(frame_latencies) / n,
        "worst_latency_ms": max(frame_latencies),
        "mean_frame_only_ms": sum(frame_us_only) / n,
        "deadline_misses": misses,
        "deadline_miss_pct": misses / n * 100,
        "exit1_pct": exit_dist["1"] / n * 100,
        "exit2_pct": exit_dist["2"] / n * 100,
        "exit3_pct": exit_dist["3"] / n * 100,
        "overall_accuracy": accuracy,
        "sc_n": sc_n,
        "sc_miss_rate": sc_miss_rate,
        "total_crypto_ms": total_crypto_us / 1000.0,
        "total_frame_ms": total_frame_us / 1000.0,
    }


def main():
    results = {}
    for policy in POLICIES:
        print(f"\n=== {policy.upper()} ===")
        e = analyze_energy(policy)
        f = analyze_frames(policy)
        results[policy] = {**e, **f}

        print(f"active window: {e['active_window_s']:.2f}s  "
              f"(idle baseline {e['idle_baseline_mA']:.2f}mA, peak {e['peak_mA']:.2f}mA, "
              f"mean {e['mean_current_mA']:.2f}mA)")
        print(f"total energy: {e['total_energy_mJ']:.2f} mJ")
        print(f"frames: {f['n_frames']}  mean_latency={f['mean_latency_ms']:.3f}ms  "
              f"worst={f['worst_latency_ms']:.3f}ms  "
              f"deadline_misses={f['deadline_misses']} ({f['deadline_miss_pct']:.2f}%) @ {DEADLINE_MS}ms budget")
        print(f"exits: exit1={f['exit1_pct']:.1f}% exit2={f['exit2_pct']:.1f}% exit3={f['exit3_pct']:.1f}%")
        print(f"overall accuracy: {f['overall_accuracy']*100:.2f}%  "
              f"safety-critical miss-rate: {f['sc_miss_rate']*100:.3f}% (n={f['sc_n']})")

    # write summary CSV
    out_path = HERE / "interleaved_summary.csv"
    fieldnames = ["policy"] + list(next(iter(results.values())).keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for policy in POLICIES:
            writer.writerow({"policy": policy, **results[policy]})
    print(f"\nwrote {out_path}")

    # deltas
    print("\n=== DELTAS ===")
    st, ad = results["static"], results["adaptive"]

    if "naive" in results:
        nv = results["naive"]
        time_saved = (nv["active_window_s"] - ad["active_window_s"]) / nv["active_window_s"] * 100
        energy_saved = (nv["total_energy_mJ"] - ad["total_energy_mJ"]) / nv["total_energy_mJ"] * 100
        miss_reduction = nv["deadline_misses"] - ad["deadline_misses"]
        print(f"adaptive vs naive: {time_saved:+.2f}% time, {energy_saved:+.2f}% energy, "
              f"{miss_reduction:+d} fewer deadline misses "
              f"({nv['deadline_misses']} -> {ad['deadline_misses']})")
    else:
        print("adaptive vs naive: SKIPPED (naive capture incomplete, pending re-capture)")

    energy_delta_vs_static = (st["total_energy_mJ"] - ad["total_energy_mJ"]) / st["total_energy_mJ"] * 100
    acc_delta_vs_static = (ad["overall_accuracy"] - st["overall_accuracy"]) * 100
    sc_delta_vs_static = (st["sc_miss_rate"] - ad["sc_miss_rate"]) * 100
    print(f"adaptive vs static: {energy_delta_vs_static:+.2f}% energy, "
          f"{acc_delta_vs_static:+.3f}pp overall accuracy, "
          f"{sc_delta_vs_static:+.3f}pp safety-critical miss-rate (positive = adaptive safer)")

    # safety-bound confirmation
    print("\n=== SAFETY-BOUND CONFIRMATION (operating alpha=0.05) ===")
    ok = ad["sc_miss_rate"] <= 0.05
    print(f"adaptive empirical safety-critical miss-rate over full workload: "
          f"{ad['sc_miss_rate']*100:.3f}%  vs  alpha=5.000%  ->  "
          f"{'WITHIN BOUND' if ok else 'BOUND VIOLATED'}")
    print("(this is a single 1230-frame empirical check, not a new conformal "
          "calibration -- the actual certified guarantee is the frozen "
          "single-touch result in BRIEF3_FINAL_certified_menu.csv; this just "
          "confirms the deployed policy didn't blow past it on this run.)")


if __name__ == "__main__":
    main()
