# 05 — Learned / Adaptive AI angles

- `learned_exit/` — PAVA risk-curve exit policy + the Bonferroni double-touch
  fix (exit2 NOT certified at α=0.05 — honest downgrade).
- `joint_scheduler/` — learned security-level + exit scheduler:
  **−41% time, −39% energy, 0 deadline misses** vs naive (70).
- `ttca/` — **Test-Time Conformal Adaptation** (Stage-1, on the certified
  3-exit model): static coverage collapses 95.8→48.6% under an abrupt shift;
  **ACI restores ~94% at +3.3% compute** (reactive lag and set-inflation
  mechanism documented). Stage-3 Pareto audit: **NO-GO on the LTC**
  (exit2 = 99% of exit3 accuracy at 53% cost). Independently verified by
  `codebase/.../conformal/verify_ttca.py`.
