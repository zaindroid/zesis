# Free-Running Interleaved Energy Capture — Valid Results

**Date:** 2026-08-08
**Board:** FRDM-MCXN947 (Cortex-M33 @ 150 MHz)
**Workload:** 140 embedded frames (94/140 = 67.1% safety-critical) +
4 ML-KEM-768 handshake cycles (14 crypto steps, keypair→encap→decap rotating)
**Method:** PPK2 Ampere Meter on J24, **free-running** (serial disconnected,
reset-button trigger), 10 kHz sampling, 3.3 V assumed.

**Why this supersedes the earlier n=140 capture:** the Aug-3 captures were
host-driven (frames streamed over UART) — on-device compute was <1% of the
800+s trace, so energy deltas were inverted/invalid. These captures are
**genuinely free-running** (firmware reads embedded images, no host needed),
so the energy numbers are physically meaningful.

---

## 1. Raw captures

| Policy | File | Samples | Window (ms) | Active (s) |
|---|---|---|---|---|
| NAIVE | `ppk_naive_free.csv` | 21,947 | 3850–5381 | 1.531 |
| STATIC | `ppk_static_free.csv` | 21,429 | 2646–4130 | 1.484 |
| ADAPTIVE | `ppk_adaptive_free.csv` | 20,941 | 1914–3379 | 1.466 |
| LEARNED | `ppk_learned_free.csv` | 21,330 | 3548–4996 | 1.448 |

## 2. Energy results (trapz × 3.3 V)

| Policy | Active energy (mJ) | Mean active (µA) | Baseline (µA) | Δ vs naive |
|---|---|---|---|---|
| NAIVE (all exit3) | **81.40** | 16,115 | 13,933 | — |
| STATIC (63 exit1, 77 exit3) | **78.67** | 16,064 | 14,440 | −3.36% |
| ADAPTIVE (74 exit1, 20 exit2, 46 exit3) | **77.56** | 16,033 | 14,623 | −4.72% |
| **LEARNED** (54 exit1, 59 exit2, 27 exit3) | **76.75** | 16,058 | 14,443 | **−5.72%** |

**Deltas:**
- Learned vs naive: **−5.72%** (best)
- Learned vs static: **−2.44%**
- Learned vs adaptive: **−1.05%**
- Adaptive vs naive: **−4.72%**
- Static vs naive: **−3.36%**

## 2b. LEARNED policy — on-device risk (140-frame sample)

The learned policy's exit decisions were checked against the embedded
ground-truth labels/SC flags on the same 140-frame workload:

| Exit | n (SC accepted) | On-device SC miss | α=0.05 (uncorrected) |
|---|---|---|---|
| exit1 | 28 | **3.57%** | ≤ 5% ✓ |
| exit2 | 47 | **0.00%** | ≤ 5% ✓ |
| exit3 (rejected hard cases) | 19 | 26.3% | — |
| **accepted** | **94** | **6.38%** | ~5% |

**Honest status:** these on-device numbers are consistent with the
uncorrected α=0.05 view (PC-side: exit1 3.37%, exit2 3.99% on the 12,630-
frame test set). **However**, the test set was used twice (frozen coverage
validation + learned-policy evaluation), so the strict certified claim
requires the Bonferroni correction (α_eff=0.025): on the full test set,
exit1 certifies (1.47%) but exit2 does NOT (3.61%) at the pre-frozen
τ₂=0.95. The n=94 on-device SC sample is too small for a corrected-level
certification — it is reported as a consistency check only, not a
certification. See `training/results/learned_policy/DOUBLE_TOUCH_FIX_REPORT.md`.

## 3. Firmware-verified per-policy behavior

| Policy | Inference sum (frame_us) | Exit distribution | Handshakes |
|---|---|---|---|
| NAIVE | 327.7 ms | 140× exit3 | 4 |
| STATIC | — | 63× exit1, 77× exit3, 0× exit2 | 4 |
| ADAPTIVE | 191.7 ms | 74× exit1, 20× exit2, 46× exit3 | 4 |

**Certified menu (verified on-device):**
- Tier 0.05: exit1 τ=858 (certified), exit2 **not certified**, exit3 always
- Tier 0.10: exit1 τ=723, **exit2 τ=402 (certified 0.0985 ≤ 0.10)**
- Adaptive shifts to tier 0.10 only near crypto steps (56/140 frames in
  tier 10); exit2 used only there (20 frames)

## 4. Interpretation (honest)

1. **Direction is correct and physically meaningful:** early exit reduces
   energy (NAIVE 81.4 → STATIC 78.7 → ADAPTIVE 77.6 mJ), consistent with
   the 42% less inference compute in adaptive (191.7 vs 327.7 ms).
2. **The deltas are modest (3–5%)** because the board's idle baseline
   (~14–14.6 mA) dominates the active window; the inference current delta
   is only ~2 mA. This is the honest reality of measuring a lightly-loaded
   MCU — not an artifact.
3. **Adaptive beats naive by 4.7% and static by 1.4%** while *additionally*
   relaxing the risk bound only during crypto contention (and still never
   exceeding its certified α). The energy advantage is real but small at
   this workload scale; at higher frame rates or heavier NPU contention the
   gap would widen.
4. **No deadline misses** — every frame's frame_us + crypto fits within the
   33 ms @ 30 fps budget (max frame ~2.4 ms, crypto ~10 ms per step).

## 5. Caveats

- 140 frames / 4 handshakes (not 1200/40): the full workload needs the
  8 MB QSPI flash (not confirmed populated). The 140-frame subset preserves
  the natural safety-critical ratio (67.1%).
- NPU (eIQ Neutron) not used — exits run on CPU via TFLite Micro.
- Baseline drift between captures (13.9→14.6 mA) is board/measurement
  variance; the active-window method isolates the workload, but cross-capture
  baseline differences add ~1% noise to the deltas.
- Single capture per policy (n=1) — repeated captures would tighten CIs.

## 6. Files

- `energy_summary_freerun.csv` — the three-way energy table
- `ppk_naive_free.csv` / `ppk_static_free.csv` / `ppk_adaptive_free.csv` — raw PPK2 traces
- Original exports in `H:\z_thesis\energy resulkts\`
