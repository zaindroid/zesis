"""
Applies the PC-calibrated tau_k thresholds (conformal_tau_table.csv, chosen
on the CALIBRATION split, computed entirely on the training lab) to
hw_results.csv -- genuine on-device NPU predictions for a stratified sample
of the held-out TEST split -- and checks whether the achieved
safety-critical miss-rate among accepted samples still stays <= the target
alpha, exactly like conformal/coverage_validate.py, but using real hardware
output instead of a PC TFLite-interpreter simulation.

Usage: python tools/hw_validate/compute_coverage.py
"""
import csv
from pathlib import Path

HERE = Path(__file__).parent
EXITS = ["exit1", "exit2", "exit3"]


def main():
    with open(HERE / "hw_results.csv", newline="") as f:
        results = list(csv.DictReader(f))
    print(f"on-device sample: {len(results)} images "
          f"({sum(int(r['is_safety_critical']) for r in results)} safety-critical)")

    with open(HERE / "conformal_tau_table.csv", newline="") as f:
        tau_table = list(csv.DictReader(f))

    with open(HERE / "coverage_validation_table.csv", newline="") as f:
        pc_table = {(r["exit"], r["target_alpha"]): r for r in csv.DictReader(f)}

    # PC-simulated predictions for this EXACT sample of images (not the
    # full natural-frequency test set) -- isolates whether any HW-vs-PC gap
    # is a real hardware effect or just an artifact of stratified sampling
    # (our sample caps safety-critical classes at 40 each, which
    # over-represents rare/hard classes relative to their natural test-set
    # frequency).
    with open(HERE / "pc_test_predictions_joined.csv", newline="") as f:
        pc_by_filename = {r["filename"]: r for r in csv.DictReader(f)}
    pc_sample = [pc_by_filename[r["filename"]] for r in results]

    out_rows = []
    print(f"\n{'exit':<7}{'alpha':<7}{'tau':<8}{'n_hw':<6}{'miss_hw':<9}{'pass_hw':<8}"
          f"{'n_pcS':<7}{'miss_pcS':<10}{'pass_pcS':<9}{'miss_pc(full)':<8}")

    for row in tau_table:
        exit_name = row["exit"]
        alpha = float(row["alpha"])
        tau = float(row["tau"])
        certifiable = row["certifiable"] == "True"

        idx = {"exit1": "1", "exit2": "2", "exit3": "3"}[exit_name]
        sc = [r for r in results if int(r["is_safety_critical"]) == 1]
        accepted = [r for r in sc if float(r[f"conf{idx}"]) >= tau]
        n = len(accepted)
        n_miss = sum(1 - int(r[f"correct{idx}"]) for r in accepted)
        achieved_miss = (n_miss / n) if n > 0 else float("nan")
        passes = certifiable and (n > 0) and (achieved_miss <= alpha)

        pc = pc_table.get((exit_name, row["alpha"]))
        pc_full_miss = pc["achieved_miss_rate_test"] if pc else "?"

        sc_pc = [r for r in pc_sample if int(r["is_safety_critical"]) == 1]
        accepted_pc = [r for r in sc_pc if float(r[f"conf{idx}"]) >= tau]
        n_pcS = len(accepted_pc)
        n_miss_pcS = sum(1 - int(r[f"correct{idx}"]) for r in accepted_pc)
        miss_pcS = (n_miss_pcS / n_pcS) if n_pcS > 0 else float("nan")
        pass_pcS = certifiable and (n_pcS > 0) and (miss_pcS <= alpha)

        print(f"{exit_name:<7}{alpha:<7}{tau:<8.3f}{n:<6}"
              f"{achieved_miss if n>0 else float('nan'):<9.4f}{str(passes):<8}"
              f"{n_pcS:<7}{miss_pcS if n_pcS>0 else float('nan'):<10.4f}{str(pass_pcS):<9}{pc_full_miss:<8}")

        out_rows.append({
            "exit": exit_name, "target_alpha": alpha, "tau_k": tau,
            "certifiable_at_calibration": certifiable,
            "n_accepted_hw": n,
            "achieved_miss_rate_hw": f"{achieved_miss:.4f}" if n > 0 else "nan",
            "passes_hw": passes,
            "n_accepted_pc_same_sample": n_pcS,
            "achieved_miss_rate_pc_same_sample": f"{miss_pcS:.4f}" if n_pcS > 0 else "nan",
            "passes_pc_same_sample": pass_pcS,
            "achieved_miss_rate_pc_fulltest": pc_full_miss,
        })

    out_path = HERE / "hw_coverage_validation_table.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"\nwrote {out_path}")

    n_fail = sum(1 for r in out_rows if not r["passes_hw"] and r["certifiable_at_calibration"])
    n_certifiable = sum(1 for r in out_rows if r["certifiable_at_calibration"])
    print(f"\n{n_certifiable - n_fail}/{n_certifiable} certifiable (exit, alpha) combinations "
          f"passed coverage validation on real NPU hardware output.")


if __name__ == "__main__":
    main()
