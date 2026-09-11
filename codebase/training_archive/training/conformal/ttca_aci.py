#!/usr/bin/env python3
"""Stage 1 (TTCA): Adaptive Conformal Inference with true multi-class
prediction SETS on the certified 3-exit model, over the 1000-frame shift seq.

Per exit k the prediction set is the textbook conformal set
    C_{t,k} = { y in classes : 1 - f_{t,k}(y) <= tau_k(alpha_{t,k}) }
with tau_k(alpha) the split-conformal quantile of non-conformity (1 - conf of
the true label) built from the CALIBRATION split (frozen protocol; the test
set is only ever evaluated, never used for tau).

Per-exit ACI (Gibbs & Candes 2021):  alpha_{t+1,k} = alpha_{t,k}
    + gamma * (alpha_target - err_{t,k}),  err = 1 - 1[Y_t in C_{t,k}].

Adaptive anytime menu: the controller uses the SHALLOWEST exit k whose
running alpha_{t,k} <= alpha_target (certified at the target level); if none,
it uses exit3 (full model, terminal). This is the certified menu made
adaptive: under shift exit1's alpha rises above target -> the menu drops to
deeper exits; when stable, alpha recovers -> early exits return."""
import numpy as np
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(__file__), "..")
RESULTS = os.path.join(ROOT, "results", "ttca")
os.makedirs(RESULTS, exist_ok=True)

ALPHA_TARGET = 0.05
GAMMA = 0.01
WINDOW = 50
EXIT_MS = {1: 0.80, 2: 1.24, 3: 2.34}
N_CLASSES = 43


def calibration_tau(nc_flat, alpha):
    """split-conformal quantile: ceil((n+1)(1-alpha))-th order statistic / n."""
    n = len(nc_flat)
    q = int(np.ceil((n + 1) * (1.0 - alpha)))
    q = min(max(q, 1), n)
    return float(np.sort(nc_flat)[q - 1])


def load_calibration_taus():
    """per-exit tau(alpha) linearized from the CALIBRATION split full
    softmax: tau_k(alpha) = tau_k(target) + slope_k * (alpha - target),
    with slope_k = d(tau)/d(alpha) < 0 (conformal: bigger alpha -> smaller
    sets). Only the calibration split is used (frozen protocol)."""
    sm = np.load(os.path.join(RESULTS, "calib_softmax.npy"))   # (n,3,43)
    labs = np.load(os.path.join(RESULTS, "calib_labels.npy"))
    taus, slopes = {}, {}
    for k in range(3):
        nc = 1.0 - sm[np.arange(len(labs)), k, labs]
        taus[k + 1] = calibration_tau(nc, ALPHA_TARGET)
        t_hi = calibration_tau(nc, max(0.005, ALPHA_TARGET - 0.02))
        t_lo = calibration_tau(nc, min(0.30, ALPHA_TARGET + 0.02))
        slopes[k + 1] = (t_lo - t_hi) / 0.04      # negative: tau drops with alpha
    return taus, slopes


def run_aci(seq_sm, labels, taus, alpha_target=ALPHA_TARGET, gamma=GAMMA):
    """per-exit ACI + adaptive menu. Returns per-frame: exit, coverage,
    set sizes, alpha tracks."""
    n = len(labels)
    alpha = {1: alpha_target, 2: alpha_target, 3: alpha_target}
    exits = np.zeros(n, dtype=int)
    covs = np.zeros(n, dtype=int)
    sizes = np.zeros(n, dtype=int)
    alphas = {k: np.zeros(n) for k in (1, 2, 3)}
    taus, slopes = taus  # (tau_at_target, slope<0)
    for t in range(n):
        sm = seq_sm[t]                        # (3, 43)
        sets = {}
        for k in (1, 2, 3):
            tau = float(np.clip(taus[k] + slopes[k] * (alpha[k] - alpha_target),
                                1e-6, 1.0))
            sets[k] = np.where(1.0 - sm[k - 1] <= tau)[0]
        # adaptive menu: shallowest exit whose alpha is at/below target
        # (band of +-2*gamma absorbs the natural ACI oscillation)
        chosen = next((k for k in (1, 2, 3)
                       if alpha[k] <= alpha_target + 2.0 * gamma), 3)
        Cc = sets[chosen]
        exits[t] = chosen
        covs[t] = int(labels[t] in Cc)
        sizes[t] = len(Cc)
        for k in (1, 2, 3):                   # ACI: update ALL exits after
            err = int(labels[t] not in sets[k])
            alpha[k] = float(np.clip(alpha[k] + gamma * (alpha_target - err),
                                     0.001, 0.99))
            alphas[k][t] = alpha[k]
    return exits, covs, sizes, alphas


def run_static(seq_sm, labels, taus):
    """static: fixed tau at alpha_target per exit, always the shallowest
    exit whose set is nonempty? -- use the SAME menu rule but with frozen
    alpha (no adaptation)."""
    n = len(labels)
    exits = np.zeros(n, dtype=int)
    covs = np.zeros(n, dtype=int)
    sizes = np.zeros(n, dtype=int)
    for t in range(n):
        sm = seq_sm[t]
        chosen = None
        for k in (1, 2, 3):
            C = np.where(1.0 - sm[k - 1] <= taus[k])[0]
            if chosen is None and len(C) > 0:
                chosen = k
        if chosen is None:
            chosen = 3
        Cc = np.where(1.0 - sm[chosen - 1] <= taus[chosen])[0]
        exits[t] = chosen
        covs[t] = int(labels[t] in Cc)
        sizes[t] = len(Cc)
    return exits, covs, sizes


def rolling(x, w=WINDOW):
    out = np.full(len(x), np.nan)
    cs = np.cumsum(x)
    for i in range(w - 1, len(x)):
        out[i] = (cs[i] - (cs[i - w] if i >= w else 0)) / w
    return out


def main():
    sm = np.load(os.path.join(RESULTS, "aci_softmax.npy"))      # (1000,3,43)
    labels = []
    with open(os.path.join(RESULTS, "aci_seq_1000.csv"), newline="") as f:
        for r in csv.DictReader(f):
            labels.append(int(r["label"]))
    labels = np.array(labels)
    taus, slopes = load_calibration_taus()
    print(f"static tau(0.05): exit1={taus[1]:.4f} exit2={taus[2]:.4f} exit3={taus[3]:.4f}")
    print(f"slopes d(tau)/d(alpha): exit1={slopes[1]:.3f} exit2={slopes[2]:.3f} exit3={slopes[3]:.3f}")

    ex_s, cov_s, size_s = run_static(sm, labels, taus)
    ex_a, cov_a, size_a, alphas = run_aci(sm, labels, (taus, slopes))

    rc_s, rc_a = rolling(cov_s), rolling(cov_a)
    seg = {"clean 0-299": (0, 300), "shift 300-699": (300, 700), "post 700-999": (700, 1000)}
    print("\n--- rolling set coverage (window 50) ---")
    print(f"{'segment':<18}{'static':>9}{'ACI':>9}")
    for name, (a, b) in seg.items():
        print(f"{name:<18}{np.nanmean(rc_s[a:b]):>9.3f}{np.nanmean(rc_a[a:b]):>9.3f}")
    print(f"{'ALL':<18}{np.nanmean(rc_s):>9.3f}{np.nanmean(rc_a):>9.3f}")

    print("\n--- exit distribution + compute ---")
    for name, (a, b) in seg.items():
        ds = np.bincount(ex_s[a:b], minlength=4)[1:]
        da = np.bincount(ex_a[a:b], minlength=4)[1:]
        print(f"{name:<18} static={ds} ACI={da}")
    ms_s = np.mean([EXIT_MS[e] for e in ex_s])
    ms_a = np.mean([EXIT_MS[e] for e in ex_a])
    print(f"mean compute: static {ms_s:.2f} ms/frame | ACI {ms_a:.2f} ms/frame "
          f"({(ms_a/ms_s-1)*100:+.1f}%)")
    print(f"mean set size: static {size_s.mean():.2f} | ACI {size_a.mean():.2f}")

    t = np.arange(len(labels))
    fig, ax = plt.subplots(3, 1, figsize=(10, 10))
    ax[0].plot(t, rc_s, label="static conformal", lw=1.2)
    ax[0].plot(t, rc_a, label="ACI (TTCA)", lw=1.2)
    ax[0].axhline(0.95, color="k", ls="--", lw=0.8)
    ax[0].axvline(300, color="r", ls=":", label="shift onset")
    ax[0].set_ylabel("rolling set coverage"); ax[0].legend(); ax[0].grid(alpha=0.3)
    for k in (1, 2, 3):
        ax[1].plot(t, alphas[k], label=f"exit{k}")
    ax[1].axhline(ALPHA_TARGET, color="k", ls="--")
    ax[1].axvline(300, color="r", ls=":")
    ax[1].set_ylabel("alpha_t"); ax[1].legend(); ax[1].grid(alpha=0.3)
    ax[2].plot(t, ex_s, label="static exit", lw=0.8, alpha=0.6)
    ax[2].plot(t, ex_a, label="ACI exit", lw=0.8, alpha=0.6)
    ax[2].axvline(300, color="r", ls=":")
    ax[2].set_ylabel("exit"); ax[2].set_xlabel("frame"); ax[2].legend(); ax[2].grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS, "ttca_stage1_plots.png"), dpi=110)

    with open(os.path.join(RESULTS, "ttca_stage1_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "label", "exit_static", "cov_static", "exit_aci",
                    "cov_aci", "size_aci", "alpha1", "alpha2", "alpha3"])
        for i in range(len(labels)):
            w.writerow([i, labels[i], ex_s[i], cov_s[i], ex_a[i], cov_a[i],
                        size_a[i], alphas[1][i], alphas[2][i], alphas[3][i]])
    print(f"\nsaved -> {RESULTS}/ttca_stage1_plots.png + ttca_stage1_summary.csv")


if __name__ == "__main__":
    main()
