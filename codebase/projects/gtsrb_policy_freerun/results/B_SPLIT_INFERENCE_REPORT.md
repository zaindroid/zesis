# Option B — PQC-Protected Split Inference: Measured Overhead

**Date:** 2026-08-09
**Hardware:** FRDM-MCXN947 (Cortex-M33 @150MHz), release build (-O3)
**Construction:** hybrid ML-KEM-768 + AES-128-GCM (NIST-recommended)

## What was measured

Protecting the segA→segB intermediate feature tensor (block3, **4,608 bytes**)
with the hybrid PQC privacy layer:
- **One-time session setup**: ML-KEM-768 keypair + encap + decap
  (establishes the shared secret — the NIST FIPS-203 key agreement)
- **Per-frame**: AES-128-GCM encrypt + decrypt of the 4,608B feature tensor
  (confidentiality + integrity via tag)

Firmware: `split_inference.cpp` (SPLIT_INFERENCE mode), free-running,
200 frames, every tag verified (`ok=0` all frames, 0 mismatches).

## Results (release -O3)

| component | time (ms) |
|---|---|
| ML-KEM-768 setup (kp+enc+dec) | **29.4** |
| AES-GCM encrypt 4,608B | 61.3 |
| AES-GCM decrypt 4,608B | 61.3 |
| **per-frame privacy total** | **122.7** |

| amortization | per-frame total (ms) |
|---|---|
| 1 frame | 152.1 |
| 10 frames | 125.6 |
| 100 frames | 123.0 |
| 1000 frames | 122.7 |

## Comparison vs perception

| | time (ms) |
|---|---|
| perception exit1 | 0.80 |
| perception exit2 | 1.24 |
| perception exit3 | 2.34 |
| **privacy layer (enc+dec)** | **122.7** |
| privacy / perception (exit3) | **52.4×** |

## The honest finding (important correction)

**My earlier prediction ("per-frame privacy is negligible") was WRONG for a
software-only implementation.** The compact table-free AES-GCM on the M33
at -O3 costs **~13 µs/byte** → 122.7 ms per 4,608B frame, which is **52× the
full perception cost**. This is a real, measurable overhead — NOT free.

The reason: the MCXN947 has **no hardware AES in the measurement path used**
(ELS-PKC is not wired into this build); the benchmark uses a compact software
AES-GCM. A hardware-AES (ELS-PKC / mcuxClAead) implementation would be
~100× faster (~1 ms), making the privacy layer genuinely negligible — but
that's a *different* (hardware-accelerated) result, which we did NOT measure.

## Honest implications for the thesis

1. **Software-only PQC split inference is expensive**: 122.7 ms/frame × 30fps
   = 3.7 s/frame — the privacy layer dominates. Not viable without hardware
   AES or batching.
2. **The one-time ML-KEM-768 handshake is cheap**: 29.4 ms once per session,
   amortizing to <1 ms/frame over 30+ frames — the PQC key agreement is NOT
   the bottleneck; the AES-GCM software implementation is.
3. **The interesting thesis angle**: the *hybrid construction* is sound (tag
   verifies, no mismatches); the cost is dominated by the symmetric part in
   software. This motivates (a) hardware-AES acceleration, or (b) encrypting
   only a downsampled/subsampled feature subset.

## Caveats (honest)

- Software AES-GCM only (no ELS-PKC hardware AES) — the 61 ms/op reflects
  the compact reference, not the platform's best.
- Fixed IV/AAD (per-frame IV would add ~0 cost, same AES ops).
- -O3 release; debug (-O0) was 265 ms/op (4× slower) — reported for
  completeness.

## Files
- `split_inference.cpp`, `common/split_aes_gcm.{c,h}`
- `results/split_inference_raw.txt` (debug), `results/split_inference_raw_release.txt` (release)
- CMake: `-DSPLIT_INFERENCE=ON` + `flash_release` preset
