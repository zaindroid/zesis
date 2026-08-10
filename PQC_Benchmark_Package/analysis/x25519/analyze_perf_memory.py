import csv
import re
from pathlib import Path

HERE = Path(__file__).parent
RESULTS_DIR = HERE.parent.parent / "results" / "x25519"
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
    rows, dh_match = parse_raw(RESULTS_DIR / "x25519_raw.txt")
    assert dh_match == 1

    summary_rows = []
    for op in OPS:
        cycles = rows[op]["cycles"]
        mean_c, std_c = mean_std(cycles)
        mean_us = mean_c / CORE_CLOCK_HZ * 1e6
        stack = rows[op]["stack"]
        print(f"{op:<16}{len(cycles):<5}{mean_c:<14.1f}{std_c:<12.2f}{mean_us:<10.1f}{stack:<12}")
        summary_rows.append({
            "variant": "X25519", "op": op, "n": len(cycles),
            "mean_cycles": f"{mean_c:.1f}", "std_cycles": f"{std_c:.2f}",
            "mean_us": f"{mean_us:.2f}", "stack_hwm_bytes": stack,
            "code_size_text_bytes": CODE_SIZE_BYTES["m_text"],
            "code_size_data_bytes": CODE_SIZE_BYTES["m_data"],
        })

    out_path = RESULTS_DIR / "perf_memory_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
