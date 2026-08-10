"""
Parses the free-running serial capture from the segmentation-overhead
firmware (main.cpp) into per-phase CSVs and computes dispatch overhead.
"""
import csv
import statistics
import sys

RAW_PATH = "H:/z_thesis/codebase/projects/npu_segments/builds/capture_segments_raw.txt"
OUT_DIR = "H:/z_thesis/codebase/projects/npu_segments/builds"

# Intermediate activation footprint (bytes), from build_toy_model.py output
ACTIVATION_AFTER_A = 2048   # 16x16x8 INT8
ACTIVATION_AFTER_B = 1024   # 8x8x16 INT8


def main():
    lines = open(RAW_PATH, encoding="utf-8").read().splitlines()
    lines = [l.strip() for l in lines if l.strip()]

    if "phase,iteration,total_us" not in lines:
        print("ERROR: header 'phase,iteration,total_us' not found in capture")
        sys.exit(1)
    start = lines.index("phase,iteration,total_us") + 1
    end = lines.index("done") if "done" in lines else len(lines)
    data_lines = lines[start:end]

    phases = {"mono": [], "seg2": [], "seg3": []}
    for line in data_lines:
        parts = line.split(",")
        if len(parts) != 3:
            continue
        phase, it, us = parts
        if phase in phases:
            phases[phase].append(int(us))

    for name, vals in phases.items():
        print(f"{name}: n={len(vals)}")
        if len(vals) != 100:
            print(f"  WARNING: expected 100 samples, got {len(vals)}")

    # Save per-phase CSVs
    for name, vals in phases.items():
        with open(f"{OUT_DIR}/phase_{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["iteration", "total_us"])
            for i, v in enumerate(vals, 1):
                w.writerow([i, v])

    stats = {}
    for name, vals in phases.items():
        stats[name] = {
            "mean": statistics.mean(vals),
            "stdev": statistics.pstdev(vals),
            "min": min(vals),
            "max": max(vals),
            "median": statistics.median(vals),
        }
        print(f"\n{name}: mean={stats[name]['mean']:.2f}us stdev={stats[name]['stdev']:.2f} "
              f"min={stats[name]['min']} max={stats[name]['max']} median={stats[name]['median']}")

    mono_mean = stats["mono"]["mean"]
    seg2_mean = stats["seg2"]["mean"]
    seg3_mean = stats["seg3"]["mean"]

    seg2_overhead_total = seg2_mean - mono_mean
    seg3_overhead_total = seg3_mean - mono_mean

    # 2-seg has 1 extra dispatch boundary (AB|C), 3-seg has 2 (A|B, B|C)
    seg2_overhead_per_boundary = seg2_overhead_total / 1
    seg3_overhead_per_boundary = seg3_overhead_total / 2

    print(f"\n--- Overhead summary ---")
    print(f"monolithic baseline:        {mono_mean:.2f} us")
    print(f"2-seg total:                {seg2_mean:.2f} us  (+{seg2_overhead_total:.2f} us vs monolithic)")
    print(f"2-seg overhead/boundary:    {seg2_overhead_per_boundary:.2f} us  (1 boundary)")
    print(f"3-seg total:                {seg3_mean:.2f} us  (+{seg3_overhead_total:.2f} us vs monolithic)")
    print(f"3-seg overhead/boundary:    {seg3_overhead_per_boundary:.2f} us  (2 boundaries)")

    with open(f"{OUT_DIR}/segmentation_overhead_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["config", "n_segments", "n_boundaries", "mean_us", "stdev_us", "min_us", "max_us",
                    "overhead_vs_monolithic_us", "overhead_per_boundary_us",
                    "intermediate_activation_bytes_total"])
        w.writerow(["monolithic", 1, 0, f"{mono_mean:.2f}", f"{stats['mono']['stdev']:.2f}",
                    stats["mono"]["min"], stats["mono"]["max"], 0, 0, 0])
        w.writerow(["2-segment", 2, 1, f"{seg2_mean:.2f}", f"{stats['seg2']['stdev']:.2f}",
                    stats["seg2"]["min"], stats["seg2"]["max"],
                    f"{seg2_overhead_total:.2f}", f"{seg2_overhead_per_boundary:.2f}",
                    ACTIVATION_AFTER_B])
        w.writerow(["3-segment", 3, 2, f"{seg3_mean:.2f}", f"{stats['seg3']['stdev']:.2f}",
                    stats["seg3"]["min"], stats["seg3"]["max"],
                    f"{seg3_overhead_total:.2f}", f"{seg3_overhead_per_boundary:.2f}",
                    ACTIVATION_AFTER_A + ACTIVATION_AFTER_B])

    print(f"\nWrote {OUT_DIR}/segmentation_overhead_summary.csv")


if __name__ == "__main__":
    main()
