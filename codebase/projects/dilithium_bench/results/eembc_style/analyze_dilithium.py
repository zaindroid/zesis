"""
Parses the three raw capture files (mldsa{44,65,87}_capture.txt, each a
free-running run captured via tools/golden/capture_serial.ps1 -- see
dilithium_bench's firmware header comment for the measurement protocol)
and produces:

  - keypair/verify: mean + spread (100 reps each, near-deterministic).
  - sign: the actual experiment. >=2000 reps, ONE raw cycle count per
    call, never pre-averaged on-device. Percentiles (min/median/mean/
    p90/p95/p99/max) and the worst/median ratio -- THE headline number --
    are computed here, independently, from the raw per-call array.
  - stack high-water-mark per op (painted+scanned every call for sign,
    so if stack depth genuinely varies with retry count it would show up
    as a non-constant HWM -- report whatever is actually observed).
  - retry-count (rejection-sampling attempt count) distribution and its
    correlation with signing time.
  - code size (m_text/m_data), transcribed from each variant's `ninja`
    build output (the linker's own memory-region report), same
    convention as mlkem_bench's analyze_perf_memory.py.

150 MHz core clock throughout this lab -- cycles converted to
microseconds via that fixed frequency.

Usage: python analyze_dilithium.py
"""
import csv
import re
from pathlib import Path

HERE = Path(__file__).parent
RESULTS_DIR = HERE.parent
CORE_CLOCK_HZ = 150_000_000
VARIANTS = ["44", "65", "87"]
KEYPAIR_VERIFY_REPS = 100
N_SIGN = 2048

# Code size (m_text + m_data), read directly from each variant's `ninja`
# build output (linker's own memory-region report) -- not measured at
# runtime, transcribed here from the build logs. Filled in as each level
# is built; a level not yet built is left as None and skipped in the
# code-size table.
CODE_SIZE_BYTES = {
    # NOTE: m_data here is from the ACTUAL build that was flashed and
    # captured (128 KiB stack, __stack_size__=0x20000). An earlier build
    # attempt at the spec's suggested 32 KiB starting stack (m_data=70656)
    # HardFaulted and was never used for a real capture -- see the
    # stack-tuning finding in the report.
    "44": {"m_text": 50840, "m_data": 168960},
    "65": {"m_text": 49368, "m_data": 237496},
    "87": {"m_text": 50160, "m_data": 273088},
}

# Stack size (bytes) passed to the linker via __stack_size__ for the run
# that produced each capture file -- recorded here since it's a build
# parameter, not something derivable from the capture itself.
STACK_SIZE_BYTES = {
    "44": 0x20000,
    "65": 0x30000,
    "87": 0x38000,
}


def cycles_to_us(c):
    return c / CORE_CLOCK_HZ * 1e6


def parse_capture(path):
    meta = {}
    keypair = {}
    verify = {}
    sign_cycles = []
    sign_stack = []
    sign_attempts = []
    sign_verify_ok = []
    verify_fail_count = None
    saw_done = False

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line == "done":
                saw_done = True
                # A stale listener process from a LATER capture can keep a
                # file handle open past this point and append a subsequent
                # run's early boot output to this file (observed in
                # practice: level N's listener wasn't stopped before level
                # N+1 was flashed). Anything after the first 'done' is not
                # this run's data -- stop here rather than let a later
                # dict-overwrite silently corrupt keypair/verify stats.
                break
            m = re.match(r"^alg,(.+)$", line)
            if m:
                meta["alg"] = m.group(1)
                continue
            m = re.match(r"^(stack_region_bytes|pk_bytes|sk_bytes|sig_bytes|n_sign_reps|"
                         r"dwt_sanity|sign_verify_fail_count),(\d+)$", line)
            if m:
                meta[m.group(1)] = int(m.group(2))
                continue
            m = re.match(r"^keypair_(mean|min|max|stack_hwm)_(?:cycles|bytes),(\d+)$", line)
            if m:
                keypair[m.group(1)] = int(m.group(2))
                continue
            m = re.match(r"^verify_(mean|min|max|stack_hwm)_(?:cycles|bytes),(\d+)$", line)
            if m:
                verify[m.group(1)] = int(m.group(2))
                continue
            m = re.match(r"^sign,(\d+),(\d+),(\d+),(\d+)$", line)
            if m:
                sign_cycles.append(int(m.group(1)))
                sign_stack.append(int(m.group(2)))
                sign_attempts.append(int(m.group(3)))
                sign_verify_ok.append(int(m.group(4)))
                continue
            if line == "done":
                saw_done = True

    return {
        "meta": meta, "keypair": keypair, "verify": verify,
        "sign_cycles": sign_cycles, "sign_stack": sign_stack,
        "sign_attempts": sign_attempts, "sign_verify_ok": sign_verify_ok,
        "saw_done": saw_done,
    }


def percentile(sorted_vals, p):
    """Nearest-rank percentile, 0 <= p <= 100, on an already-sorted list."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (p / 100) * (n - 1)
    lo = int(k)
    hi = min(lo + 1, n - 1)
    frac = k - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def mean(vals):
    return sum(vals) / len(vals)


def stddev(vals):
    m = mean(vals)
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5


def median(sorted_vals):
    return percentile(sorted_vals, 50)


def analyze_sign(cycles, attempts, verify_ok):
    n = len(cycles)
    s = sorted(cycles)
    mn, mx = s[0], s[-1]
    med = median(s)
    mean_c = mean(cycles)
    p90 = percentile(s, 90)
    p95 = percentile(s, 95)
    p99 = percentile(s, 99)
    worst_over_median = mx / med if med > 0 else float("inf")

    verify_fail = n - sum(verify_ok)

    # Retry (rejection-sampling attempt count) distribution.
    from collections import Counter
    attempt_hist = Counter(attempts)

    # Retry-vs-time correlation: mean signing time per attempt count.
    by_attempts = {}
    for c, a in zip(cycles, attempts):
        by_attempts.setdefault(a, []).append(c)
    retry_time_table = {
        a: {"n": len(v), "mean_us": cycles_to_us(mean(v))}
        for a, v in sorted(by_attempts.items())
    }

    # Pearson correlation coefficient between attempts and cycles.
    if n > 1 and len(set(attempts)) > 1:
        ma, mc = mean(attempts), mean(cycles)
        cov = sum((a - ma) * (c - mc) for a, c in zip(attempts, cycles)) / n
        sa = stddev(attempts)
        sc = stddev(cycles)
        pearson_r = cov / (sa * sc) if sa > 0 and sc > 0 else float("nan")
    else:
        pearson_r = float("nan")

    return {
        "n": n, "min_cycles": mn, "median_cycles": med, "mean_cycles": mean_c,
        "p90_cycles": p90, "p95_cycles": p95, "p99_cycles": p99, "max_cycles": mx,
        "worst_over_median": worst_over_median,
        "min_us": cycles_to_us(mn), "median_us": cycles_to_us(med),
        "mean_us": cycles_to_us(mean_c), "p90_us": cycles_to_us(p90),
        "p95_us": cycles_to_us(p95), "p99_us": cycles_to_us(p99),
        "max_us": cycles_to_us(mx),
        "verify_fail_count": verify_fail,
        "attempt_hist": dict(sorted(attempt_hist.items())),
        "retry_time_table": retry_time_table,
        "pearson_r_attempts_vs_cycles": pearson_r,
    }


def main():
    summary_rows = []
    sign_analyses = {}
    captures = {}

    for v in VARIANTS:
        path = RESULTS_DIR / f"mldsa{v}_capture.txt"
        if not path.exists():
            print(f"-- ML-DSA-{v}: no capture file yet ({path.name}), skipping --")
            continue
        cap = parse_capture(path)
        captures[v] = cap

        if not cap["saw_done"]:
            print(f"  WARNING: ML-DSA-{v} capture has no trailing 'done' line -- "
                  f"run may be truncated/incomplete, treat with caution")

        n_keypair = len(cap["keypair"])
        n_sign = len(cap["sign_cycles"])
        print(f"ML-DSA-{v}: keypair fields={n_keypair}, sign reps captured={n_sign}")

        if n_sign < 2000:
            print(f"  WARNING: only {n_sign} sign reps captured, spec asks for >=2000")

        if cap["sign_cycles"]:
            sa = analyze_sign(cap["sign_cycles"], cap["sign_attempts"], cap["sign_verify_ok"])
            sign_analyses[v] = sa
            if sa["verify_fail_count"] > 0:
                print(f"  *** ML-DSA-{v}: {sa['verify_fail_count']} sign->verify "
                      f"round-trip FAILURES -- investigate before trusting this run ***")

        summary_rows.append({
            "variant": f"ML-DSA-{v}",
            "keypair_mean_us": cycles_to_us(cap["keypair"].get("mean", 0)),
            "keypair_min_us": cycles_to_us(cap["keypair"].get("min", 0)),
            "keypair_max_us": cycles_to_us(cap["keypair"].get("max", 0)),
            "keypair_stack_hwm_bytes": cap["keypair"].get("stack_hwm", ""),
            "verify_mean_us": cycles_to_us(cap["verify"].get("mean", 0)),
            "verify_min_us": cycles_to_us(cap["verify"].get("min", 0)),
            "verify_max_us": cycles_to_us(cap["verify"].get("max", 0)),
            "verify_stack_hwm_bytes": cap["verify"].get("stack_hwm", ""),
            "sign_n": len(cap["sign_cycles"]),
            "sign_min_us": sign_analyses[v]["min_us"] if v in sign_analyses else "",
            "sign_median_us": sign_analyses[v]["median_us"] if v in sign_analyses else "",
            "sign_mean_us": sign_analyses[v]["mean_us"] if v in sign_analyses else "",
            "sign_p90_us": sign_analyses[v]["p90_us"] if v in sign_analyses else "",
            "sign_p95_us": sign_analyses[v]["p95_us"] if v in sign_analyses else "",
            "sign_p99_us": sign_analyses[v]["p99_us"] if v in sign_analyses else "",
            "sign_max_us": sign_analyses[v]["max_us"] if v in sign_analyses else "",
            "sign_worst_over_median": sign_analyses[v]["worst_over_median"] if v in sign_analyses else "",
            "sign_stack_hwm_bytes_min": min(cap["sign_stack"]) if cap["sign_stack"] else "",
            "sign_stack_hwm_bytes_max": max(cap["sign_stack"]) if cap["sign_stack"] else "",
            "stack_size_bytes": STACK_SIZE_BYTES.get(v, ""),
            "code_size_text_bytes": (CODE_SIZE_BYTES.get(v) or {}).get("m_text", ""),
            "code_size_data_bytes": (CODE_SIZE_BYTES.get(v) or {}).get("m_data", ""),
        })

    if not summary_rows:
        print("No capture files found yet -- nothing to analyze.")
        return

    out_path = HERE / "dilithium_summary.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"\nwrote {out_path}")

    # Per-call raw sign CSV, re-derived from the parsed capture (so it's
    # independently regenerable from the raw serial dump, not just a
    # copy of it).
    for v, cap in captures.items():
        raw_path = HERE / f"mldsa{v}_sign_raw.csv"
        with open(raw_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["iter", "cycles", "us", "stack_hwm_bytes", "attempts", "verify_ok"])
            for i, (c, st, a, ok) in enumerate(zip(
                    cap["sign_cycles"], cap["sign_stack"],
                    cap["sign_attempts"], cap["sign_verify_ok"])):
                w.writerow([i, c, f"{cycles_to_us(c):.3f}", st, a, ok])
        print(f"wrote {raw_path} ({len(cap['sign_cycles'])} rows)")

    print("\n--- SIGN latency distribution (headline result) ---")
    print(f"{'variant':<10}{'n':<6}{'min_us':<10}{'median_us':<11}{'mean_us':<10}"
          f"{'p90_us':<10}{'p95_us':<10}{'p99_us':<10}{'max_us':<10}{'worst/median':<13}")
    for v, sa in sign_analyses.items():
        print(f"{'ML-DSA-'+v:<10}{sa['n']:<6}{sa['min_us']:<10.1f}{sa['median_us']:<11.1f}"
              f"{sa['mean_us']:<10.1f}{sa['p90_us']:<10.1f}{sa['p95_us']:<10.1f}"
              f"{sa['p99_us']:<10.1f}{sa['max_us']:<10.1f}{sa['worst_over_median']:<13.3f}")

    print("\n--- retry (rejection-sampling attempt) distribution ---")
    for v, sa in sign_analyses.items():
        total = sum(sa["attempt_hist"].values())
        hist_str = ", ".join(f"{a} attempt(s): {c} ({c/total*100:.1f}%)"
                              for a, c in sa["attempt_hist"].items())
        print(f"ML-DSA-{v}: {hist_str}")
        print(f"  Pearson r(attempts, cycles) = {sa['pearson_r_attempts_vs_cycles']:.3f}")
        for a, t in sa["retry_time_table"].items():
            print(f"    attempts={a}: n={t['n']}, mean_us={t['mean_us']:.1f}")

    print("\n--- deadline-hazard interpretation ---")
    for v, sa in sign_analyses.items():
        ratio = sa["worst_over_median"]
        if ratio >= 2.0:
            verdict = ("non-determinism is REAL -- would threaten a hard real-time "
                       "control deadline sized near the median")
        elif ratio <= 1.3:
            verdict = "tight -- jitter motivation is WEAK for this level"
        else:
            verdict = "moderate -- borderline, report plainly"
        worst_us = sa["max_us"]
        print(f"ML-DSA-{v}: worst/median = {ratio:.3f}x  ({verdict})")
        print(f"  worst observed sign = {worst_us:.1f} us -> fatal to a "
              f"{1e6/worst_us:.0f} Hz ({worst_us/1000:.3f} ms) control loop or faster; "
              f"irrelevant to loops slower than that")


if __name__ == "__main__":
    main()
