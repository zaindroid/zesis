# Related-Work Candidates (web-searched, verify before citing)

Real papers found via web search to fill the `[CITE: ...]` placeholders in
`THESIS_PROPOSAL_DRAFT.md`. Every entry below was verified to exist (title,
authors, venue checked against the source), but **you should still pull
each one up yourself and read at least the abstract before citing** —
I did not read full papers, only verify metadata and skim
search-engine-generated summaries. Confidence level noted per entry.

---

## Cluster 1: Early-exit / anytime neural networks

**Teerapittayanon, S., McDanel, B., Kung, H.T. "BranchyNet: Fast inference
via early exiting from deep neural networks." ICPR 2016.**
Confidence: high (well-known foundational paper, exactly matches). The
origin of the joint multi-exit loss framing used in Brief 2's training.

**Jazbec, M. et al. "Fast yet Safe: Early-Exiting with Risk Control."
NeurIPS 2024. arXiv:2405.20915.**
Confidence: high. **This is the single most directly relevant related-work
paper found** — it explicitly combines early-exit neural networks with
conformal-style risk control, which is exactly the technique this thesis
applies (independently) to GTSRB + real NPU hardware. Read this one first
and use it to sharpen the novelty claim: what does this thesis do that
that paper doesn't (real hardware deployment + PQC co-location + the
adaptive load-aware policy, none of which appear to be in scope there
based on the abstract)?

**Also found, possibly worth a skim**: "NACHOS: Neural Architecture
Search for Hardware Constrained Early Exit Neural Networks" (arXiv, exact
year/venue not verified) — relevant to the NPU-op-whitelist-constrained
architecture design angle if you want a citation there instead of/beside
MobileNet.

---

## Cluster 2: Conformal prediction / conformal risk control

**Angelopoulos, A.N., Bates, S., Fisch, A., Lei, L., Schuster, T.
"Conformal Risk Control." ICLR 2024. arXiv:2208.02814 (preprint
circulated since Aug 2022).**
Confidence: high on metadata. This is very likely the primary paper to
cite for the conformal calibration method in `conformal/calibrate.py`.

**Bates, S., Angelopoulos, A., Lei, L., Malik, J., Jordan, M.
"Distribution-Free, Risk-Controlling Prediction Sets." J. ACM, 2021.
arXiv:2101.02703.**
Confidence: medium-high on relevance, **not fully verified** — I could not
mechanically extract the exact bound formula `(n·R̂+1)/(n+1) ≤ α` from
either paper's PDF (tool limitation, not a negative result). One of these
two papers is very likely where that exact finite-sample UCB bound
originates. **Before finalizing, check both papers directly against your
`calibrate.py` docstring's bound and cite whichever one actually states it
in that form** — possibly both, if Angelopoulos et al. builds on Bates et
al.'s more general risk-controlling-prediction-sets framework.

---

## Cluster 3: Post-quantum cryptography on constrained devices

**NIST FIPS 203 (Module-Lattice-Based Key-Encapsulation Mechanism
Standard).** Cite directly for ML-KEM standardization.

**Kannwischer, M.J., Rijneveld, J., Schwabe, P., Stoffelen, K. "pqm4:
Testing and Benchmarking NIST PQC on ARM Cortex-M4." Second PQC
Standardization Conference, 2019. IACR ePrint 2019/844.**
Confidence: high. Cite as the optimized-assembly alternative to PQClean's
portable reference implementation used in this thesis — good place to
note the honest gap ("PQClean clean, not pqm4-optimized — cite as an
honest baseline" is already your own framing from KQ3).

**Kannwischer, M.J., Schwabe, P., Stebila, D., Wiggers, T. "Improving
Software Quality in Cryptography Standardization Projects." EuroS&P
Workshops (SSR) 2022. IACR ePrint 2022/337.**
Confidence: high. This is the PQClean project's own paper — cite for the
`PQClean` codebase this thesis's benchmarks are built on.

**Also found**: "MEML-KEM: A Memory-Efficient Implementation of ML-KEM for
IoT Devices" (Springer, exact venue/year not fully verified) and
"Benchmarking NIST-Standardised ML-KEM and ML-DSA..." (arXiv:2603.19340) —
both worth a look if you want a direct comparison point for your own KQ3
cycle-count numbers against other published embedded ML-KEM benchmarks.

---

## Cluster 4: Resource contention / co-located workloads on embedded SoCs

**Bamberg, L., Minnella, F., Bosio, R., Ottati, F., Wang, Y., Lee, J.,
Lavagno, L., Fuks, A. "eIQ Neutron: Redefining Edge-AI Inference with
Integrated NPU and Compiler Innovations." Submitted to IEEE Transactions
on Computers, 2025. arXiv:2509.14388.**
Confidence: high. **This describes the exact NPU (NXP eIQ Neutron) used as
this thesis's target hardware** — cite when characterizing/justifying the
hardware target, and potentially cross-check its reported speedup/
compute-utilization numbers against your own KQ2/KQ6 measurements.

**Islam, B., Nirjon, S. "Zygarde: Time-Sensitive On-Device Deep Inference
and Adaptation on Intermittently-Powered Systems." Proc. ACM IMWUT, Vol.
4, No. 3, 2020.**
Confidence: high on metadata, good analogy: adapts DNN inference depth to
a *different* resource constraint (intermittent power availability rather
than crypto load), but the mechanism — adapting an anytime model's
operating point to current system state — is structurally the same idea
this thesis applies to crypto contention. Good citation for "prior work
adapts inference to system state, but not to this specific resource
(PQC-induced contention), and not with a certified/provable risk bound."

**Zhao, H., Georgantas, N. "Strait: Perceiving Priority and Interference
in ML Inference Serving." arXiv:2604.28175, preprint (2026).**
Confidence: high on metadata, very new (2026 preprint, so treat with
appropriate caution as not-yet-peer-reviewed). Explicitly treats
early-exit points as "a scheduling degree of freedom" under GPU-serving
contention — structurally close to this thesis's adaptive policy, but in
a cloud-GPU-serving context rather than embedded/PQC. Good for the
"resource contention forces exit-depth adaptation" framing generally.

**Search finding worth stating explicitly in the thesis**: a direct search
for "co-scheduling cryptographic workload with ML inference on embedded
microcontrollers" turned up essentially nothing specific to that exact
combination — adjacent work exists on embedded security side-channels and
general embedded ML scheduling, but the specific gap (PQC handshake +
real-time certified perception sharing one constrained chip) appears
genuinely unaddressed in the literature as of this search. Worth stating
as the explicit gap this thesis fills, rather than assuming it and being
wrong — if you or your supervisors know of a paper that does address this
directly, it changes the novelty framing significantly.

---

## How to use this file

Each `[CITE: ...]` marker in `THESIS_PROPOSAL_DRAFT.md` corresponds to one
of the clusters above. Replace the markers with the specific
paper(s) once you've verified them yourself, and remove this file's
"candidate, verify" framing from your actual proposal — this document is
scaffolding for you, not something to hand in as-is.
