# Split summary (FROZEN FOUR-WAY protocol)

Seed: `20260728`  |  track fractions train/cal/margin = `0.75/0.15/0.1`

| split | images | classes present | role |
|---|---|---|---|
| train | 29369 | 43 | checkpoint selection (train + internal val) |
| calibration | 5850 | 43 | conformal tau_k only |
| margin_val | 3990 | 43 | margin derivation only |
| test | (quarantined, unchanged) | 43 | final single touch only |

test.csv was defined once and is QUARANTINED: this script never writes it; its SHA-256 in checksums.sha256 is frozen. The full protocol is documented in FROZEN_PROTOCOL.md -- do not re-run coverage_validate.py except as the final, single, frozen test touch.

All splits are TRACK-aware (never frame-level) and stratified per class -- see the module docstring and data/splits/safety_critical.md.
