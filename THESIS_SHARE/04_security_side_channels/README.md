# 04 — Security & Side Channels

- `activity_leakage/` — the power envelope reveals which ML-KEM op is running
  (RF 99.8%, robust to 16-point downsampling). Scope: activity, not key
  recovery (10 kHz too coarse — documented).
- `exit_leakage/` — the power envelope reveals the anytime EXIT decision
  (RF 98.3%, perfect 18/18/18 holdout) — an attack on the certification.
- `obfuscation/` — dummy-crypto defenses: full obfuscation infeasible at 768;
  **selective p=0.3 / exit1-aware** cut the attacker 100→68–76% at feasible
  cost (honest caveat: exit privacy stays exposed).
- `split_inference/` — ML-KEM-768 + AES-GCM on intermediate activations
  (per-frame 122.7 ms software AES — HW-AES scoped out honestly).
- `dtls_cid/` — DTLS Connection-ID battery amortization (up to **19×** on the
  ESP32 at 1/min wake-ups; honest duty-cycle crossover).

Raw: `../data/energy_ppk2/energy_mlkem1024_activity_trigger_*`,
`energy_exit_leakage_bursts_*`.
