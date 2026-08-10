# Option A (reframed) — PPK2 + CNN Crypto-Activity Leakage Study

**Status:** firmware built (`mlkem_bench` ACTIVITY_MODE, 44,572 B); capture
+ CNN pending board connection.

## What this is (and isn't)

- **IS**: an AI × PQC security study where a CNN learns to identify **which
  ML-KEM operation (keypair/encap/decap) and security level (512/768/1024)
  is running** from the 10 kHz PPK2 power envelope alone — a real
  activity/operational leakage observation.
- **IS NOT**: key-recovery side-channel analysis. That requires a ≥100 MS/s
  oscilloscope (the literature operates at 100 MS/s–1 GS/s to resolve NTT
  butterflies); the PPK2's 10 kHz is ~4 orders of magnitude too coarse. See
  `A_FEASIBILITY.md`.

## The firmware (built, `debug/mlkem_bench_cm33_core0.bin`)

- 3 security levels (512/768/1024) × 60 reps × 3 ops = 540 segmentable bursts
- **10 ms inter-op gaps** → each op is a clearly separated burst at 100 µs/sample
- **Per-rep key variation** (counter-seeded operands) → CNN sees diverse data
- **Trigger GPIO P0_31 (Arduino D7)** toggles high during each op (optional
  wiring to PPK2 D0 for hardware alignment; the idle gaps alone suffice)
- Serial prints `op,<idx>,<keypair|encaps|decaps>` AFTER each burst and
  `level,<512|768|1024>` before each level — for host-side labeling of the
  PPK2 trace (no UART during measurement windows beyond the labeling lines)

## Capture procedure (user, PPK2 on J24)

1. Reconnect the FRDM-MCXN947 (probe + COM9 + PPK2 on J24)
2. Flash `debug/mlkem_bench_cm33_core0.bin`
3. **Disconnect serial** (or leave connected — the labeling lines are short
   and outside the measurement windows; for the cleanest trace, disconnect)
4. Arm PPK2 (Ampere Meter, ≥120 s window — 540 ops × (op + 10 ms gap),
   ~512: 60×3×(20+24+29ms) ≈ 13 s + gaps; 768 ≈ 20 s; 1024 ≈ 29 s; total
   ≈ 70 s of active + ~10 s gaps)
5. Reset → capture → save `ppk_activity_raw.csv`
6. Reconnect serial, read the labeling log → `activity_labels.txt`

## CNN pipeline (host side, after capture)

1. **Segment** the trace at the 10 ms idle gaps → per-op bursts
2. **Label** each burst from `activity_labels.txt` (op, level)
3. **Train/test split**: e.g., 80/20 by rep (different keys in train vs test)
4. **CNN**: 1-D CNN over the ~200–500 sample burst (the power envelope),
   softmax over 9 classes (3 ops × 3 levels), or two heads
   (op classifier + level classifier)
5. **Metrics**: per-class accuracy, confusion matrix, and the key question:
   *can the model tell which op is running? which security level?*
6. **Countermeasure eval**: re-capture with dummy ops inserted (or ops
   reordered) → does the CNN's accuracy drop? Quantifies the value of
   on-device activity obfuscation.

## Files

- `activity_capture.c` — the firmware (source)
- `CMakeLists.txt` — `-DMLKEM_ACTIVITY_MODE=ON` build option
- `debug/mlkem_bench_cm33_core0.bin` — built binary (44,572 B)
- `A_FEASIBILITY.md` — why key-recovery is out of scope, activity is in
