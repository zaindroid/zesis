# 04 — Security and Side Channels: Leakage, Obfuscation, Split-Inference Privacy, DTLS-CID Amortization

## Purpose

Five experiments examine the certified-anytime system from an attacker's
and a standards perspective: does the power envelope leak what the device
is doing (crypto activity, exit decisions)? Can that be defended
affordably? What does protecting intermediate perception features with PQC
actually cost? And what does the IETF DTLS Connection-ID standard buy a
battery-powered device once its handshake is post-quantum?

## Setup / Method (shared across the leakage experiments)

**Hardware:** FRDM-MCXN947 with a GPIO trigger (P0_31) wired to a PPK2
digital input, giving clean per-operation isolation in the power capture.
**Method (shared, both leakage experiments):** each captured pulse is
resampled to a 256-point power envelope, then **z-scored** (mean removed,
std normalized) so the classifier cannot use absolute current or duration
— it must learn the envelope *shape*. A **middle-50% ablation** additionally
removes the envelope edges (which correlate with duration) as a stronger
test. Random Forest + MLP classifiers (546/180 samples is too small for a
deep CNN), 5-fold cross-validation, compared against duration-only and
majority-class baselines.

## Results

### 4.1 Crypto-activity leakage — which ML-KEM operation is running?

550 pulses of ML-KEM-1024 keypair/encaps/decaps (546 usable after dropping
4 artifacts; labels 183/182/181, durations 51.0/57.2/66.7 ms distinguish
the three ops cleanly).

| classifier | CV accuracy |
|---|---|
| RF, full envelope (shape-only) | **99.8% ± 0.4%** |
| RF, middle-50% only (edges removed) | **99.8% ± 0.4%** |
| MLP, full envelope | **99.8% ± 0.4%** |
| duration-only baseline | 100% |
| majority-class baseline | 33.6% |

**Robustness sweep** (attacker's probe cost — envelope downsampled):

| samples/envelope | CV accuracy |
|---|---|
| 256 (10 kHz) | 99.8% |
| 128 / 64 / 32 | 99.8% each |
| 16 (~1.6 kHz effective) | 99.8% |

The leakage survives a **16× cheaper probe**. This is activity/operation
leakage (which op is running), *not* key-recovery side-channel analysis —
10 kHz is far too coarse to recover key material (which needs ≥100 MS/s);
stated explicitly, not implied.

### 4.2 Exit-decision leakage — does the power envelope reveal which exit ran?

180 isolated exit bursts (60 images × exit1/2/3; durations 0.62/0.24/0.92
ms distinguish the exits — note exit2's burst is shorter than exit1's
individual segment time due to how the burst boundaries were captured,
consistent within this dataset).

| classifier | CV accuracy |
|---|---|
| RF full shape (z-scored) | **98.3% ± 2.2%** |
| RF middle-50% only (edges removed) | **100.0%** |
| raw envelope | 97.2% |
| duration-only baseline | 100% |
| majority baseline | 33.3% |

Perfect confusion matrix (18/18/18) on a stratified 30% holdout. **This is
an attack on the certification itself**: the conformal risk bound is
designed to keep classifier *errors* below α, but the *exit decision* — the
observable outcome of that bound — leaks at ~98–100% even from shape alone,
with edges (duration) removed. An attacker with a cheap current probe can
determine whether the certified-anytime model was confident enough to stop
early.

### 4.3 Obfuscation defenses — can the leakage be hidden affordably?

**Leakage-aware scheduler (dummy crypto steps), trace-driven simulation on
real measured MCXN947 costs, 1230 frames / 123 real crypto steps, 33 ms
deadline:**

| ML-KEM level | policy | misses | +energy | crypto attacker | hidden |
|---|---|---|---|---|---|
| 512 (24.1ms/step < slot) | no_defense | 0 | — | 100% | 0% |
| 512 | fixed_dummy | 0 | +99.2% | 50.2% | 99% |
| 512 | **learned_obfusc** | **0** | **+50.4%** | **66.5%** | **50%** |
| 768 (38.7ms/step > slot) | no_defense | 6 | — | 100% | 0% |
| 768 | fixed_dummy | **13** | +99.2% | 50.2% | 99% |
| 768 | deadline_aware / learned_obfusc | 6 | +0% | 100% (no room to hide) | — |

**At ML-KEM-768 no dummy fits without a deadline miss — obfuscation is
infeasible at this security level.** This is a genuinely new coupling: the
scheduler's security-level choice (how strong a handshake to run)
determines whether activity-leakage defense is even *possible* — security
level ⇒ leakability ⇒ defensibility.

**Selective / probabilistic obfuscation** (a finer-grained follow-up
specifically targeting the infeasible 768 case): probabilistic p=0.3
(dummy after each real step with 30% probability) and exit1-selective
(dummy only when the next frame exits at the cheapest exit):

| ML-KEM-768, policy | misses | +energy | crypto attacker | hidden | exit leak |
|--------|--------|---------|-----------------|--------|-----------|
| no_defense | 6* | — | 100% | 0% | 98.3% |
| fixed_dummy (full) | **13** | +99% | 50% | 99% | 91.9% |
| **probabilistic p=0.3** | **9** | +32.5% | **75.5%** | 33% | 96.2% |
| **exit1-selective** | **10** | +48% | **67.6%** | 48% | 95.2% |

\* the 768 baseline already misses 6 deadlines before any defense is added
(a full 768 crypto step alone exceeds the 33 ms slot).

**p=0.3 cuts the crypto-activity attacker from 100%→75.5% at only +3
deadline misses over the already-stressed baseline** — the engineering
sweet spot between "no defense" and "infeasible full defense."
Exit1-selective reaches 67.6% by reusing anytime-exit headroom (dummy only
on frames with slack). **Honest boundary**: the exit-decision leak barely
moves (98.3%→95–96%) under either light-dummy policy — the compromise
protects crypto-activity privacy, not exit-decision privacy; that asymmetry
is itself a finding pointing at future work (exit-obfuscated envelopes).

### 4.4 Split-inference privacy overhead

Protecting the segA→segB intermediate feature tensor (4,608 bytes) with a
hybrid ML-KEM-768 + AES-128-GCM construction, release build (-O3), 200
frames, every AES-GCM tag verified (0 mismatches):

| component | time (ms) |
|---|---|
| ML-KEM-768 setup (once per session) | 29.4 |
| AES-GCM encrypt 4,608B | 61.3 |
| AES-GCM decrypt 4,608B | 61.3 |
| **per-frame privacy total (amortized, 1000 frames)** | **122.7** |
| perception exit3 (for comparison) | 2.34 |
| **privacy layer / perception (exit3)** | **52.4×** |

**Honest correction to an earlier prediction**: per-frame privacy is *not*
negligible in a software-only implementation — 122.7 ms/frame is 52× the
full perception cost, because the MCXN947's software AES-GCM (no hardware
AES engine wired into this build) costs ~13 µs/byte. The one-time ML-KEM-768
session setup (29.4 ms) is cheap and amortizes to <1 ms/frame — the
symmetric AES-GCM software implementation is the actual bottleneck, not
the PQC key agreement. A hardware-AES path (ELS-PKC, not measured here)
would plausibly be ~100× faster.

### 4.5 DTLS Connection-ID life-cycle energy amortization

24-hour state-machine model, using the measured PPK2 handshake energies
above: naive client (full PQC handshake every wake-up) vs CID client (one
handshake + symmetric AES-CCM-168 per wake-up). CR2032 battery (2430 J),
deep sleep 5 µA.

**Battery life on CR2032 (days), PQC 768+87 (1.87 mJ MCX / 18.24 mJ
ESP32-S3 per handshake; 2.76 µJ / 58.6 µJ per symmetric record):**

| Board | N (wake-ups/day) | Naive | CID | Gain |
|-------|------------------|-------|-----|------|
| MCXN947 | 24 (hourly) | 1812 | 1872 | +3% (sleep-dominated) |
| MCXN947 | 288 (5/min) | 1324 | 1872 | +41% |
| MCXN947 | 1440 (1/min) | 609 | 1870 | **+207% (3×)** |
| ESP32-S3 | 24 | 1401 | 1847 | +32% |
| ESP32-S3 | 288 | 370 | 1826 | +393% (5×) |
| ESP32-S3 | 1440 | **88** | **1740** | **+1880% (19×)** |

**Crossover** (wake-up rate where per-day handshake energy equals deep-sleep
energy — above this, handshake energy dominates and CID becomes critical):
MCX PQC 768+87 every 2.1 min (693 wake-ups/day); ESP32 PQC 768+87 every 20
min (71/day); ESP32 classical every 54 min.

## Analysis / Interpretation

1. **Both leakage channels are real, cheap to exploit, and survive
   downsampling**: a ~$50 10 kHz current probe identifies crypto operation
   type at 99.8% and the anytime exit decision at 98–100%, using envelope
   *shape* alone (not just duration/level). This is genuine operational
   privacy leakage, explicitly scoped as distinct from key-recovery SCA.
2. **Defense is a real engineering trade-off, not a solved problem**: full
   dummy-crypto obfuscation is infeasible at the thesis's own operating
   point (ML-KEM-768, 33 ms deadline) — there simply isn't slack to hide a
   dummy step. Probabilistic/exit-aware partial defenses recover a
   meaningful privacy gain (100%→~68–76% attacker accuracy) at bounded
   cost, but they protect crypto-activity privacy while leaving
   exit-decision privacy almost fully exposed — an honest, actionable
   asymmetry rather than a claimed complete fix.
3. **The DTLS Connection-ID amortization is real but not constant**: it is
   proportional to wake-up rate and per-handshake cost. At the classic
   hourly IoT duty cycle the device is sleep-dominated and CID buys only a
   few percent; at high-frequency wake-ups (1/min) it is a 3–19× battery-
   life feature, dramatically more so on the board with the more expensive
   handshake (ESP32-S3). This gives the IETF standards argument physical
   numbers and a quantified crossover point rather than a qualitative
   claim.
4. **Split-inference privacy is not free in software**: the finding that
   per-frame AES-GCM dominates cost (52× perception) redirects the
   thesis's privacy-layer design toward hardware acceleration or
   subsampled-feature encryption rather than assuming the PQC layer itself
   is the bottleneck.

## Raw data

- `raw_data/energy_ppk2/energy_mlkem1024_activity_trigger_mcxn947.csv` — raw PPK2 trace, crypto-activity leakage capture (§4.1)
- `raw_data/energy_ppk2/energy_exit_leakage_bursts_mcxn947.csv` — raw PPK2 trace, exit-decision leakage capture (§4.2)
- `raw_data/04_security_sidechannels/leakage_aware_summary.json` — machine-readable leakage-aware scheduler results (§4.3, dummy-crypto policies)
- `raw_data/04_security_sidechannels/selective_obfuscation_summary.json` — machine-readable selective/probabilistic obfuscation results (§4.3)
- `raw_data/serial_captures/serial_split_inference_mcxn947.txt` — split-inference raw serial capture (§4.4)
- `raw_data/04_security_sidechannels/cumulative_hourly.png` — DTLS-CID cumulative energy plot, hourly wake-ups (§4.5)
- `raw_data/03_classical_baseline/dtls_cid_daily_energy.csv` — machine-readable daily energy table backing §4.5
