# Research Overview Video — Narration Script

**Title:** *Certified Anytime Perception under Post-Quantum Cryptographic Load*
**Format:** spoken narration for a NotebookLM-style overview/video (~13–15 min, ≈2100 words)
**Style:** story mode, accessible to a general technical audience, all numbers from the measured results.

---

## Opening — the world we live in

[VISUAL: montage — a smart traffic camera, a battery-powered sensor on a lamppost, a car dashboard]

Imagine a small device — a traffic-sign recognition camera inside a car, or a sensor on a streetlight that never gets a new battery. It has a tiny microcontroller, a few megabytes of memory, and a job to do: look at the world, understand what it sees, and send secure messages about it. Two seemingly unrelated questions meet on this little chip.

First: how does it *see*? Modern neural networks are powerful, but they are also expensive — and on a tiny microcontroller, every millisecond of computation costs energy and time. Second: how does it *stay secure*? The world is moving to post-quantum cryptography — the new math that protects against future quantum computers — but that new math is heavy, and it lands on the exact same small chip.

This is the story of a research project that put those two things together: a perception system that is **certified to be safe**, and a cryptographic load that is **rigorously measured** — and a controller that lets them share the chip without breaking the deadline.

---

## Act 1 — Why post-quantum cryptography, and why benchmark it?

[VISUAL: a quantum computer icon crossing out a lock; a timeline "today → 2030"]

Let's start with the cryptography, because that's why benchmarking became the backbone of this thesis.

Today, almost all secure communication on the internet — and on millions of IoT devices — relies on a few mathematical problems that are hard for *classical* computers. But a sufficiently large quantum computer would solve those problems quickly. That's not a sci-fi threat; it's a migration deadline. Governments and standards bodies — including NIST and the IETF, where my supervisor Prof. Tschofenig works — are standardizing the replacements: **ML-KEM**, a key-encapsulation mechanism, and **ML-DSA**, a digital signature scheme. These are lattice-based: built on high-dimensional geometry problems that are believed to stay hard even for quantum machines.

The catch? Lattice cryptography is **expensive** — several times slower than the classical ECC math it replaces, and far more demanding on memory. And it lands on devices that have the least resources to spare.

So the first question of this thesis was: **what does post-quantum cryptography actually cost on real, modern microcontrollers?** That is why benchmarking — proper, rigorous, reproducible benchmarking — became a critical pillar of the whole project. Not as a formality, but as the *foundation*: you cannot design a controller that adapts to a load you haven't measured.

---

## Act 2 — What we benchmarked, and how

[VISUAL: two boards side by side — FRDM-MCXN947 and ESP32-S3 — with their specs]

We benchmarked on **two real hardware platforms**: the NXP FRDM-MCXN947, a Cortex-M33 microcontroller at 150 megahertz with a neural-network accelerator, and the ESP32-S3, an Xtensa processor at 240 megahertz. Two very different chips, one story.

We measured **ML-KEM at three security levels** — 512, 768, and 1024 — and **ML-DSA at three levels** — 44, 65, and 87. For each one we measured key generation, encapsulation, decapsulation, signing, and verification, thousands of times, with real cycle counters, on real silicon. We also ran the same benchmarks under three different software stacks — bare metal, the Zephyr operating system, and the ESP-IDF framework — so the numbers are comparable across platforms.

Three findings from this benchmarking stand out.

**First: the cost is real.** A single ML-KEM-768 key exchange takes roughly 9 to 12 milliseconds on the NXP board — the equivalent of several frames of perception on the same chip.

**Second — and this is the headline — ML-DSA signing has a fat tail.** The *median* signing time is fine, but the *worst* case is **six to eight times slower**, because the algorithm keeps re-rolling random values until they meet a constraint — rejection sampling. And the critical discovery: this worst-to-median ratio is **identical across both boards**. It's not a hardware quirk — it's a property of the algorithm itself. Any system that plans on the average signing time will miss its deadlines, guaranteed.

**Third: the migration is not uniformly bad.** When we benchmarked the *classical* baseline — using the official EEMBC SecureMark-TLS benchmark, the industry standard, on both boards — we found something surprising. On the ESP32, switching from classical ECDH/ECDSA to post-quantum ML-KEM/ML-DSA actually made the handshake **60 to 80 percent faster in both time and energy**, because that chip's classical crypto stack is the bottleneck. On the NXP board, the migration costs anywhere from a 35 percent *saving* at the lowest security level to a 38 percent *increase* at the highest.

That is the value of benchmarking: it turned a vague fear — "PQC is slow" — into a precise, board-by-board, security-level-by-security-level map of exactly where the cost is, and where it isn't.

---

## Act 3 — The core system: certified anytime perception

[VISUAL: a 3-exit neural network diagram; a stop-sign image flowing through; a green "certified" badge]

Now, the perception side.

A traffic-sign classifier doesn't have to look at every image with equal effort. Some signs are obvious — a clear, large stop sign — and can be answered with a tiny fraction of the network. Others need the full model. This is the idea of **anytime perception**: a network with three exits, at 30, 60, and 100 percent of its depth, so the chip can stop early when it's confident.

But "confident" is not a guarantee. So we wrapped the exits in **conformal prediction** — a statistical framework that turns raw confidence into a *provable* risk bound. We used a frozen, auditable protocol: the test data was touched exactly once, at the very end, and every threshold was calibrated on separate data. The result: for each exit and each target error rate, a certified threshold — if the model accepts the prediction at that exit, the probability of a dangerous mistake is mathematically bounded. Some exits were certified; one was honestly *not* — and we reported that, rather than tuning the numbers until it passed. That integrity is the heart of the method.

Then we interleaved the two: the certified model, and the ML-KEM cryptography, sharing the same core. We ran over a thousand frames with a full post-quantum handshake every ten frames, and compared three policies: always run the full network; always exit early; or **adapt** — use the certified menu to stop early when the crypto load allows. The adaptive policy saved **14 to 15 percent of device time with no meaningful increase in risk**. The certification, measured, translated directly into real energy savings.

---

## Act 4 — The AI and learning layer

[VISUAL: a small control-loop diagram; "exit decision" and "security level" knobs turning]

Now the learning part — where the system gets smarter.

The first question: can a **learned exit policy** beat a hand-set one? We trained isotonic risk curves on the calibration data — learning, for each confidence level, the actual probability of a mistake — and let the system pick the shallowest exit whose risk was certified. It worked, and it also taught us a lesson in scientific honesty: when we audited the result under a strict correction for multiple testing, one of the exits failed certification, and we reported that rather than hiding it.

Then the bigger question: can one controller learn **both** decisions at once — how much cryptography to run *and* how deep to perceive? This is the **joint scheduler**. Using the real measured costs from our benchmarks — exit times, key-exchange times, per security level — we simulated the full pipeline under a strict 33-millisecond frame deadline. The learned joint scheduler cut **41 percent of the time and 39 percent of the energy, and missed zero deadlines** — where the naive baseline missed seventy. Learning, grounded in measured costs, turned the shared-chip problem into a solved scheduling problem.

And then we asked the question the whole thesis was waiting for: can the system keep its safety guarantee when the *world changes*? Conformal prediction assumes the test data looks like the calibration data. In a real car, entering a tunnel is a sudden change — an abrupt distribution shift. We simulated exactly that: a thousand frames, and at frame 300 the images suddenly darken by sixty percent with noise added, like a camera failing. The static, certified thresholds collapsed — coverage fell from 96 percent to 49 percent. Then we applied **test-time conformal adaptation** — an online feedback loop that watches its own mistakes and widens the prediction sets when it's making errors, and tightens them again when the environment stabilizes. The adaptive system held coverage at **94 to 95 percent through the shift**, for only three percent more compute. It does not react instantly — there is an honest, measurable lag of about a hundred frames — and the safety margin appears as larger prediction sets, not deeper exits. But it recovers, and it proves the safety guarantee can survive a changing world.

---

## Act 5 — The security reality check

[VISUAL: a power trace oscilloscope; a lock icon; a question mark]

A thesis about security on embedded hardware would not be complete without asking: what does the *physical* device leak?

Using a high-sampling-rate power meter, we showed that the power envelope reveals **which cryptographic operation is running** — 99.8 percent accuracy — and even more strikingly, it reveals **the anytime exit decision itself** — 98.3 percent accuracy. An attacker watching the power trace can tell whether the model stopped early or ran deep. That's an attack on the certification itself: the device broadcasts how much it trusted each image.

The obvious defense — run dummy cryptographic operations to hide the real ones — turns out to be computationally infeasible at the top security level under the frame deadline. So we tested the engineering compromise: **probabilistic and selective obfuscation**. Insert dummy crypto with probability thirty percent, or only when the network exits early — the cheap exit leaves timing headroom. The attacker's accuracy dropped from one hundred percent to about 68 to 76 percent, at a feasible cost. It's not a perfect defense — and we say so honestly: it hides the *crypto activity*, but not the *exit decision*. That honest boundary is itself a contribution.

Two more experiments completed the picture. First, we connected our measured numbers to the real standards world: a **DTLS Connection-ID** model, the standard Prof. Tschofenig champions, showed that amortizing the post-quantum handshake across a session extends battery life by **up to nineteen times** on the ESP32 at high wake-up rates. Second, a hardware-level post-mortem of optimized assembly code — the fastest way to run crypto, but written for an older CPU core — showed it corrupts its own stack on the modern core, caught at the register level by the new hardware's fault-detection. A crash, turned into an architectural finding.

---

## Conclusion — the cohesive story

[VISUAL: the full system diagram; the thesis title; the boards]

So let me bring it together.

The world is migrating to post-quantum cryptography, and that migration lands on small, energy-constrained devices. This thesis did three things about that.

**First, it measured.** EEMBC-standard benchmarks on two real platforms, three security levels each, in latency and in energy — turning "PQC is expensive" into a precise, reproducible map. It found the fat tail of ML-DSA that any real-time system must respect, and it found that on some platforms the migration is actually a *win*.

**Second, it adapted.** A certified anytime perception system — with provable risk bounds, not just high confidence — learned to share the chip with this cryptographic load, saving 14 to 15 percent, then 41 percent time and 39 percent energy with zero missed deadlines, and proved its safety guarantee survives a changing world through test-time conformal adaptation.

**Third, it was honest.** About what it could not certify. About where the defense stops working. About the reactive lag in adaptation. About a benchmark that did not fit. That honesty is what makes the results trustworthy — and in a field where the cost of a wrong number is a missed deadline or a failed safety bound, trustworthiness is the point.

The certified-anytime controller — the part of the system that provably absorbs the post-quantum load — is the load-bearing component. And now, it's a story supported by measurements on real hardware, from the power trace to the fault register.

[VISUAL: end card — thesis title, supervisors, "thank you"]
