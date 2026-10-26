# Security experiments — attack, defense, and the slack gate

Board pair: FRDM-MCXN947 (Cortex-M33 @ 150 MHz, eIQ Neutron NPU) on COM9, and
ESP32-S3 (Xtensa LX7 @ 240 MHz, CPU-only inference) on COM17.
All crypto costs at `-O2` (wolfSSL 5.9.2 native), all timing on-device.

This run tested the reframed thesis before anything is built on it: is the
attack real, does the defense address the leak that was actually measured, and
does the certified-anytime slack cover the countermeasure's cost.

**Headline: the attack is real but it is a timing leak, not a power leak — and
that changes the countermeasure from envelope randomisation to duration
equalisation. The slack gate then comes out opposite on the two boards.**

---

## 1. Literature gate — the idea is not as open as it looked

The reframe proposed "fund obfuscation from slack" as novel. The search says the
*principle* is published, at a different layer:

- **Fine-Grained Instruction Reordering** (arXiv 2107.11336) explicitly uses
  "the time between operand availability of critical instructions (**slack**)"
  to build obfuscated schedules at ~96% of baseline performance. It is a
  microarchitectural out-of-order scheduling result, not a task-level deadline
  result — but the word and the mechanism are the same.
- **CF'26 poster, "Security and Cost Trade-offs of Side-Channel Countermeasures
  for AES Software on RISC-V SoCs"** already measures masking vs software/hardware
  noise vs **Secure-Ibex (data-independent timing + random dummy instruction
  insertion)** on execution time, code size, **power and energy**. That is the
  cost/security trade-off frame on embedded silicon, for AES.
- Hiding by dummy operations is established: Secure-Ibex, and a 2025 Kyber work
  using redundant modular ops + LFSR pseudo-random scheduling inside the
  primitive.
- A CASCADE 2025 result attacks *shuffled* ML-KEM and shows the countermeasure
  raises attack time from 30 s to ~3 h rather than preventing it.

**What survives as ours:** not "obfuscation is affordable from slack", but the
*dependency* — that a **certified** safety mechanism is what makes the freed
slack safe to spend, on PQC rather than AES, evaluated against an adaptive
attacker. The novelty claim must be narrowed to that. "Nobody has the
distributions" was too strong.

---

## 2. The attack re-audit — the 99.8% is a stopwatch, not a side channel

The activity-leakage result claimed ~99.8% operation identification from the
power envelope. Re-audited here with the splits a real attacker faces.

| Method | Accuracy |
|---|---|
| **duration only** (1 scalar, no power trace) | **0.998** |
| shape, RandomForest, random 5-fold (the original claim) | 0.993 |
| shape, RandomForest, **temporal 70/30** | 1.000 |
| shape, RandomForest, blocked 5-fold | 0.993 |
| shape, MLP (standardised features) | 0.9964 |
| duration, MLP | **1.000** |
| z-scored shape (amplitude removed) | 0.991 |
| middle-50% of the envelope | 0.993 |

Durations by class on the MCXN947:

| class | mean | min | max |
|---|---|---|---|
| keypair | 50.58 ms | 12.30 (warm-up outlier) | **51.40** |
| encapsulate | 57.27 ms | **54.30** | 57.70 |
| decapsulate | 67.61 ms | **66.70** | 210.90 |

**There is zero cross-class duration overlap — 0 of 1,098 samples.** keypair's
maximum (51.40) sits below encapsulate's minimum (54.30), which sits below
decapsulate's minimum (66.70). A single scalar separates all three classes
perfectly, and a duration-only MLP scores 1.000.

**Conclusion.** The headline result is reproducible, but it is a **duration**
leak, not a power-envelope leak. The classifier adds nothing over a stopwatch;
the ML pipeline in the original experiment was measuring operation time by a
roundabout route. This is a materially different — and much weaker — claim than
"a learned observer reads cryptographic activity from the power trace".

Three consequences:

1. The **AI-as-adversary framing has no attack to justify it** at this
   measurement bandwidth. If the thesis keeps an ML attacker, it needs a leak
   that is not duration — which requires equal-duration operations and much
   higher bandwidth than a PPK2.
2. The **countermeasure must change.** Randomising the power envelope while the
   operation still takes 50.6 / 57.3 / 67.6 ms hides nothing. The defense that
   addresses the measured leak is **duration equalisation** — pad every
   operation to the slowest one, which the literature already lists as
   "fixed-time execution".
3. The **threat model survives but must be restated.** Timing is exactly what a
   fault-injection attacker needs to trigger a glitch, so "the observer learns
   when signing happens" remains a real consequence. It just isn't an ML result.

---

## 3. Per-exit perception cost, both boards (measured)

The ESP32 figure in `policy_results_esp32_*.csv` was dismissed earlier in this
project as "UART-transfer-dominated". **That was wrong.** Measuring the same
three segments on-device with `esp_timer` (`seg_timing.cpp`, 30 iterations)
reproduces those numbers almost exactly:

| Exit | ESP32-S3 (measured, on-device) |
|---|---|
| exit1 (segA) | **459.3 ms** |
| exit2 (segA+segB) | 574.8 ms |
| exit3 (segA+segB+segC) | **1005.4 ms** |
| exit3 − exit1 | **546.1 ms** |

Against the MCXN947 (NPU), where the same exits cost 0.80 / 1.24 / 2.34 ms.

The ESP32-S3 runs the identical INT8 models through TFLite Micro CPU kernels
with the arenas in external PSRAM, at `-Os`, with no NPU. It is ~430x slower per
frame than the M33 + Neutron path. The UART was never the bottleneck.

---

## 4. The slack gate — opposite answers on the two boards

Does the certified early-exit slack cover the countermeasure cost?

| Board | perception (exit3) | exit slack/frame | KEM-768 handshake | padding cost | verdict |
|---|---|---|---|---|---|
| MCXN947 (NPU) | 2.34 ms = 7.1% of a 33 ms frame | 1.54 ms | 21.62 ms | 3.10 ms | **not needed** |
| ESP32-S3 (CPU) | 1005.4 ms | **546.1 ms** | 21.62 ms | 3.10 ms | **load-bearing** |

- On the **NPU board**, perception consumes 7% of the frame and the crypto
  handshake is amortised to ~2.2 ms/frame. The frame uses ~4.5 ms of 33 ms.
  There is ~28 ms of idle budget, so **certified early exit is not what makes
  the countermeasure affordable — the idle budget is.** The architecture has no
  work to do here.
- On the **CPU board**, perception at full depth takes longer than a one-second
  frame. Early exit frees **546 ms/frame**, which is ~176x the padding cost of a
  KEM handshake and ~9x an ML-DSA-65 sign mean. **Here the architecture is
  load-bearing: without early exit there is no room.**

That is a cross-platform result in its own right: the certified-anytime
mechanism is unnecessary on the accelerator board and essential on the
CPU-only board. It gives the reframed thesis a defensible reason to exist —
but only on the CPU-class target, which is not where the perception work was
originally done.

---

## 5. Deadline-aware hiding, re-run at September costs

The original `leakage_aware_scheduler.py` used a **115.97 ms** ML-KEM-768
handshake and reported the deadline-aware allocation **infeasible at level 768**.
September's `-O2` wolfSSL harness measured the same handshake at **21.62 ms**
(5.4x cheaper). Re-run with the corrected threat model (duration equalisation)
and the corrected costs, over 1230 frames at a 33 ms deadline with one crypto
operation every 10 frames:

| level | policy | misses | ops padded | energy | overhead | attacker accuracy |
|---|---|---|---|---|---|---|
| 512 | no_defense | 0 | 0/123 | 516.6 mJ | 0.0% | 1.000 |
| 512 | always_pad | 0 | 123/123 | 543.2 mJ | 5.2% | 0.333 |
| 512 | **deadline_aware** | **0** | 82/123 | 543.2 mJ | 5.2% | **0.333** |
| 768 | no_defense | 0 | 0/123 | 815.5 mJ | 0.0% | 1.000 |
| 768 | **deadline_aware** | **0** | 81/123 | 854.1 mJ | **4.7%** | **0.341** |
| 1024 | no_defense | 0 | 0/123 | 1200.5 mJ | 0.0% | 1.000 |
| 1024 | **deadline_aware** | **0** | 81/123 | 1246.4 mJ | 3.8% | **0.341** |

**The old negative result has flipped.** Deadline-aware duration equalisation
now reaches near-chance attacker accuracy (0.333-0.341) at **+3.8-5.2% energy
with zero deadline misses** at every security level — where the previous run
could not place a single dummy operation at level 768.

The honest reading, though, is the one from §4: this is now *easy*, because
crypto got cheap and the frame has slack. The interesting regime is a tight
deadline or a heavy perception load — i.e. the ESP32-S3, not the M33.

---

## 6. What this does to the reframed thesis

| Claim | Status after this run |
|---|---|
| Feasible: PQC on a modern MCU is nearly free | **Holds** (September benchmarks) |
| Leaky: a *learned* observer reads crypto activity | **Weakens to a timing leak**; no ML needed |
| Hardened: deadline-aware hiding closes it at measured cost | **Holds, and is now cheap** at -O2 costs |
| The certified anytime slack is what funds the defense | **Board-dependent**: load-bearing on ESP32-S3, not needed on MCXN947 |

The architecture is coherent, but its load-bearing premise is **conditional on
the target**, and the AI's role in the attack has evaporated at this bandwidth.
Both are fixable, but neither by more of the same measurements:

- To keep an ML attacker, the leak must be non-duration: capture
  equal-duration operations (same op, key varying) and test whether anything
  survives once duration is controlled. If nothing does, the honest thesis
  statement is "at microcontroller power-monitor bandwidth, cryptographic
  activity leaks through timing, and that is all."
- To keep the certified-anytime dependency, the work must be positioned on the
  CPU-class board where perception dominates the frame — and said plainly, since
  that is the opposite of where the perception results were produced.

---

## 7. Caveats

- The re-audit is **one capture, one board, one algorithm** (ML-KEM-1024 only —
  the firmware compiled only that level, so the "3 levels" labelling in the
  original capture is misleading). Cross-session and cross-board leakage
  generalisation is untested and cannot be tested from this data.
- The 33 ms frame budget is an assumption. On the ESP32-S3 it is meaningless —
  that board cannot run these models at 30 fps at all.
- The slack-gate model amortises one KEM operation every 10 frames and uses the
  expected perception cost, not the worst-case frame. A worst-case-frame model
  would tighten the NXP verdict further and loosen the ESP32 one.
- The E4 re-run models energy as proportional to time at fixed power, using the
  measured 6.63 mJ/handshake at 768 as the anchor. It is a model, not a PPK2
  capture; the padding overhead is an estimate.
- No PPK2 was connected during this run, so no new power traces were taken; all
  energy numbers are from the earlier September captures.
- The prior-art check was two web searches, not a systematic review. It found
  enough to invalidate the strong novelty claim; it is not sufficient to
  establish that the narrowed claim is novel.

---

## 8. Artifacts

| Path | Contents |
|---|---|
| `mlkem_bench/results/activity/reaudit_leakage.py`, `REAUDIT.json` | the duration-leak re-audit |
| `mlkem_bench/results/activity/slack_gate.py`, `SLACK_GATE.json` | the slack gate, both boards |
| `training_archive/training/conformal/e4_duration_hiding.py` | deadline-aware hiding re-run |
| `training_archive/training/results/leakage_aware/E4_DURATION_HIDING.json` | its results |
| `gtsrb_multiexit_esp32s3/main/seg_timing.cpp` | ESP32-S3 per-exit timing firmware |
| `gtsrb_multiexit_esp32s3/results/esp32_seg_timing.txt` | ESP32-S3 measured exit costs |
