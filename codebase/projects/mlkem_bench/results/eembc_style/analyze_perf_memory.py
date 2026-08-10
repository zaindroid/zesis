"""
Parses the three raw capture files (mlkem{512,768,1024}_raw.txt, each a
clean 100-iteration free-running run captured via
tools/golden/capture_serial.ps1, see BENCHMARK_METHODOLOGY.md for the
full protocol) and produces a summary table: per-operation cycle count
(mean, std) and peak stack usage (constant across iterations by
construction -- report it directly, no averaging needed since it's a
watermark, not a per-run measurement with noise).

150 MHz core clock throughout this lab -- cycles converted to
microseconds via that fixed frequency.

Usage: python analyze_perf_memory.py
"""
import csv
import re
from pathlib import Path

HERE = Path(__file__).parent
CORE_CLOCK_HZ = 150_000_000
VARIANTS = ["512", "768", "1024"]
OPS = ["keypair", "encaps", "decaps"]

# Code size (m_text + m_data) read directly from each variant's `ninja`
# build output (linker's own memory-region report) -- not measured at
# runtime, transcribed here from the build logs.
CODE_SIZE_BYTES = {
    "512": {"m_text": 41648, "m_data": 40928},
    "768": {"m_text": 41432, "m_data": 42400},
    "1024": {"m_text": 41944, "m_data": 44032},
}


def parse_raw(path):
    rows = {op: {"cycles": [], "stack": None} for op in OPS}
    kem_match = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            for op in OPS:
                m = re.match(rf"^{op},(\d+),(\d+)$", line)
                if m:
                    rows[op]["cycles"].append(int(m.group(1)))
                    stack = int(m.group(2))
                    if rows[op]["stack"] is None:
                        rows[op]["stack"] = stack
                    elif rows[op]["stack"] != stack:
                        print(f"  WARNING: stack HWM varied within run for {op} "
                              f"({rows[op]['stack']} vs {stack}) -- unexpected, "
                              f"investigate before trusting this number")
            m = re.match(r"^kem_match,(\d+)$", line)
            if m:
                kem_match = int(m.group(1))
    return rows, kem_match


def mean_std(vals):
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    return mean, var ** 0.5


def main():
    print(f"{'variant':<8}{'op':<10}{'n':<5}{'mean_cycles':<14}{'std_cycles':<12}"
          f"{'mean_us':<10}{'stack_bytes':<12}")
    summary_rows = []
    for v in VARIANTS:
        rows, kem_match = parse_raw(HERE / f"mlkem{v}_raw.txt")
        assert kem_match == 1, f"ML-KEM-{v}: kem_match != 1, encaps/decaps disagree!"
        for op in OPS:
            cycles = rows[op]["cycles"]
            assert len(cycles) == 100, f"ML-KEM-{v}/{op}: expected 100 reps, got {len(cycles)}"
            mean_c, std_c = mean_std(cycles)
            mean_us = mean_c / CORE_CLOCK_HZ * 1e6
            stack = rows[op]["stack"]
            print(f"{v:<8}{op:<10}{len(cycles):<5}{mean_c:<14.1f}{std_c:<12.2f}"
                  f"{mean_us:<10.1f}{stack:<12}")
            summary_rows.append({
                "variant": f"ML-KEM-{v}", "op": op, "n": len(cycles),
                "mean_cycles": f"{mean_c:.1f}", "std_cycles": f"{std_c:.2f}",
                "mean_us": f"{mean_us:.2f}", "stack_hwm_bytes": stack,
                "code_size_text_bytes": CODE_SIZE_BYTES[v]["m_text"],
                "code_size_data_bytes": CODE_SIZE_BYTES[v]["m_data"],
            })

    out_path = HERE / "perf_memory_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"\nwrote {out_path}")

    print("\n--- full handshake (keypair + encaps + decaps), summed means ---")
    for v in VARIANTS:
        rows, _ = parse_raw(HERE / f"mlkem{v}_raw.txt")
        total_us = sum(mean_std(rows[op]["cycles"])[0] for op in OPS) / CORE_CLOCK_HZ * 1e6
        total_stack = max(rows[op]["stack"] for op in OPS)  # peak across the handshake, not summed
        print(f"ML-KEM-{v}: handshake_us={total_us:.1f}  "
              f"peak_stack_bytes={total_stack} (max single-op HWM, not summed -- "
              f"ops run sequentially, reusing the same stack region)")


if __name__ == "__main__":
    main()
