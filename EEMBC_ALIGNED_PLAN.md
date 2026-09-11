# EEMBC-Aligned PQC Benchmarking — Analysis Plan (publishable + citable)

**Context:** The professor wants benchmarking in the style of EEMBC
(Embedded Microprocessor Benchmark Consortium) — specifically **SecureMark**,
**SecureMark-TLS**, and **ULPMark**. This document maps our measured data to
the official EEMBC methodology and defines the publishable analysis.

---

## 1. What EEMBC actually defines (authoritative, from the official repos)

### SecureMark-TLS (github.com/eembc/securemark-tls)
- **Purpose:** standardized efficiency measurement of cryptographic
  processing on IoT edge nodes (TLS handshake context).
- **Performance score formula (official):**
  ```
  SecureMark score = 1000 / ( Σ weighted_primitive_runtimes )
  ```
  (sum of weighted runtimes, inverted → decreasing time = increasing score,
  scaled by 1000 to integer range)
- **Workload:** 14-phase TLS handshake profile:
  AES128-ECB encrypt (144/224/320B), AES128-CCM enc/dec, ECDH p256r1,
  ECDSA p256r1 sign/verify, SHA256 (23/57/384/4224B), data tx.
- **Two modes:**
  - *Self-hosted (free):* runs on any board, computes **performance score**.
  - *Official harness (licensed):* adds energy score + validation + upload.
- **SecureMark V2** (github.com/eembc/securemark-v2): adds light/medium/heavy
  crypto profiles, TRNG, secure-boot (RSA-2048/4096), and **PQC-capable
  cipher suites** — the PQC-relevant extension.

### ULPMark (EEMBC's ultra-low-power suite)
- ULPMark-CP (compute), ULPMark-PP (peripheral), ULPMark-CM (CoreMark-ARM),
  ULPMark-ML (ML inference).
- **Core metric: energy efficiency** — work per µJ (e.g., inferences/µJ,
  operations/µJ). Higher is better.

---

## 2. Mapping our measured data to EEMBC metrics

| EEMBC benchmark | EEMBC metric | Our measured equivalent | Status |
|---|---|---|---|
| SecureMark-TLS | Σ(weighted primitive time)⁻¹×1000 | ML-KEM-768 handshake time (kp+enc+dec) | ✅ have latency |
| SecureMark-TLS | energy per handshake | PPK2 energy per handshake (clean 6.6 mJ, m4f 3.0 mJ) | ✅ have energy |
| SecureMark V2 PQC | PQC cipher-suite handshake perf | ML-KEM-512/768/1024 + ML-DSA-44/65/87 latency | ✅ have |
| ULPMark-ML | inferences/µJ | multi-exit perception energy under crypto load | ✅ have |
| SecureMark | crypto primitive efficiency | clean vs m4f (1.39-1.58× speedup, −26% energy) | ✅ have |

---

## 3. The publishable deliverables (what to build)

### D1. SecureMark-TLS score on our boards (official, citable)
- **Run the official self-hosted SecureMark-TLS firmware** on the FRDM-MCXN947
  (it's free, no license needed for the performance score).
- This yields an **official SecureMark-TLS score** on our exact board —
  directly comparable to EEMBC's published score tables
  (eembc.org/securemark/scores.php).
- **Citation:** EEMBC. *SecureMark-TLS Benchmark.* eembc.org, GitHub
  repo eembc/securemark-tls.

### D2. PQC-specific SecureMark-style score (our contribution)
Since EEMBC's official SecureMark-TLS uses *classical* crypto (AES/ECDH/ECDSA),
we define a **PQC-extension score** following the same formula:
```
PQC-SecureMark score = 1000 / (Σ weighted PQC primitive times)
```
with the 14-phase structure replaced by the PQC handshake phases:
ML-KEM kp/enc/dec + ML-DSA kp/sign/verify. Compute per config:
- clean vs m4f-optimized
- per security level (512/768/1024, 44/65/87)
- per board (MCXN947, ESP32-S3)

### D3. ULPMark-style energy scores
```
ULPMark-PQC score = operations / µJ
```
from our PPK2 data:
- ML-KEM-768 clean: 6.63 mJ/handshake → 151 ops/J
- ML-KEM-768 m4f: 3.0 mJ (kp+enc) → 333 ops/J (partial, decap faults)
- Plus the interleaved perception+crypto energy (ULPMark-ML-style)

### D4. The EEMBC-format report
A single report in EEMBC's table style:
- methodology (config, iterations, harness, energy setup)
- per-primitive tables (latency, energy, memory)
- score tables (SecureMark-style, ULPMark-style)
- cross-board comparison (MCXN947 vs ESP32-S3)
- optimization comparison (clean vs m4f)

---

## 4. Methodology rigor (EEMBC-compliant)

| EEMBC requirement | Our compliance |
|---|---|
| Fixed workload/inputs | ✅ frozen 1230-frame + 41-handshake protocol |
| Documented clock/config | ✅ 150MHz M33, documented |
| Repetitions for statistics | ✅ 100 reps ML-KEM, 2000+ ML-DSA sign |
| Calibrated energy measurement | ✅ PPK2 Ampere Meter, 10kHz, J24 |
| Free-running (no debugger) | ✅ reset-triggered |
| Separate performance vs energy | ✅ DWT cycles vs PPK2 energy |

---

## 5. Citations (for the thesis)

1. EEMBC. *SecureMark-TLS Benchmark* (GitHub: eembc/securemark-tls).
2. EEMBC. *SecureMark V2* (GitHub: eembc/securemark-v2).
3. EEMBC. *ULPMark Benchmark Suite* (eembc.org/ulpmark).
4. EEMBC. *SecureMark Score Tables* (eembc.org/securemark/scores.php).
5. PQClean. *PQClean: Clean implementations of post-quantum algorithms*
   (github.com/PQClean/PQClean).
6. pqm4. *pqm4: Post-quantum crypto library for ARM Cortex-M4*
   (github.com/mupq/pqm4).

---

## 6. Next steps (in priority order)

1. **Run official SecureMark-TLS self-hosted** on MCXN947 → official score
2. **Compute PQC-SecureMark scores** (D2) from existing latency data
3. **Compute ULPMark-style energy scores** (D3) from PPK2 data
4. **Write the EEMBC-format report** (D4) merging everything
5. **(Optional) SecureMark V2 with PQC cipher suite** if the repo supports it

---

*Note: the official energy score requires the licensed EEMBC harness; the
performance score is freely reproducible with the self-hosted firmware. Our
PPK2 energy data is methodologically equivalent (calibrated current probe,
free-running) and citable as "EEMBC-style energy measurement."*
