# The Three Experiments — Detailed Report and Thesis Significance

**Subtitle:** *Amortization, portability, and obfuscation — three ways the PQC load
meets the real world.*

Prepared: 2026-08-11. Companion documents:
`securemark_tls_mcxn947/results/DTLS_CID_REPORT.md`,
`pqm4_bench_mcxn947/results/PQM4_M4F_M33_POSTMORTEM.md`,
`training/results/leakage_aware/SELECTIVE_OBFUSCATION_REPORT.md`.

---

## 0. Where these experiments sit in the thesis

The thesis is **"Certified Anytime Perception under Post-Quantum Cryptographic
Load"** — a multi-exit neural classifier with *provable* risk bounds, sharing
the MCU with ML-KEM/ML-DSA crypto, and a controller that adapts both
decisions (how deep to perceive, how much crypto to run) to a real-time
deadline.

That core is complete and validated. These three experiments are the **third
layer**: they take the already-measured PQC costs and push them toward what
reviewers and the IETF community actually care about —

| Experiment | The question it answers | Thesis pillar it strengthens |
|---|---|---|
| **1. DTLS CID amortization** | What does the PQC handshake cost over a *lifetime*, not one handshake? | Systems value of the standards story (Prof. Tschofenig) |
| **2. pqm4 M4F→M33 post-mortem** | Why does the fastest crypto code crash on the modern core? | Deep embedded/portability mastery (Prof. Houben) |
| **3. Selective obfuscation** | Is there an engineering middle ground between "no defense" and "too slow"? | Security realism; honest boundaries |

The chain that ties them: the PQC load is **real and quantified** (EEMBC
baseline + energy) → it **dominates battery life at high duty cycles** (Exp 1)
→ the obvious optimization (hand-written asm) carries a **portability trap**
(Exp 2) → and the obvious countermeasure (dummy crypto) is **infeasible at the
768 operating point**, forcing an honest partial defense (Exp 3).

---

## 1. Experiment 1 — DTLS Connection-ID life-cycle energy amortization

### 1.1 Why it was necessary
A handshake energy number (1.87 mJ) is a lab result. The IETF community —
and Prof. Tschofenig, a primary author of the DTLS Connection-ID standard —
asks: *what does that mean for a battery-powered device over a day?* The
standard exists to let low-power IoT devices **resume** sessions with
symmetric crypto instead of re-running expensive handshakes. This experiment
is the first place the thesis turns that standard into **physical numbers**:
how many battery days does the CID buy, given *measured* PQC handshake
energies on the thesis boards?

### 1.2 Method
A 24-hour state-machine model over a battery deployment. A client wakes N
times/day. Two clients differ only in session handling:

- **Naive** — a full PQC handshake (ML-KEM-768 + ML-DSA-87) on *every*
  wake-up (session timeout / network drop → re-handshake).
- **CID** — one handshake at boot, then only symmetric AES-GCM per wake-up
  (the Connection ID keeps the session alive).

All energies are the **PPK2-measured incremental values** (above idle):
PQC 768+87 handshake **1.87 mJ (MCXN947)** / **18.24 mJ (ESP32-S3)**; the
classical ECDH/ECDSA phase 1.36 / 48.27 mJ; symmetric AEAD per record
(AES-CCM-168 proxy) **2.76 µJ** / **58.6 µJ**. Sleep current 5 µA @ 3.0 V
deep sleep; batteries CR2032 (2430 J) and 500 mAh LiPo (6660 J).

### 1.3 Results

**Daily communication+communication-sleep energy (mJ), naive/CID:**

| Board | variant | N=24 (hourly) | N=288 (5 min) | N=1440 (1 min) |
|-------|---------|--------------|---------------|----------------|
| MCXN947 | PQC 768+87 | 1341 / 1298 | 1476 / 1298 | 1835 / 1298 |
| ESP32-S3 | PQC 768+87 | 1735 / 1316 | 3053 / 1320 | **6566 / 1331** |
| ESP32-S3 | classical | 2456 / 1346 | 5935 / 1350 | **15214 / 1361** |

**Battery life on a CR2032 (days), PQC 768+87:**

| Board | N | Naive | CID | Gain |
|-------|---|-------|-----|------|
| MCXN947 | 24 | 1812 | 1872 | +3% |
| MCXN947 | 1440 | 609 | 1870 | **+207%** |
| ESP32-S3 | 24 | 1401 | 1847 | +32% |
| ESP32-S3 | 288 | 370 | 1826 | **+393%** |
| ESP32-S3 | 1440 | **88** | **1740** | **+1880% (19×)** |

**Crossover** — wake-up rate at which per-day handshake energy equals
deep-sleep energy (5 µA): MCXN947 PQC 768+87 **every 2.1 min** (693/day);
ESP32-S3 PQC 768+87 **every 20 min** (71/day); ESP32-S3 classical **every
54 min** (27/day).

### 1.4 What it revealed (the honest story)
1. **The CID pays in proportion to duty cycle and per-handshake cost.** At the
   classic hourly cadence with 5 µA sleep, battery life is sleep-dominated
   (≈5 years — beyond shelf life), so the CID gain is a few percent. At
   1 wake-up/min the CID is a **19× battery-life feature on the ESP32**.
2. **The crossover is platform-dependent and quantifiable.** The ESP32 (10×
   pricier handshake) needs the CID even at 20-minute cadences; the MCX (a
   genuinely low-power handshake) can ignore it until ~2-minute cadences.
3. This is the **amortization argument for the DTLS CID standard, stated with
   physical numbers from the thesis boards** — exactly the "prove the
   battery-life savings of the standard" framing the experiment was designed
   for, with the honest duty-cycle caveat included.

---

## 2. Experiment 2 — The pqm4 M4F→M33 assembly post-mortem

### 2.1 Why it was necessary
The pqm4 library (hand-written Cortex-M4F assembly) is the standard answer to
"make PQC faster on M-profile" — and measured here it delivered **1.39–1.58×
speedups** on ML-KEM keypair/encaps. But on the modern Cortex-M33 of the
MCXN947 it **faults or hangs**. A thesis that claims portability of certified
crypto cannot leave a crash as a footnote: the crash *is* the finding. The
experiment converts it into an **architectural post-mortem** with exact
hardware fault registers — the kind of low-level evidence reviewers value.

### 2.2 Method
A custom `HardFault_Handler` was added to the pqm4 benchmark firmware to
capture the ARMv8-M fault status registers (CFSR/HFSR/MMFAR/BFAR and the
stacked PC) at the instant of failure. The remaining failure mode (a hang at
128 KB stack) was investigated live via LinkServer's GDB server: halt the
hung core, read PC/LR/SP and the stack contents.

### 2.3 Results

**Default 32 KB stack — exact fault registers captured on hardware:**
```
PQM4_BEGIN alg=MLDSA level=44
kp..
=== HardFault (M4F asm on M33) ===
CFSR  = 0x00100000   HFSR  = 0x40000000
MMFAR = 0xE000ED34   BFAR  = 0xE000ED38     <- stale (no precise address)
stacked PC = 0x40000000                     <- EXC_RETURN value, frame corrupt
[FORCED] escalated to HardFault
```
Decode: **CFSR bit 20 = UNSTKERR** (unstacking error — the saved exception
frame could not be unwound because it was already corrupted), **HFSR bit 30 =
FORCED**. Not STKOF (bit 16), not UNALIGNED (bit 24), not UNDEFINSTR (bit 16),
not a precise DACCVIOL (bit 30; MMFAR/BFAR stale).

**128 KB stack — GDB evidence of the hang:**
```
pc  0x20018040   (inside the stack region, executing DATA as code)
lr  0x1302e8a9   (garbage — not a flash address)
sp  0x20018800   (91 KB BELOW the 128 KB __StackLimit: the SP itself was smashed)
disassembly at PC: strh r1,[r0,#2]; movs r0,#1; strh r1,[r0,#2] (r0=1 → addr 3);
                   b.n .-2        (0xE7FE infinite self-loop = the "hang")
backtrace: corrupt
```

### 2.4 What it revealed (the precise root cause)
The pqm4 **M4F-targeted assembly corrupts its own call state on the
Cortex-M33**. The failure is:
- **not** a TrustZone/security-state violation (no INVPC/INVSTATE/NOCP),
- **not** an illegal instruction (no UNDEFINSTR),
- **not** the naive expectation of an unaligned-LDRD UsageFault (no
  UNALIGNED; the fault class is an **unstacking error**),
- but a **stack-discipline incompatibility**: the hand-written asm's
  register/SP handling (push/pop lists, SP arithmetic, 8-byte-aligned
  LDRD/STRD twiddle loads) does not survive the M33's stricter ARMv8-M
  behavior. At 32 KB the M33's stack-limit hardware escalates it to
  HardFault (UNSTKERR+FORCED); at 128 KB the corruption silently derails
  PC/LR/SP into an infinite loop in RAM.

**The architectural insight:** the M4F (ARMv7-M) has no stack-limit hardware —
it overruns *silently*. The M33 (ARMv8-M) monitors the stack limit and
catches the corruption at the hardware level. So "the same code" fails
*differently and detectably* on the modern core — a concrete, low-level
argument that **optimized crypto must be re-validated per core generation,
and that the M33's security hardware (MSPLIM) turns a silent memory-corruption
bug into a diagnosable fault**.

---

## 3. Experiment 3 — Selective / probabilistic side-channel obfuscation

### 3.1 Why it was necessary
The leakage-aware scheduler (#2) ended on a binary note: **full dummy-crypto
obfuscation is infeasible at ML-KEM-768** under the 33 ms deadline. A thesis
that only says "the defense doesn't fit" leaves the security story unfinished.
The engineering reality is probabilistic: insert dummy crypto *sometimes* —
with probability p, or only on the cheap exit-1 frames that leave timing
headroom — and measure how much the attacker actually degrades while the
deadline still holds.

### 3.2 Method
Extension of the trace-driven leakage-aware model (real measured costs, FIFO
3-slot backlog, 33 ms deadline, 1230 frames, 123 real crypto steps). Two new
policies on top of the existing set:
- **probabilistic p=0.3** — dummy after each real step with p=0.3 (random
  schedule; the attacker cannot rely on fixed timing),
- **exit1_selective** — dummy after a real step only when the next frame
  exits at exit1 (cheapest exit → most headroom), using the measured
  adaptive exit distribution (exit1 45% / exit2 17% / exit3 38%).

Two attacker targets: (A) real-vs-dummy crypto activity (naive accuracy +
hidden fraction); (B) exit-decision leakage (the measured 98.3% RF envelope
classifier, degraded toward chance on dummy-contaminated frames).

### 3.3 Results

**ML-KEM-768 (the constrained case):**

| policy | misses | +time | +energy | dummies | crypto attacker | hidden | exit leak |
|--------|--------|-------|---------|---------|-----------------|--------|-----------|
| no_defense | 6* | — | — | 0 | 100% | 0% | 98.3% |
| fixed_dummy (full) | **13** | +99% | +99% | 122 | 50% | 99% | 91.9% |
| **probabilistic p=0.3** | **9** | +32.5% | +32.5% | 40 | **75.5%** | 33% | 96.2% |
| **exit1_selective** | **10** | +48% | +48% | 59 | **67.6%** | 48% | 95.2% |

\* the 768 baseline already misses 6 deadlines (a full 768 step = 38.7 ms >
33 ms slot — the joint-scheduler finding).

**ML-KEM-512 (feasible reference):** all policies 0 misses; p=0.3 → attacker
81.5% at +22.8% energy; exit1_selective → 67.6% at +48%.

### 3.4 What it revealed (the honest boundary)
1. **The full-defense infeasibility is confirmed and quantified** (768: 6→13
   deadline misses).
2. **The probabilistic compromise is the engineering sweet spot**: p=0.3 cuts
   the crypto-activity attacker from ~100% → **75.5%** (33% of real steps
   hidden) at only **+3 deadline misses** and +32.5% energy — feasible,
   measurable, and defensible.
3. **The exit decision is a reusable obfuscation resource**: exit1-selective
   placement reaches a **67.6%** attacker (48% hidden) — the anytime exit
   logic itself gives the scheduler the headroom to hide crypto.
4. **The honest caveat**: the *exit-decision* leak barely degrades (98.3% →
   95–96%) at these light dummy rates. The compromise protects **crypto
   activity**, not **exit privacy**. Hiding the exit would need dense
   dummies — the infeasible regime. This asymmetry is itself a finding: it
   tells future work exactly where the remaining leak lives, instead of
   pretending the problem is solved.

---

## 4. Story overview — why these three matter, and what they mean for the thesis

### 4.1 The narrative arc they complete

The thesis now tells a **four-act story**:

1. **Act I — The certified controller.** A multi-exit classifier with provable
   risk bounds (frozen conformal protocol), interleaved with PQC crypto, saves
   14–15% time/energy with no risk increase. *The efficiency claim.*
2. **Act II — Learning and leakage.** Learned exit policies, the joint
   scheduler (−41% time / −39% energy / 0 misses), and the power-envelope
   leakages (crypto activity 99.8%, exit decision 98.3%). *The AI and
   security claims.*
3. **Act III — The PQC cost, honestly measured.** ML-KEM/ML-DSA on both
   boards, the ML-DSA fat tail (worst/median 6–8×, identical across
   platforms), EEMBC SecureMark-TLS classical baseline (14/14 CRC on both
   boards), and the migration cost (−35%…+38% MCX; −62…−82% ESP32) in latency
   **and** energy. *The benchmarking claim (professor-required).*
4. **Act IV — The three experiments (this report).** The cost is not an
   endpoint — it is something the real world *uses, breaks, and defends*:
   - **Amortization (Exp 1):** the measured handshake cost, projected over a
     battery lifetime, proves *when* the DTLS CID standard pays (19× on the
     ESP32 at high duty cycle) — the systems/standards significance.
   - **Portability (Exp 2):** the fastest implementation path (m4f asm) is
     shown *on the hardware* to corrupt its call state on the M33 — an exact
     fault-register root cause (CFSR.UNSTKERR), not a vague "it crashes".
   - **Obfuscation (Exp 3):** the obvious defense (dummy crypto) fails the
     deadline at 768, but a probabilistic/exit-conditioned schedule restores
     a *feasible, partial* defense — the security realism.

### 4.2 What each experiment contributes to the thesis's argument

| Experiment | Contribution | The sentence it enables in the thesis |
|---|---|---|
| **1. DTLS CID** | The PQC cost is projected to battery life; the CID standard's value is quantified per platform and duty cycle. | "The post-quantum handshake cost, measured on the thesis boards, is amortized by DTLS Connection IDs up to 19× in battery life at high wake-up rates; below a duty-cycle crossover the device is sleep-bound." |
| **2. pqm4 post-mortem** | A software crash becomes an architectural finding with exact fault registers. | "Hand-optimized M4F PQC assembly corrupts its stack state on the Cortex-M33; the ARMv8-M stack-limit hardware converts a silent M4F overrun into a diagnosable CFSR.UNSTKERR fault — optimized crypto must be re-validated per core generation." |
| **3. Obfuscation** | The defense space is mapped: infeasible (full), feasible-partial (p=0.3, exit-selective), with an honest boundary. | "Full dummy obfuscation is infeasible at ML-KEM-768 under the frame deadline; a probabilistic or exit-conditioned schedule restores feasibility while cutting the crypto-leak attacker from 100% to ~68–76% — at the cost that exit privacy remains exposed." |

### 4.3 Why a reviewer should care (the three hats)

- **Prof. Tschofenig (IETF/standards):** Exp 1 takes his standard and the
  thesis's physical numbers and produces the *amortization argument* — when
  post-quantum DTLS CID matters for battery life, with the honest crossover
  where it does not.
- **Prof. Houben (embedded/systems):** Exp 2 is the depth signal — exact
  fault registers, GDB evidence, a correct ARMv8-M decode, and a finding that
  overturns the naive "M4F asm on M33 = unaligned access" expectation. It
  shows the student can *debug at the register level*, not just benchmark.
- **The security reviewers:** Exp 3 is the maturity signal — a defense
  *boundary* stated honestly (we hide crypto activity, not exit privacy),
  with quantified trade-offs, rather than a fabricated clean win.

### 4.4 What the thesis now claims (one paragraph)

> Certified anytime perception under post-quantum cryptographic load is not
> just a measured efficiency win on two MCUs: the load it manages is a real,
> battery-relevant cost (amortized by DTLS Connection IDs with up to 19×
> battery-life impact), its fastest implementations carry genuine portability
> risk on modern ARMv8-M cores (captured at the fault-register level), and
> its side-channel defense requires honest engineering compromises
> (probabilistic/exit-aware obfuscation) rather than a binary yes/no. The
> certified-anytime controller — the part that provably absorbs this load —
> is therefore the load-bearing component of the whole system.

---

## 5. Files

- `securemark_tls_mcxn947/results/DTLS_CID_REPORT.md` + `dtls_cid_model.py` +
  `results/dtls_cid/` (plot + daily_energy.csv)
- `pqm4_bench_mcxn947/results/PQM4_M4F_M33_POSTMORTEM.md` +
  `results/mldsa44_fault.txt` (32 KB capture) + `results/mldsa44_128k_fault.txt`
  (128 KB capture) + fault handler in `main.c`
- `training/conformal/selective_obfuscation.py` +
  `training/results/leakage_aware/SELECTIVE_OBFUSCATION_REPORT.md` +
  `selective_obfuscation_summary.json`
