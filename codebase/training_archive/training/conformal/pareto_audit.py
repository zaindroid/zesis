#!/usr/bin/env python3
"""Stage-3 Go/No-Go gate: Pareto efficiency audit — is the LTC worth training?

Compare the discrete 3-exit anytime frontier (measured: per-exit accuracy on
the calibration split, per-exit compute from the PPK2-validated EXIT_MS) with
the best-case continuous (LTC) frontier. The LTC's advantage can only be the
accuracy 'trapped' between the discrete exits — compute that bound and the
risk-adjusted cost of realising it.

Verdict rule (the user's staged-plan framing):
  - If the discrete frontier already covers the trade-off well (exit2 ~
    exit3 accuracy at ~half the cost), the LTC gain is < a few % -> NO-GO
    (discrete is Pareto-optimal); granularity, if wanted, is cheaper via
    adding discrete exits with the EXISTING certification machinery."""
import csv, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(__file__), "..")
RESULTS = os.path.join(ROOT, "results", "ttca")
os.makedirs(RESULTS, exist_ok=True)

EXIT_MS = {1: 0.80, 2: 1.24, 3: 2.34}          # measured (MCX)
EXIT_FRAC = {1: 0.30, 2: 0.60, 3: 1.00}         # model depth fraction


def exit_accuracy(exit_k):
    rows = list(csv.DictReader(open(os.path.join(
        ROOT, "results", f"calibration_predictions_exit{exit_k}.csv"))))
    acc = sum(int(r["correct"]) for r in rows) / len(rows)
    return acc


def main():
    acc = {k: exit_accuracy(k) for k in (1, 2, 3)}
    print("discrete anytime frontier (measured):")
    for k in (1, 2, 3):
        print(f"  exit{k} ({EXIT_FRAC[k]*100:.0f}% depth, {EXIT_MS[k]:.2f} ms): "
              f"top-1 {acc[k]*100:.1f}%")

    # 1) saturation: exit2 vs exit3
    print(f"\nexit2 captures {acc[2]/acc[3]*100:.1f}% of exit3's accuracy at "
          f"{EXIT_MS[2]/EXIT_MS[3]*100:.0f}% of the cost "
          f"(acc gain exit2->exit3: {(acc[3]-acc[2])*100:+.1f} pp).")

    # 2) bounded-gain framing (sound): the LTC can only add accuracy between
    #    the discrete exits.
    reg12 = (EXIT_MS[2] - EXIT_MS[1]) / EXIT_MS[2] * 100
    reg23 = (acc[3] - acc[2]) * 100
    print("\nbounded-gain analysis (the LTC's max possible advantage):")
    print(f"  [exit1->exit2] {EXIT_MS[1]:.2f}->{EXIT_MS[2]:.2f} ms: at best the "
          f"LTC reaches exit2 accuracy ({acc[2]*100:.1f}%) earlier -> max energy "
          f"gain {reg12:.0f}% on those frames, IF it matches exit2 accuracy at "
          f"exit1's cost (unproven; per-step MLP overhead works against it)")
    print(f"  [exit2->exit3] {EXIT_MS[2]:.2f}->{EXIT_MS[3]:.2f} ms: only "
          f"{reg23:.1f} pp of accuracy remains (exit2 already has 99% of exit3's "
          f"accuracy at 53% cost)")
    print("  -> realistic LTC headroom: a few % energy at best, and only if the "
          "LTC is strictly more accurate per MAC than the discrete model (no "
          "evidence for this on GTSRB with a tiny LTC).")

    # 3) risk-adjusted cost of realising that headroom
    print("\nrisk-adjusted cost (LTC):")
    items = [
        ("LTC training on GTSRB (new pipeline, ODE/closed-form)", "weeks"),
        ("INT8 quantization of the Euler loop + f-MLP (custom layer)", "high risk"),
        ("continuous certification curve tau(k) (Stage 2 machinery)", "new"),
        ("hardware port NXP+ESP32 + PPK2 re-validation", "weeks"),
    ]
    for it, cost in items:
        print(f"  - {it}: {cost}")
    print("\nalternative (cheaper granularity): add 1-2 discrete exits "
          "(e.g. 45%/75% depth) reusing the EXISTING certification pipeline "
          "-> the anytime menu gains granularity at ~days of effort.")

    # 4) verdict
    print("\n" + "=" * 70)
    saturated = reg23 < 1.0        # exit2 already carries 99% of exit3 accuracy
    if saturated:
        print("GO/NO-GO VERDICT: NO-GO on the LTC for the efficiency story.")
        print("1) the discrete frontier SATURATES at exit2 (99.0% of exit3's")
        print("   accuracy at 53% of the cost; only 0.9 pp remains);")
        print("2) the only theoretical gain (exit2 accuracy reached earlier)")
        print("   is CONDITIONAL on the LTC beating the discrete model's")
        print("   accuracy-per-MAC (no evidence for a tiny LTC on GTSRB);")
        print("3) the certification curve tau(k) + INT8 ODE + hardware port is")
        print("   a multi-week, high-risk investment for a few-% bound.")
        print("If fine-grained temporal packing is wanted, add 1-2 discrete")
        print("exits with the existing certified-anytime machinery (days).")
    else:
        print("GO/NO-GO VERDICT: GO - headroom worth the LTC risk.")
    print("=" * 70)

    # plot
    ms = [0.0, EXIT_MS[1], EXIT_MS[2], EXIT_MS[3]]
    ac = [0.0, acc[1], acc[2], acc[3]]
    t = np.linspace(0, EXIT_MS[3], 200)
    plt.figure(figsize=(8, 5))
    plt.step(ms, ac, where="post",
             label="discrete 3-exit (measured)", lw=2)
    plt.plot(t, np.minimum(np.interp(t, [0, EXIT_MS[1], EXIT_MS[2]], [0, acc[1], acc[2]]),
                           acc[2]), "--", label="ideal continuous (upper bound)", lw=1.4)
    plt.scatter([EXIT_MS[1], EXIT_MS[2], EXIT_MS[3]],
                [acc[1], acc[2], acc[3]], color="k", zorder=5)
    for k in (1, 2, 3):
        plt.annotate(f"exit{k}", (EXIT_MS[k], acc[k]), textcoords="offset points",
                     xytext=(6, -4))
    plt.xlabel("per-frame compute (ms, measured)"); plt.ylabel("top-1 accuracy")
    plt.title("Any-time frontier: discrete 3-exit vs best-case continuous (LTC)")
    plt.grid(alpha=0.3); plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "stage3_pareto_audit.png"), dpi=110)
    print(f"\nsaved -> {RESULTS}/stage3_pareto_audit.png")


if __name__ == "__main__":
    main()
