# On-Board Deployment Verification (Task 37, 38, 43)

Board: FRDM-MCXN947 (eIQ Neutron NPU), free-running (reset-button, no debugger
attached), fixed golden input (GTSRB test 00000.ppm, ROI (6,5,48,49), true
label 16), 100 iterations. Capture: `board_capture.txt`.

## Task 37 -- Golden-input check

**Bit-exact: FAIL. Decision-level: PASS.**

The board's `PRINTF("%d", (int)tensor->data.int8[i])` was not sign-extending
negative INT8 values correctly (fsl_debug_console's lightweight printf
printed them as their raw uint32 two's-complement bit pattern, e.g. `-24`
appeared as `4294967272`). **Fixed** in `main.cpp` (new `PrintInt8Array()`
helper that emits the sign explicitly) and reflashed; a fresh capture
confirms the board now prints correctly-signed values directly, and the
underlying numeric drift (below) is unchanged -- confirming it's a real,
deterministic NPU-side rounding difference and not an artifact of the old
print bug.

Once decoded, board INT8 tensors are **not bit-exact** against the PC
TFLite-interpreter reference, but are close (max drift 1-4 LSB per tensor,
growing slightly deeper into the network as expected from accumulation):

| tensor | max |diff| (LSB) |
|---|---|
| exit1_logits | 1 |
| block3_features (first 10) | 2 |
| exit2_logits | 3 |
| block6_features (first 10) | 4 |
| exit3_logits | 3 |

**Root cause investigated and resolved (driver/converter version skew ruled
out experimentally).** The boot-time warning originally printed by the
Neutron driver --

```
Microcode version mismatch! Neutron Driver is 3.1.1-0X447b3538 but model
converted with 3.1.3-0X1e788118. Runtime (driver, firmware) should be
aligned with converter
```

-- indicated the on-board Neutron driver (3.1.1) and the
`neutron-converter.exe` used to produce the segment `.tflite`/converted
graphs (3.1.3) were different microcode versions. The eIQ Neutron SDK
install at `H:\z_thesis\codebase\sdk\eiq_neutron_sdk` ships a
version-matched `libNeutronDriver.a`/`libNeutronFirmware.a` for the
`mcxn94x` target (3.1.3) alongside the same-version converter. These were
swapped into `gtsrb_multiexit`'s **project-local** vendored copy
(`frdmmcxn947_cm33_core0/mcxn/`, originals kept as `*.orig_3.1.1` for
rollback) -- this directory is private to this project, not the shared
`mcuxsdk` tree other NPU projects in this workspace build against, so the
change has zero blast radius outside `gtsrb_multiexit`. Rebuilt, reflashed,
recaptured.

Result: the "Microcode version mismatch" warning is now gone (confirming
the driver swap took effect), but **the numeric drift is byte-for-byte
identical to the mismatched-driver run** -- same values, same diffs, down
to the LSB. This experimentally rules out driver/converter version skew as
the cause. The actual source is simply that the Neutron NPU's fixed-point
kernels don't compute bit-identically to TFLite's reference CPU kernels for
INT8 conv/pooling -- a normal, expected characteristic of hardware
acceleration (different rounding/accumulation order), not a bug or
misconfiguration. This is a more defensible finding for the thesis than the
original hypothesis.

**Decision-level check (what actually matters for the pipeline): PASS.**
Despite the LSB-level drift, the **argmax prediction at every exit matches
both the PC reference and the true label (16)**:

| exit | board argmax | PC ref argmax | true label |
|---|---|---|---|
| exit1 | 16 | 16 | 16 |
| exit2 | 16 | 16 | 16 |
| exit3 | 16 | 16 | 16 |

Confidence values (steady-state, from the timing loop) are also well clear
of the conformal thresholds: exit1 conf=0.986 (>= TAU1=0.957, accept),
exit2 conf=0.999 (>= TAU2=0.926, accept), exit3 conf=1.000. So on this
golden input the chain would correctly early-exit at exit1.

**Recommendation:** treat the 1-4 LSB drift as a known, documented
NPU-vs-reference-kernel characteristic, not a pipeline bug -- the
quantization and NPU execution are functionally correct on-device (matching
predicted class + true label at every exit, confidence far above the
calibrated thresholds). The driver/converter version mismatch that was
originally suspected has been fixed (and is a genuine improvement worth
keeping -- runtime and toolchain are now aligned, as NXP recommends), but
was experimentally shown not to be the source of the drift.

## Task 38 -- Per-exit latency and arena usage (free-running, on-board)

### Arena usage (from `SEG*_Init()` boot log)

| segment | arena used | arena budget | utilization |
|---|---|---|---|
| segA | 30,632 B | 32,768 B | 93.5% |
| segB | 9,608 B | 16,384 B | 58.6% |
| segC | 5,796 B | 8,192 B | 70.8% |

### Latency (steady-state per-iteration timings, free-running loop, N=100, effectively constant across iterations)

| stage | time (us) |
|---|---|
| segA invoke | ~709 |
| copy1 (segA feat -> segB in) | ~23 |
| segB invoke | ~324 |
| copy2 (segB feat -> segC in) | ~8 |
| segC invoke | ~1007 |
| **measured-segment sum** | **~2071** |
| **wall total (incl. 2x CPU softmax + argmax)** | **~2253** |

CPU-side softmax/argmax overhead (2 calls, one after segA and one after
segB, not individually timed) accounts for the ~182us gap between the
summed segment times and the measured wall total -- non-negligible at
~8% of total latency, worth budgeting for in any real-time deployment.

**"What if we'd stopped here" latency** (what the certified-anytime pipeline
actually cares about):

| stopped at | latency |
|---|---|
| exit1 only | ~709 us |
| exit2 (segA + copy1 + segB) | ~1,056 us |
| exit3 (full chain) | ~2,253 us |

On this golden input, exit1's confidence (0.986) clears TAU1 (0.957), so
the certified pipeline would accept at exit1 -- a **3.2x latency reduction**
(709us vs 2,253us for the full chain) for this sample, consistent with the
thesis's core "certified-anytime" claim: most inputs don't need the full
backbone.

## Task 43 -- On-device conformal coverage validation (real NPU, not PC simulation)

Task 37 showed the NPU's INT8 output isn't bit-exact vs. the PC TFLite
simulation used to *calibrate* the conformal tau_k thresholds
(`conformal/calibrate.py`, entirely PC-side) and to *validate* them
(`conformal/coverage_validate.py`, also PC-side, run on the full 12,630-image
TEST split). This raised an obvious question: does the certified
miss-rate bound still hold when the model actually runs on the NPU?

**Method.** Added a UART batch-inference protocol to the firmware
(`main.cpp`, 'I' + 6912 raw INT8 bytes in, `R,pred1,conf1,pred2,conf2,
pred3,conf3` out over the same debug-console UART already used for
PRINTF; discovered and worked around a stuck-USB-endpoint issue identical
to the earlier SWD lockup -- fixed by a physical unplug/replug). Pulled a
stratified sample from the training lab's TEST split (never touched
before now, same discipline as `coverage_validate.py`): 1,230 images
(1,080 safety-critical, capped at 40/class across all 27 safety-critical
classes, plus 150 non-safety-critical for context; seed 20260728). Ran
every image through the real deployed chain (`tools/hw_validate/
run_hw_validate.py`) -- 1,230/1,230 succeeded, zero protocol desyncs,
618 ms/image (UART transfer-bound, not compute-bound). Applied the
existing PC-calibrated tau_k thresholds and recomputed achieved
safety-critical miss-rate among accepted samples
(`tools/hw_validate/compute_coverage.py`), exactly mirroring
`coverage_validate.py`'s methodology.

**Headline number, naively read: only 3/8 certifiable (exit, alpha)
combinations passed on real hardware**, vs. 7/8 on the PC's full-test-set
run. **That naive comparison is misleading, and the real finding is more
interesting.** To isolate cause, I pulled the PC TFLite-interpreter's
predictions for these *exact same 1,230 images* (not the full natural-
frequency test set) and recomputed the PC-simulated miss-rate on the
identical sample:

| exit | alpha | tau | n (hw) | miss (hw) | n (PC, same sample) | miss (PC, same sample) | miss (PC, full 12,630-image test) |
|---|---|---|---|---|---|---|---|
| exit1 | 0.05 | 0.957 | 83 | 0.0241 | 87 | 0.0230 | 0.0067 |
| exit1 | 0.10 | 0.918 | 138 | 0.0580 | 138 | 0.0580 | 0.0196 |
| exit2 | 0.01 | 0.994 | 601 | 0.0116 | 597 | 0.0117 | 0.0054 |
| exit2 | 0.05 | 0.926 | 799 | 0.0438 | 798 | 0.0489 | 0.0296 |
| exit2 | 0.10 | 0.725 | 940 | 0.1053 | 940 | 0.1053 | 0.0619 |
| exit3 | 0.01 | 0.999 | 782 | 0.0217 | 775 | 0.0245 | 0.0114 |
| exit3 | 0.05 | 0.944 | 932 | 0.0708 | 934 | 0.0707 | 0.0408 |
| exit3 | 0.10 | 0.628 | 1036 | 0.1197 | 1038 | 0.1233 | 0.0752 |

(full table: `tools/hw_validate/hw_coverage_validation_table.csv`)

**The hardware and PC-simulated miss-rates agree closely on the same
sample** (within ~0.005 in every row -- e.g. exit3/alpha=0.05: 0.0708
hardware vs 0.0707 PC-simulated on the identical 932/934 accepted images).
This confirms, at population scale, what the single-image golden-input
check already suggested: **the NPU's 1-4 LSB numerical drift essentially
never changes an accept/reject or classification decision** -- it is not
the cause of the higher miss-rate seen here.

**The real cause is the sampling design, not the hardware.** The
miss-rate gap is almost entirely between "stratified sample" (hw and PC
alike, ~0.02-0.12) and "PC full natural-frequency test set" (~0.005-0.075)
-- i.e. it shows up identically whether the classifier runs on the NPU or
in the PC simulator, so it isn't a hardware effect at all. My sample caps
every safety-critical class at 40 images regardless of how many exist in
the natural test set (e.g. class 16 has only 150 test images total vs.
class 2's 750), which deliberately over-represents rare classes relative
to their natural frequency. Rare classes have less training data and are
measurably harder, so a class-balanced sample shows a higher miss-rate
than an unweighted one drawn from the natural distribution -- exactly as
you'd expect, independent of any deployment question.

**Conclusions:**
1. **NPU vs. PC-simulation decision equivalence: confirmed at scale, not
   just on one golden image.** The 1-4 LSB drift from Task 37 does not
   propagate into materially different accept/reject or classification
   outcomes across 1,230 real images.
2. **The original PC-side headline result (Brief 3, natural-frequency
   full test set, 7/9 certifiable combos passing) remains the right
   number for "expected real-world risk under the natural class
   distribution."** This on-device run doesn't overturn it -- it
   corroborates that the deployed hardware reproduces that same PC-side
   behavior.
3. **Genuinely new and worth flagging for the thesis:** the conformal
   guarantee's margin shrinks substantially under a class-balanced
   (rather than natural-frequency) evaluation, because rare safety-critical
   classes are measurably harder. A safety framing arguably *should* care
   about this worst-case-per-class view, not just the aggregate
   natural-frequency rate -- this is a legitimate limitation to discuss,
   independent of anything about NPU deployment.

### Natural-frequency-reweighted on-device miss-rate (closes the gap above)

The stratified-sample miss-rates above (0.02-0.12) are not directly
comparable to the alpha targets or the PC full-test numbers, because every
safety-critical class was capped at 40 sampled images regardless of its
true test-set frequency (60-750/class). Since every safety-critical class
happens to have a natural count >= 40 (the minimum, classes 0/19/27, is
60), each class contributes exactly 40 images to the sample -- which makes
a clean Horvitz-Thompson-style reweighting possible without any new
hardware runs: treat each class's 40-image sample miss-rate as an unbiased
estimate of that class's true miss-rate, then weight each class's estimate
by its natural test-set prevalence
(`tools/hw_validate/compute_natural_weighted_coverage.py`):

| exit | alpha | tau | miss (raw stratified sample) | miss (natural-frequency reweighted) | passes alpha? |
|---|---|---|---|---|---|
| exit1 | 0.05 | 0.957 | 0.0241 | 0.0142 | PASS |
| exit1 | 0.10 | 0.918 | 0.0580 | 0.0355 | PASS |
| exit2 | 0.01 | 0.994 | 0.0116 | 0.0114 | FAIL (near-miss) |
| exit2 | 0.05 | 0.926 | 0.0438 | 0.0303 | PASS |
| exit2 | 0.10 | 0.725 | 0.1053 | 0.0719 | PASS |
| exit3 | 0.01 | 0.999 | 0.0217 | 0.0172 | FAIL |
| exit3 | 0.05 | 0.944 | 0.0708 | 0.0444 | PASS |
| exit3 | 0.10 | 0.628 | 0.1197 | 0.0716 | PASS |

**6 of 8 certifiable combinations pass on real hardware once the sample
composition is corrected for** (up from the naive/misleading 3/8 reading
of the raw stratified numbers). The two remaining failures are both the
strictest alpha=0.01 tier -- consistent with Brief 3's PC-side full-test
finding that alpha=0.01 was already the hardest tier to hit reliably
(exit3/alpha=0.01 failed there too, by a smaller 0.0114-vs-0.01 margin).
This is now a coherent story across every stage of validation (PC
simulation, PC-on-hardware-sample, hardware-with-natural-reweighting): the
alpha=0.05 and alpha=0.10 tiers are robust; alpha=0.01 is a genuine edge
case worth flagging as a limitation rather than a passing result, at every
stage, not just this one.

Raw data: `tools/hw_validate/hw_results.csv` (per-image on-device
predictions), `hw_coverage_validation_table.csv` (final table),
`pc_test_predictions_joined.csv` (PC reference joined to the same sample),
`hw_validate_manifest.csv` (sample definition, seed 20260728).
