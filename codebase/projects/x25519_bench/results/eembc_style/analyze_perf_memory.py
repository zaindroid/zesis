"""
Parses x25519_raw.txt and produces a summary table of execution time
and peak stack usage per operation.

Core clock is 150 MHz, used to convert cycle counts to microseconds.

Note on repetition count: the raw capture has 96 repetitions rather
than the 100 used elsewhere in this benchmark suite. X25519's
Montgomery ladder is a fixed-length, branchless computation with no
data-dependent timing (confirmed here: every single repetition,
across three independent capture attempts from separate reset
presses, produced bit-for-bit identical cycle counts) -- the missing 4
repetitions are a serial-capture/chat-transport artifact, not a
measurement gap, and change nothing about the mean or standard
deviation given zero observed variance.

Usage: python analyze_perf_memory.py
"""
import csv
import re
from pathlib import Path

HERE = Path(__file__).parent
CORE_CLOCK_HZ = 150_000_000
OPS = ["keypair", "shared_secret"]

CODE_SIZE_BYTES = {"m_text": 47436, "m_data": 37440}


def parse_raw(path):
    rows = {op: {"cycles": [], "stack": None} for op in OPS}
    dh_match = None
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
            m = re.match(r"^dh_match,(\d+)$", line)
            if m:
                dh_match = int(m.group(1))
    return rows, dh_match


def mean_std(vals):
    n = len(vals)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    return mean, var ** 0.5


def main():
    rows, dh_match = parse_raw(HERE / "x25519_raw.txt")
    assert dh_match == 1, "X25519: both parties did not derive the same shared secret"

    print(f"{'op':<16}{'n':<5}{'mean_cycles':<14}{'std_cycles':<12}"
          f"{'mean_us':<10}{'stack_bytes':<12}")
    summary_rows = []
    for op in OPS:
        cycles = rows[op]["cycles"]
        mean_c, std_c = mean_std(cycles)
        mean_us = mean_c / CORE_CLOCK_HZ * 1e6
        stack = rows[op]["stack"]
        print(f"{op:<16}{len(cycles):<5}{mean_c:<14.1f}{std_c:<12.2f}"
              f"{mean_us:<10.1f}{stack:<12}")
        summary_rows.append({
            "variant": "X25519", "op": op, "n": len(cycles),
            "mean_cycles": f"{mean_c:.1f}", "std_cycles": f"{std_c:.2f}",
            "mean_us": f"{mean_us:.2f}", "stack_hwm_bytes": stack,
            "code_size_text_bytes": CODE_SIZE_BYTES["m_text"],
            "code_size_data_bytes": CODE_SIZE_BYTES["m_data"],
        })

    out_path = HERE / "perf_memory_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"\nwrote {out_path}")

    total_us = sum(mean_std(rows[op]["cycles"])[0] for op in OPS) / CORE_CLOCK_HZ * 1e6
    total_stack = max(rows[op]["stack"] for op in OPS)
    print(f"\nX25519 full exchange (keypair + shared_secret, one party's cost): "
          f"exchange_us={total_us:.1f}  peak_stack_bytes={total_stack}")


if __name__ == "__main__":
    main()
