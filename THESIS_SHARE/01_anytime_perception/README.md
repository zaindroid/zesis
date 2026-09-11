# 01 — Anytime Perception (the core)

**What:** the 3-exit GTSRB classifier (30/60/100% depth) with split-conformal
certified risk, interleaved with ML-KEM-768 on the MCXN947, and the three
exit policies (NAIVE/STATIC/ADAPTIVE) validated free-running with the PPK2.

- `report/` — deployment, policy-experiment, and free-running-energy reports
- `results/` — per-frame policy results + energy summaries
- raw energy traces: `../data/energy_ppk2/energy_interleaved_*`
- headline: adaptive policy **−14–15% time vs naive, no meaningful risk
  increase** (certified menu); free-running energy NAIVE 81.4 → ADAPTIVE
  77.6 → LEARNED 76.8 mJ.

Code: `codebase/projects/gtsrb_multiexit/` (+ `gtsrb_policy_singlecore/`,
`gtsrb_policy_freerun/`); training/certification: `codebase/training_archive/training/`.
