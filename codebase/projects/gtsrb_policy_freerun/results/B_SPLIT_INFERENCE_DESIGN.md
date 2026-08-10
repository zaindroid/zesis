# Option B — PQC-Protected Split Inference (design)

**Status:** Design complete; hardware measurement is the next step (feasible
with the proven PPK2 rig + free-running firmware pattern).

## What this is

**Privacy-preserving split inference**: the multi-exit GTSRB classifier runs
on the edge MCU, but the **intermediate features are encrypted** before
"transmission" to a cloud/second stage — protecting the input-derived
features from an eavesdropper. The cryptographic layer is a **hybrid
ML-KEM-768 + AES-GCM** construction (the NIST-recommended scheme):

1. **One-time**: ML-KEM-768 handshake establishes a 32-byte shared secret
   (the NIST-FIPS-203 way; the 116 ms cost is paid once per session, not per
   frame).
2. **Per frame**: the block3 feature tensor is **AES-256-GCM** encrypted
   (confidentiality + integrity via the tag) before it "leaves" the edge;
   the cloud leg decrypts and continues segB/segC.

## Why it's interesting for the thesis

- It quantifies the **real privacy overhead** of protecting AI intermediates
  with PQC on an MCU — crypto + perception + energy, end-to-end, on real
  hardware (most papers simulate or use PCs).
- It connects the two thesis halves: the perception pipeline (certified
  anytime) + the PQC layer (ML-KEM-768), in a *privacy* framing rather than
  a latency/energy one.
- The certified-anytime property is **orthogonal**: exits still respect
  their risk bounds; the crypto only protects the features between segments.

## Measured inputs (already have)

| piece | size/cost | source |
|---|---|---|
| block3 features (segA→segB) | **4,608 B** (12×12×32 int8) | ESP32 port header |
| block6 features (segB→segC) | 1,440 B (6×6×40 int8) | same |
| ML-KEM-768 handshake | 116 ms | mlkem_bench |
| AES-256-GCM @ ~4.6KB | ~10-50 µs (hardware AES or mcuxClAes) | SDK |
| per-frame perception | 0.8/1.24/2.34 ms (exit1/2/3) | freerun telemetry |

## The overhead story (honest prediction)

- **Per-frame crypto cost: negligible** (~10-50 µs AES-GCM on 4.6KB vs
  0.8-2.3 ms perception) — the privacy layer is essentially free *per frame*.
- **The real cost is the one-time ML-KEM handshake (116 ms)** — amortized
  over N frames: 116/N ms per frame. For a 100-frame session that's 1.16 ms
  extra (≈ 1 frame's worth of perception); for a 1000-frame session, 0.12 ms.
- **Energy**: AES-GCM ~2 mA × 30 µs ≈ negligible; the handshake ~6.6 mJ
  (measured) amortized similarly.

**The expected headline**: *hybrid-PQC split inference adds negligible
per-frame cost; the only measurable overhead is the one-time key agreement,
which amortizes away over a session — making PQC-protected AI intermediates
practically free on this MCU.*

## Hardware measurement plan (feasible, proven rig)

1. **Firmware**: add to the freerun project a `SPLIT_INFERENCE` mode where
   segA→segB handoff goes through: ML-KEM-768 key agreement (once) →
   AES-GCM encrypt(block3) → AES-GCM decrypt → segB. Measure per-frame
   crypto_us + total, with the PPK2 for energy.
2. **AES-GCM**: use mcuxClAes (SDK) or a compact AES-GCM; if the SDK's
   crypto lib is heavy, a small software AES-128-GCM suffices for the
   *privacy-layer overhead* measurement (the exact cipher matters less than
   the latency/energy profile).
3. **Capture**: three runs (baseline no-crypto / with-crypto, one-time
   handshake amortized / per-frame) — the same PPK2 free-running protocol.

## Files / status

- This design doc
- Next: confirm AES-GCM source (mcuxClAes vs software) + firmware build
