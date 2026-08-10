# Unified Experiment Report — Certified Anytime Perception under Post-Quantum Load

**Date:** 2026-08-10
**Scope:** Merges the original C/A/B studies with the five follow-up experiments (#1-#5) into one coherent thesis narrative.
**Thesis line:** *Certified anytime perception on an edge MCU that also runs post-quantum crypto — risk, latency, and leakage all certified; scheduler, defense, and limits all measured.*

---

## 1. The thesis arc (one paragraph)

A tiny robot chip must (a) classify traffic signs with a certified-anytime
multi-exit network (stop early when the conformal risk bound allows) and
(b) run post-quantum crypto (ML-KEM/ML-DSA). The thesis asks: what really
happens when these share the same 150MHz core, the same 33ms deadline, and
the same battery? The experiments below turn that into measured, honest
answers: the scheduler should adapt (C), the crypto leaks activity through
power (A), encrypting AI intermediates has a real software cost (B), and the
new work shows the crypto latency tail is certifiable (1), the security level
decides whether leakage defense is possible (2), and the certification itself
leaks its exit decisions through power (3), with hardware limits documented
(4) and voltage robustness measured (5).

---

## 2. Foundations (measured before this work)

- **Certified anytime perception**: 3-exit MobileNetV1-style GTSRB classifier,
  split-conformal risk certification per exit (τ thresholds, frozen protocol,
  6/9 certified tiers), INT8 per-exit tflite, NPU-backed.
- **PQC benchmarks**: ML-KEM-512/768/1024 + ML-DSA-44/65/87 on MCXN947,
  ESP32-S3, and Zephyr; EEMBC-style tables; energy model (0.382 nJ/cycle).
- **Key data assets**: 12,000+ ML-DSA sign latency samples; 4,000+ ML-KEM
  op samples; per-exit perception costs; PPK2 energy methodology (J24).

---

## 3. Option C — Joint learned scheduler (scheduling)

**Result: −41% time, −39% energy, 70→0 deadline misses, certified risk held.**

A trace-driven scheduler on real measured costs picks the ML-KEM security
level AND the exit per frame under the 33ms deadline. Learned security-level
rule (drop to 512 under deadline pressure) + learned exit risk curves
(calibration-only) beat naive/static/adaptive. Clean protocol (margin_val,
test single-touch). *File: JOINT_SCHEDULER_REPORT.md*

## 4. Option A — Crypto-activity leakage (security)

**Result: a 10kHz PPK2 current probe identifies ML-KEM ops at 99.8% CV, even
from 16 samples/envelope.**

A learned classifier reads *which crypto operation* runs from the power
envelope — cheap, no calibration. This is operational/activity leakage
(privacy/anonymity), NOT key recovery (that needs an oscilloscope; documented
in A_FEASIBILITY.md). *File: ACTIVITY_LEAKAGE_REPORT.md*

## 5. Option B — PQC-protected split inference (privacy)

**Result: ML-KEM-768+AES-128-GCM on the 4,608B feature tensor costs
122.7ms/frame (software AES) + 29.4ms one-time key agreement — 52x the
perception cost, tag-verified.**

Honest correction of the initial "negligible" prediction: software-only AES
is the bottleneck, not the PQC. Hardware AES (ELS-PKC) would be ~100x faster
but requires a 468-file integration (Exp #4). *File: B_SPLIT_INFERENCE_REPORT.md*

---

## 6. New Experiment #1 — Conformal LATENCY certificates (headline)

**Result: ML-DSA signing cannot be certified within a 33ms frame on the NXP
— certified τ at α=0.05 is 3.8-7x the deadline.**

The same distribution-free conformal machinery that certifies *perception
risk* now certifies *crypto latency*: P(latency ≤ τ) ≥ 1−α, from 12,000
measured samples. Empirical exceed rates match α exactly (method validated).
Cross-platform NXP/ESP32 = 1.26x. The 7x fat tail becomes a *rigorous
real-time constraint*, motivating batch/async signing. *File:
CONFORMAL_LATENCY_REPORT.md*

## 7. New Experiment #2 — Leakage-aware scheduling (headline)

**Result: leak obfuscation requires crypto slack; the security level decides
whether defense is even possible.**

At ML-KEM-512 (24ms step < 33ms slot): learned dummy insertion hides 50% of
real steps for +50% energy, zero deadline misses. At ML-KEM-768 (38.7ms >
slot): infeasible — no room to hide. **New coupling: security level ⇒
leakability ⇒ defensibility** — the scheduler's strength choice is a privacy
decision, not just time/energy. *File: LEAKAGE_AWARE_REPORT.md*

## 8. New Experiment #3 — Exit-decision leakage (headline)

**Result: the power envelope reveals WHICH exit the certified-anytime model
took, at 98-100% accuracy (shape-only, edges removed).**

An attacker learns *when the model was confident enough to stop* — an attack
on the certification itself, not the crypto. Connects A (crypto leaks) and
the perception side: both schedules and confidence regimes leak through
power. *File: EXIT_LEAKAGE_REPORT.md*

## 9. New Experiment #4 — Hardware-AES scoping (honest limit)

**Result: the MCXN947 has no standalone hardware-AES driver** (CASPER is
ECC/RSA only; ELS-PKC = 468 files). Documented as future work; the software
122.7ms baseline stands as the honest number. *File: D4_HW_AES_SCOPING.md*

## 10. New Experiment #5 — Voltage robustness (supporting, NOT headline)

**Result: crypto latency is constant across 3.3V→2.2V (18.46s, ±0.01s);
energy drops 34% (972→646 mJ).**

Honest role: a *validity check*, not a contribution. It answers the question
"does battery sag break the certified latency?" with a measured NO — the #1
certificates hold across the operating range. Secondary observation (energy
−34% at low V) is close to textbook P=V·I. Positioned as robustness evidence.
*File: E5_VOLTAGE_SWEEP_REPORT.md*

---

## 11. Contribution table

| # | Contribution | Novelty | Role |
|---|---|---|---|
| C | Joint learned security-level + exit scheduler | strong | headline (scheduling) |
| A | Crypto-activity leakage from 10kHz power | strong | headline (security) |
| B | PQC split-inference software cost | moderate | headline (privacy) |
| 1 | Conformal latency certificates for fat-tailed crypto | **high** | headline |
| 2 | Security-level ⇒ defensibility coupling | **high** | headline |
| 3 | Exit-decision leakage (attack on certification) | **high** | headline |
| 4 | Hardware-AES scoping (honest limit) | low | documentation |
| 5 | Voltage robustness of certified latency | low | supporting |

## 12. The unified story

> Put a certified-anytime AI and PQC crypto on a 150MHz battery chip, and the
> measured reality is: **(C)** adapt both crypto strength and exit point to
> the deadline; **(1)** the crypto tail is certifiable but excludes
> per-frame ML-DSA; **(A/3)** both crypto activity AND exit decisions leak
> through power at ~99-100%; **(2)** the security level you choose decides
> whether you can defend that leakage; **(B)** encrypting AI features in
> software is correct but expensive (hardware AES = future work); **(5)** the
> certificates hold across the battery range. Risk, latency, and leakage are
> all certified — and the limits are honestly measured.

## 13. Honest limitations
- #3/#A: 180/546-sample datasets (small but clean CV).
- #2: simulation on measured costs (dummy energy modeled as matched).
- #1: single-board, -O3/debug mixes documented.
- #4/#5: hardware limits and supporting status stated plainly.
