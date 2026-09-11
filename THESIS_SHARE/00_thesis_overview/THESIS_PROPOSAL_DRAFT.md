# Thesis Proposal Draft — Problem, Methodology, Evaluation

**Working title**: *Certified Anytime Perception under Post-Quantum
Cryptographic Load*

This draft is built entirely from work already completed and measured on
real hardware (see `MILESTONE_REPORT.md` and the per-experiment reports it
references). Every place literature needs to be cited is marked
`[CITE: ...]`. **`RELATED_WORK_CANDIDATES.md` (same folder) now has real,
verified-to-exist papers for most of these** — found via web search,
metadata-checked but not fully read by me, so treat as a strong starting
point to verify yourself, not a final bibliography. The most important one
to read first: Jazbec et al., "Fast yet Safe: Early-Exiting with Risk
Control" (NeurIPS 2024) — it does something close to this thesis's
certification approach, so understanding exactly what it does and doesn't
cover is the key to a sharp novelty claim.

---

## 1. Problem Statement

Embedded and edge devices are increasingly expected to do two things at
once that individually already stress constrained hardware:

1. **Real-time, safety-relevant perception** — e.g. vision-based
   classification or detection for robotics, ADAS-adjacent, or autonomous
   systems, where a late or wrong answer has real consequences and the
   device typically has a small NPU/accelerator and a tight power/latency
   budget.
2. **Post-quantum secure communication** — the NIST PQC standardization
   (ML-KEM finalized as FIPS 203 in 2024) means devices that need
   long-term confidentiality must migrate from classical ECDH to
   lattice-based key exchange, which is measurably heavier: on a
   Cortex-M33-class MCU, a full ML-KEM-768 handshake costs on the order of
   100+ ms — multiple frame-periods' worth of a 30 fps perception budget.

**The problem**: when a single constrained device must do both, how
should it allocate its limited compute so that (a) the security property
(a completed, correct key exchange) is not indefinitely delayed, and (b)
the perception system's *safety* property — not just its throughput — is
preserved even when it has to run cheaper/faster under load, with a
*provable*, not just empirical, bound on the risk that shortcut
introduces.

Naive strategies fail on one side or the other:
- **Always run perception at full depth/accuracy, regardless of system
  state**: if crypto and perception contend for the same execution
  resource (a shared core, or the security handshake's own latency
  budget), perception either misses its deadline during a handshake, or
  the system has to serialize the two, delaying secure communication.
- **Statically shrink perception to "leave room" for crypto**: wastes
  accuracy during the (likely majority of) time when no handshake is in
  flight, and provides no formal guarantee about how much risk the
  shortcut introduces — a fixed shallow model either has no certified
  bound at all, or an overly conservative one chosen for the worst case.

This thesis argues for a third approach: a perception system that can
**certifiably** trade depth for speed at inference time (an "anytime"
property, with each stopping point carrying a statistically valid risk
bound), combined with a policy that **adapts which certified operating
point to use based on the system's current cryptographic load** — getting
the throughput benefit of shrinking under load without losing the formal
guarantee that motivated certification in the first place.

`[CITE: motivate the PQC migration urgency and timeline — NIST FIPS
203/204/205 finalization, industry migration pressure]`
`[CITE: motivate real-time/safety-critical embedded perception constraints
— a paper characterizing latency/accuracy/power tradeoffs for
vision-on-microcontroller deployments]`

---

## 2. Research Questions

- **RQ1 (contention characterization)**: On a representative NPU-equipped
  microcontroller, does a PQC key-exchange workload create measurable
  *resource* contention (memory bandwidth, execution unit sharing) with
  concurrent NPU-based perception inference, or is any interference purely
  *temporal/scheduling* in nature (i.e. one workload occupying a core the
  other needs, with no effect on the other's raw execution speed when it
  does run)?
- **RQ2 (certified deployment fidelity)**: Do finite-sample conformal risk
  bounds calibrated on a PC-side simulation of a quantized multi-exit
  model continue to hold when the model is deployed and run on real NPU
  hardware, given that NPU and reference-CPU INT8 kernels are not
  guaranteed to be bit-exact?
- **RQ3 (adaptive certified policy value)**: In a deployment scenario
  where crypto and perception genuinely share an execution resource, does
  a policy that adapts its certified operating point (exit depth / risk
  tier) to current cryptographic load reduce total system completion time
  relative to (a) an uncertified naive baseline and (b) a certified but
  load-unaware static policy, without a statistically significant increase
  in achieved risk?

---

## 3. Solution Methodology

All of the following has been implemented and measured on a physical
FRDM-MCXN947 board (dual Cortex-M33 + eIQ Neutron NPU), not simulated.

### 3.1 Feasibility characterization (answers groundwork for RQ1)

A six-question feasibility sprint measuring, free-running (no attached
debugger — debugger-attached timing was found to distort results and is
never used for a reported number) on real silicon:
- Toolchain/NPU bring-up and INT8 op-whitelist characterization for the
  target NPU (`[CITE: Bamberg et al., "eIQ Neutron: Redefining Edge-AI
  Inference with Integrated NPU and Compiler Innovations", arXiv:2509.14388
  — this is a direct description of the exact NPU used here; see
  RELATED_WORK_CANDIDATES.md]`).
- ML-KEM-512/768/1024 primitive costs at each security level (keypair,
  encapsulation, decapsulation), using the PQClean reference (portable,
  not assembly-optimized) implementation
  (`[CITE: Kannwischer et al., "Improving Software Quality in Cryptography
  Standardization Projects" (PQClean, EuroS&P Workshops 2022) for the
  reference implementation; Kannwischer, Rijneveld, Schwabe, Stoffelen,
  "pqm4: Testing and Benchmarking NIST PQC on ARM Cortex-M4" (2019) as the
  optimized-assembly alternative, to justify choosing the portable
  reference and note the gap]`).
- CPU-CPU and NPU-vs-crypto resource contention, measured directly by
  running the NPU inference workload on one core while independently
  loading the other core with continuous ML-KEM-768 operations, comparing
  cycle-identical timing with the crypto core idle vs. active.
- Multi-exit segmentation overhead (fixed NPU dispatch cost vs.
  requantization-copy cost per exit boundary), decomposed via cross-validated
  build/algorithm variants to separate hardware floor from optimizable
  software cost.

**Result relevant to RQ1**: zero measurable NPU-vs-crypto resource
contention on this dual-core target (Δ ≈ 0.001-0.003% in both an initial
toy-model test and a repeat using the actual deployed multi-exit model,
Section 3.4). Multi-exit overhead is small (~29 μs fixed dispatch cost per
boundary in a release build), making a several-exit design practical.

### 3.2 Certified multi-exit perception pipeline (answers RQ2)

- **Data**: GTSRB (43-class traffic sign classification), track-aware
  stratified train/calibration/test split (avoiding the same physical
  sign leaking across splits), with a safety-critical subset defined via
  GTSDB's prohibitory+danger superclass taxonomy (27 of 43 classes)
  (`[CITE: GTSRB benchmark paper; GTSDB benchmark paper — Houben et al.,
  since GTSDB's taxonomy is used directly here]`).
- **Architecture**: MobileNet-v1-flavored backbone restricted to an
  NPU-whitelisted operator set (no attention/SE-blocks/in-graph softmax),
  three exit heads at 30/60/100% backbone depth, trained with a joint
  BranchyNet-style multi-exit loss
  (`[CITE: Teerapittayanon, McDanel, Kung, "BranchyNet: Fast inference via
  early exiting from deep neural networks", ICPR 2016]`)
  (`[CITE: MobileNet — Howard et al., for the backbone family; well-known,
  find your own preferred version (v1/v2) reference]`).
  Final exit outperforms a no-exit single-output baseline trained on the
  same backbone by ~0.9pp — consistent with a deep-supervision effect
  documented for other auxiliary-loss architectures
  (`[CITE: deep supervision / auxiliary classifier literature, e.g.
  GoogLeNet's auxiliary heads, or a more recent citation for the same
  effect]`).
- **Quantization**: post-training INT8-per-channel quantization
  (representative-dataset calibration, corrected for an initial
  class-imbalance sampling bug), 0.05-0.60pp accuracy drop per exit.
- **Certification**: per-exit confidence threshold chosen via a
  finite-sample conformal risk bound
  (`[CITE: Angelopoulos, Bates, Fisch, Lei, Schuster, "Conformal Risk
  Control", ICLR 2024 (arXiv:2208.02814) and/or Bates, Angelopoulos, Lei,
  Malik, Jordan, "Distribution-Free, Risk-Controlling Prediction Sets",
  JACM 2021 (arXiv:2101.02703) — verify which one states the exact bound
  form (n·R̂+1)/(n+1) ≤ α used in calibrate.py before citing, see
  RELATED_WORK_CANDIDATES.md]`)
  targeting safety-critical-class miss-rate at α ∈ {0.01, 0.05, 0.10}.
  An initial calibration attempt failed to generalize to the held-out
  test split (diagnosed as a genuine calibration/test distribution shift,
  not a bug); fixed with a margin-corrected recalibration, achieving 7/9
  nominal (exit, α) targets on the PC-simulated held-out test set.
  `[CITE: Jazbec et al., "Fast yet Safe: Early-Exiting with Risk Control",
  NeurIPS 2024 (arXiv:2405.20915) -- directly combines early-exit with
  conformal-style risk control; this is THE paper to read and position
  against for the novelty claim (real hardware deployment + PQC
  co-location + load-adaptive policy don't appear to be in that paper's
  scope -- verify and state precisely what's different]`
- **Deployment and hardware validation**: NPU segment conversion,
  on-device golden-input verification (found NPU output is *not*
  bit-exact vs. the PC reference simulator — 1-4 LSB drift, root-caused to
  inherent NPU-vs-reference-kernel rounding differences, not a driver
  version mismatch, which was investigated and ruled out experimentally),
  and — the key methodological contribution for RQ2 — **re-running the
  full conformal coverage validation using genuine on-device NPU output**
  for 1,230 real images, not just the PC simulation. After correcting for
  a sample-composition confound (a class-balanced validation sample
  inflates measured risk relative to the natural class-frequency
  distribution — corrected via Horvitz-Thompson-style reweighting
  `[CITE: Horvitz-Thompson estimator, if using that name formally]`),
  6/8 certifiable (exit, α) combinations hold on real hardware, with the
  two remaining failures both at the strictest α=0.01 tier — consistent
  with the same tier being the hardest to certify in the original
  PC-simulation validation.

### 3.3 Contention scenario design (answers RQ1's negative result, sets up RQ3)

Because 3.1/3.4 established **zero** resource contention on the native
dual-core layout, that result by itself gives an adaptive policy nothing
to react to. To construct a scenario with genuine, unavoidable contention
— and to generalize the finding to smaller/cheaper single-core targets
than this dev board — crypto and the perception decision logic were
placed on **one** shared core, cooperatively interleaved (one ML-KEM-768
sub-operation every N frames).

### 3.4 Adaptive certified exit policy (answers RQ3)

Three exit policies compared under identical crypto scheduling (verified
constant crypto cost across all three):
- **Naive**: always executes the full multi-exit chain, ignoring
  confidence.
- **Static certified**: fixed conformal threshold (α=0.05 tier),
  independent of system state.
- **Adaptive certified**: α=0.05 normally; shifts to the looser but still
  conformally certified α=0.10 tier for frames immediately
  surrounding a scheduled crypto step, trading a controlled amount of
  certified risk margin for throughput under load.

---

## 4. Evaluation Criteria

1. **Safety / achieved risk**: empirical safety-critical miss-rate among
   accepted predictions at each certified exit and α tier, measured (a) on
   the PC-simulated held-out test set, (b) on genuine on-device NPU
   output, and (c) reweighted to the natural class-frequency distribution
   — reported against the nominal α target in all three, not just the
   most favorable one.
2. **Latency / throughput**: total system time to complete a fixed
   combined workload (N perception frames + M required crypto
   handshake steps), decomposed into crypto-side and perception-side
   contributions, under each policy.
3. **Statistical rigor, not point estimates**: paired significance testing
   given the same input sequence is processed under every policy —
   Wilcoxon signed-rank test on per-frame latency (is the speedup a
   consistent effect, not a few outliers), McNemar's test on paired
   correctness (are miss-rate differences between policies actually
   distinguishable from chance at the sample size used)
   `[CITE: Wilcoxon, F. "Individual Comparisons by Ranking Methods."
   Biometrics Bulletin, 1(6), 80-83, 1945; McNemar, Q. "Note on the
   sampling error of the difference between correlated proportions or
   percentages." Psychometrika 12(2), 153-157, 1947 -- both fully
   verified via web search, safe to cite directly]`.
4. **Robustness to design parameters**: sensitivity of the throughput
   result to the crypto-interrupt frequency and the adaptive policy's
   load-detection window, via a trace-driven sweep using hardware-measured
   per-component costs, validated against the directly hardware-tested
   operating point (achieved <0.04% simulation-vs-hardware error) before
   trusting untested parameter combinations.
5. **Reproducibility**: fixed seeds throughout (data split, training,
   conformal calibration sample selection), documented and hashed data
   splits, and an explicitly-flagged deterministic (non-cryptographically-secure)
   RNG stub used only for on-device benchmarking reproducibility, never
   presented as a security property.

---

## 5. What's Established vs. Open

**Established, on real hardware, as of this draft:**
- RQ1: architecturally isolated on the native 2-core layout (null result,
  but rigorously shown, and replicated with the real deployed model, not
  just a toy demo).
- RQ2: conformal certification largely survives real NPU deployment
  (6/8 combinations after correcting a sampling confound), with the
  strictest tier as a known, explained edge case.
- RQ3: adaptive certified policy gives a statistically validated 14-15%
  throughput improvement over naive with no significant risk increase,
  robust across an 8x sweep of crypto-interrupt frequency.

**Genuinely open, pending supervisor input** — see the specific questions
already raised separately: whether the thesis should work at the raw
primitive layer (current) or a full protocol-handshake layer (Tschofenig),
whether GTSRB classification (current) or GTSDB detection is the intended
scope (Houben), and whether the single-core contention scenario (needed
to get a non-null RQ3 result) is an acceptable framing or needs to be
reconciled with the dual-core reality of the actual target board.

---

## 6. Related-work map

**Update: a first pass has been done — see `RELATED_WORK_CANDIDATES.md`**
for real, verified-to-exist papers against all four clusters below (found
via web search, metadata-checked, not fully read — verify before citing).
The map below is still useful for structuring the literature review
section itself.

1. **Early-exit / anytime neural networks** — BranchyNet (found: 
   Teerapittayanon et al., ICPR 2016) and the broader early-exit
   literature; any work specifically combining early-exit with formal/
   statistical guarantees (found: Jazbec et al., "Fast yet Safe:
   Early-Exiting with Risk Control", NeurIPS 2024 — **the closest existing
   work to this thesis's certification approach**; reading it carefully
   and stating precisely what it doesn't cover is the best way to stake a
   sharp novelty claim here).
2. **Conformal prediction / conformal risk control** — the core Vovk et
   al. conformal prediction framework (not yet searched — a classic,
   should be easy to find and cite), and specifically the finite-sample
   risk control bound used here (found: Angelopoulos, Bates, Fisch, Lei,
   Schuster, "Conformal Risk Control", ICLR 2024; and/or Bates,
   Angelopoulos, Lei, Malik, Jordan, "Distribution-Free, Risk-Controlling
   Prediction Sets", JACM 2021 — verify which one has the exact bound
   form used).
3. **Post-quantum cryptography on constrained devices** — NIST PQC
   standardization documents (FIPS 203/204/205), PQClean (found:
   Kannwischer et al., EuroS&P Workshops 2022) and pqm4 (found:
   Kannwischer, Rijneveld, Schwabe, Stoffelen, 2019) as reference/
   optimized embedded implementations, and existing embedded ML-KEM
   benchmarking studies on Cortex-M-class hardware to compare your KQ3
   numbers against (candidate found, not fully verified: arXiv:2603.19340).
4. **Resource contention / co-located workloads on embedded SoCs** — this
   is where the "PQC + ML sharing one chip" gap lives. Found: a direct
   description of this thesis's target NPU (Bamberg et al., "eIQ Neutron",
   2025), and two structurally-analogous-but-different-domain systems
   papers (Islam & Nirjon, "Zygarde", ACM IMWUT 2020 — adapts inference
   depth to intermittent power rather than crypto load; Zhao & Georgantas,
   "Strait", 2026 preprint — treats early-exit as a scheduling lever under
   GPU-serving contention). **A direct search for "co-scheduling PQC with
   ML inference on embedded microcontrollers" turned up nothing specific
   to that combination** — this supports treating it as the genuine gap
   this thesis fills, but double-check with your supervisors in case
   they're aware of something this search missed.
