# A_FEASIBILITY — Why key-recovery SCA is out of scope; activity-leakage is in

## The hard limit: PPK2 sampling rate

The nRF PPK2 (Ampere Meter mode) samples at **~10 kHz** (100 µs/sample) —
its maximum for continuous logging. Real profiled power-SCA on ML-KEM/ML-DSA
(the CHES/TCHES-grade attacks on Kyber/Dilithium NTT, 2023–2025) operates at
**100 MS/s–1 GS/s** oscilloscope rates to resolve the individual NTT
butterfly / modular-multiplication operations (~10–100 ns each).

An ML-KEM-768 encap is ~37.9 ms = ~5.7M cycles at 150 MHz. At 100 µs/sample
that's **~380 samples of aggregated current** — every key-dependent
transition is averaged away across millions of cycles. A CNN trained on such
traces has **no key-dependent signal to learn**; the averaged envelope
carries only operation/security-level information.

**Conclusion: key-recovery neural SCA is physically infeasible with the
PPK2.** We state this plainly rather than build a doomed pipeline.

## What the 10 kHz envelope CAN support (the reframed angle)

The aggregated power envelope at 100 µs/sample still encodes **macro-level
activity**:
- **Which operation** (keypair 32.6 ms / encap 37.9 ms / decap 45.4 ms for
  768) — distinguishable by duration AND envelope shape
- **Which security level** (512/768/1024 handshakes 72/116/175 ms; per-op
  durations scale ~1.6× per level) — monotonic and clearly separable
  (per-op energy 1.1/1.9/2.8 mJ keypair etc.)

This is a real **operational/activity leakage** observation: if an
eavesdropper with a cheap current probe can tell what crypto activity is
happening (e.g., when handshakes occur, at what security level), that's an
anonymity/privacy leak — and **countermeasures** (dummy ops, randomized
ordering, concurrent dummy computation) can be evaluated by whether they
flatten the CNN's discriminative signal.

## The honest framing for the thesis

- **In scope**: PPK2 + CNN *activity classification* (operation + security
  level identification), with countermeasure evaluation. Genuine AI × PQC
  security work, feasible on current hardware.
- **Out of scope / future work**: key-recovery SCA — requires an
  oscilloscope (≥100 MS/s) + trigger-aligned per-op capture with randomized
  keys. Documented here so the thesis doesn't overclaim.

## Verification of feasibility (done)

- Existing ML-KEM traces (512/768/1024) show per-handshake energy 4.14/6.63/
  9.76 mJ — monotonic, ~1.6× per level, cleanly separable at the envelope
  level (already measured in the eembc_style energy benchmark).
- The new ACTIVITY_MODE firmware adds segmentable per-op gaps + varied keys,
  so a CNN can be trained on labeled per-op bursts.
