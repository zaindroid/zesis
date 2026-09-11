# Experiment 3 — Selective / Probabilistic Side-Channel Obfuscation

**Question:** Full dummy-crypto obfuscation was shown infeasible at ML-KEM-768
(0 dummies fit under the 33 ms frame budget). Can a *selective* or
*probabilistic* dummy policy degrade the attacker's ability to tell real
crypto / exit decisions apart — while still fitting the real-time deadline?

**Method:** extension of the leakage-aware scheduler model (trace-driven,
real measured costs, FIFO 3-slot backlog, 33 ms deadline, 1230 frames, 123
real ML-KEM crypto steps every 10th frame). Two new policies:
- **probabilistic_p03** — dummy after each real step with p=0.3 (random
  schedule; attacker cannot rely on fixed timing)
- **exit1_selective** — dummy after a real step *only* when the next frame
  exits at exit1 (the cheapest exit → the most timing headroom); uses the
  measured adaptive exit distribution (exit1 45% / exit2 17% / exit3 38%).

Two attacker targets:
- **crypto activity** (real-vs-dummy): naive "every step is real" accuracy +
  fraction of real steps hidden by a neighboring dummy.
- **exit decision** (the measured RF envelope classifier, 98.3% on clean
  envelopes): a dummy in the frame contaminates the envelope — modeled
  transparently as accuracy decaying to chance (1/3) on dummy frames.

## Results

### ML-KEM-512 (the feasible case)

| policy | misses | +time | +energy | dummies | crypto attacker | hidden | exit leak |
|--------|--------|-------|---------|---------|-----------------|--------|-----------|
| no_defense | 0 | — | — | 0 | 100.0% | 0% | 98.3% |
| fixed_dummy (full) | 0 | +99% | +99% | 122 | 50.2% | 99% | 91.9% |
| **probabilistic p=0.3** | 0 | +22.8% | +22.8% | 28 | 81.5% | 23% | 96.8% |
| **exit1_selective** | 0 | +48% | +48% | 59 | 67.6% | 48% | 95.2% |

### ML-KEM-768 (the real-time-constrained case — the experiment's focus)

| policy | misses | +time | +energy | dummies | crypto attacker | hidden | exit leak |
|--------|--------|-------|---------|---------|-----------------|--------|-----------|
| no_defense | 6* | — | — | 0 | 100.0% | 0% | 98.3% |
| fixed_dummy (full) | **13** | +99% | +99% | 122 | 50.2% | 99% | 91.9% |
| **probabilistic p=0.3** | **9** | +32.5% | +32.5% | 40 | **75.5%** | 33% | 96.2% |
| **exit1_selective** | **10** | +48% | +48% | 59 | **67.6%** | 48% | 95.2% |

\* the 768 baseline already has 6 deadline misses: a full 768 crypto step
(38.7 ms) exceeds the 33 ms slot even with no defense — the joint-scheduler
finding that 768 is infeasible under a tight slot.

## Findings

1. **The full-defense claim is confirmed and quantified**: at 768,
   fixed_dummy (a dummy after every real step) more than doubles the deadline
   misses (6 → 13) — infeasible, as established. At 512 it *is* feasible (0
   misses) but costs +99% time/energy.
2. **The probabilistic compromise works at 768**: p=0.3 drops the crypto
   attacker from 100% → **75.5%** (and hides 33% of real steps) at only +3
   deadline misses over the already-stressed baseline and +32.5% energy. That
   is the engineering sweet spot: *some* obfuscation, *some* feasibility.
3. **Exit-aware selection hides more per dummy**: exit1_selective reaches the
   attacker at 67.6% (hidden 48%) — better crypto hiding than p=0.3 — at +4
   misses. The anytime exit decision is genuinely reusable as an obfuscation
   signal: cheap exits buy headroom for noise.
4. **Honest caveat — the exit decision itself is NOT hidden**: with these
   light dummy rates the exit-decision classifier only degrades 98.3% → 95–96%
   (the dummies touch only 2–5% of frames). Hiding the *exit* (attack B)
   would need dense dummies, which is exactly the infeasible regime at 768.
   The compromise protects the *crypto activity* (attack A), not the exit
   privacy. This asymmetry is a real, publishable finding.

## Why it matters (thesis)

The experiment shows the obfuscation problem is not binary. "Full obfuscation
is too slow" was the naive conclusion; the honest engineering answer is a
**probability/exit-conditioned dummy schedule** that cuts the crypto-leak
attacker from ~100% to ~68–76% for a feasible 30–50% energy overhead and a
handful of extra deadline misses — and it exposes exactly where the remaining
leak lives (the exit decision), pointing to future work (e.g., exit-obfuscated
envelopes) rather than pretending the problem is solved.

## Files

- `conformal/selective_obfuscation.py` — the model (reuses the measured-cost
  framework from `leakage_aware_scheduler.py` / `joint_scheduler.py`)
- `results/leakage_aware/selective_obfuscation_summary.json` — machine-readable
- Physical follow-up (documented, not run): a PPK2 re-capture with dummy
  frames to measure the *real* envelope degradation of the RF classifier.
