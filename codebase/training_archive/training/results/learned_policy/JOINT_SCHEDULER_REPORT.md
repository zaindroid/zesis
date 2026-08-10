# Option C — Joint Learned Scheduler (security level + exit under deadline/energy)

**Date:** 2026-08-08
**Status:** Trace-driven simulation on REAL measured MCXN947 costs; firmware
port is the natural next step (deferred — see caveats).

---

## 1. The joint decision

A certified-anytime system under real crypto+perception load must decide TWO
things per unit of work:
1. **Which ML-KEM security level** to use for the next handshake (512/768/1024)
2. **Which perception exit** to stop at per frame (1/2/3), subject to the
   certified SC-risk bound

The **joint learned policy** makes both decisions from data. The exit side
uses the learned isotonic risk curves (calibration-trained, as before). The
security-level side uses the *measured* per-level costs — the analytically
learned rule: **pick the highest level whose per-step cost fits the deadline
slot** (this is exactly the "principled heuristic" the RL-gate simulations
found for crypto selection — the joint result shows it compounds with learned
exits).

## 2. Real measured inputs (MCXN947, all from benchmark/hardware runs)

| input | value |
|---|---|
| exit1 / exit2 / exit3 latency | 0.80 / 1.24 / 2.34 ms |
| ML-KEM-512 / 768 / 1024 handshake | 72.2 / 116.0 / 174.9 ms |
| per-step (handshake/3) | 24.1 / 38.7 / 58.3 ms |
| per-handshake energy | 4.20 / 6.63 / 9.76 mJ |
| frame deadline (@30fps) | 33 ms |
| crypto step frequency | 1 per 10 frames |
| FIFO frame buffer | 3 slots (bounded backlog model) |

## 3. Results (trace-driven, 12,630 test frames + 3,990 margin_val)

| policy | security level | total time (test) | energy (test) | deadline misses | early-exit |
|---|---|---|---|---|---|
| naive | 768 fixed | 78.4 s | 3382 mJ | 70 | 0% |
| static | 768 fixed | 69.6 s | 3206 mJ | 70 | 45% |
| adaptive | 768 fixed | 67.9 s | 3173 mJ | 70 | 56% |
| **learned (joint)** | **512 under tight slot** | **45.9 s** | **2079 mJ** | **0** | **85%** |

**Deltas (learned vs naive, test):**
- **Time: −41.4%** (45.9 vs 78.4 s)
- **Energy: −38.5%** (2079 vs 3382 mJ)
- **Deadline misses: 70 → 0**
- **SC risk unchanged**: exit1 3.37%, exit2 3.99% (the learned exit curves;
  same as the standalone learned-policy result, since the exit decisions are
  identical — the security-level change does not affect perception risk)

## 4. Why the joint policy wins so much more than exit-only

Exit-only learning (Option A of the earlier work) cut energy ~8% by raising
early-exit from 45%→85%. The joint policy cuts **39%** — the dominant effect
is the **security-level decision**: ML-KEM-768's per-step cost (38.7 ms)
exceeds the 33 ms frame slot, causing systematic backlog/misses; dropping to
512 (24.1 ms/step) fits the slot, eliminating all 70 misses and cutting the
crypto time ~1.6× and crypto energy ~1.6× (512 handshake 4.20 vs 768 6.63 mJ).

**This is the FIX-2 reconciliation made concrete**: the crypto-selection side
is low-dimensional with measured costs, so the learned rule *is* the
principled heuristic (drop to the level that fits); the exit side is
high-dimensional, so learned risk curves add value. The joint policy
correctly applies each approach where it pays — and the compound effect is
much larger than either alone.

## 5. Honest caveats

- **Trace-driven, not hardware-measured**: the scheduler was simulated on
  real per-component costs; the full joint policy in firmware (with dynamic
  per-handshake level selection) is the natural next step. The exit side is
  already hardware-validated (POLICY_LEARNED, PPK2: 76.75 mJ); the
  security-level-switching side is not yet on-device.
- **The 512-drop is a security-level downgrade**: under a hard 33 ms/frame
  deadline, the learned rule always picks 512 — this trades security level
  for deadline adherence. Whether that's acceptable is a policy decision
  (the thesis's "security-level selection under battery/deadline" framing).
  A variant that keeps 768 and accepts the 70 misses is the status quo
  (naive/static/adaptive).
- **Double-touch of the test set**: the exit-side numbers reuse the test
  evaluation already reported (shared test set). The joint result is a
  *simulation over the same held-out predictions*, not a new test touch —
  but it does not claim fresh single-touch validity either. The security-
  level rule is derived from measured costs (not test data), so it is not
  test-fitted; the exit curves remain calibration-trained.
- **Simple backlog model**: a 3-slot FIFO buffer is an assumption; real
  schedulers may drop-oldest instead. The *ranking* of policies is robust
  (fixed-768 always misses, 512 never does).

## 6. Files

- `results/learned_policy/joint_scheduler_summary.csv` — full table
- `conformal/joint_scheduler.py` — the simulator (all costs from real
  measurements, documented in the header)
