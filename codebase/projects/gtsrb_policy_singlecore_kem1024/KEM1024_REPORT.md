# ML-KEM-1024 Variant: Does the Adaptive Policy's Benefit Scale with Crypto Weight?

Repeats the single-core interleaved policy experiment
(`gtsrb_policy_singlecore/POLICY_EXPERIMENT_REPORT.md`) with ML-KEM-1024
(the heaviest NIST-standardized security level) in place of ML-KEM-768,
same 1230-image sample, same crypto schedule (period=10, 123 steps = 41
handshakes, verified identical across all three policies again).

## Result: absolute time saved is essentially constant; percentage saved shrinks

| policy | total device time | vs. naive (768) | vs. naive (1024) |
|---|---|---|---|
| naive (768) | 7633.6 ms | -- | -- |
| static (768) | 6542.4 ms | 1091.1 ms faster (14.3%) | -- |
| adaptive (768) | 6476.2 ms | 1157.4 ms faster (15.2%) | -- |
| naive (1024) | 10056.3 ms | -- | -- |
| static (1024) | 8966.8 ms | -- | 1089.5 ms faster (10.8%) |
| adaptive (1024) | 8898.3 ms | -- | 1158.0 ms faster (11.5%) |

The **absolute** time saved by exiting early is nearly identical regardless
of crypto weight (static: 1091ms @768 vs 1090ms @1024; adaptive: 1157ms
@768 vs 1158ms @1024) -- expected, since that saving comes entirely from
the perception side, which doesn't know or care which KEM variant is
running. The **percentage** saved drops (14.3%->10.8%, 15.2%->11.5%)
because ML-KEM-1024's larger fixed crypto cost (7180ms total vs 4757ms for
768, a ~51% increase, consistent with KQ3's measured ~1.5x scaling per
security level) makes up a bigger share of the total workload, leaving
relatively less of the total for the perception-side saving to matter
against.

This is the same underlying mechanism as the period sweep in
`PARAMETER_SWEEP_REPORT.md` (savings shrink as the fixed-cost workload
grows relative to the variable-cost one), now confirmed along a different
axis (crypto *weight* rather than crypto *frequency*) -- consistent, not a
coincidence, and a genuinely useful characterization for the thesis: **the
adaptive policy's value is largest for lighter/more frequent crypto
workloads and smallest (but never zero, per the sweep) for heavier/rarer
ones.**

## Accuracy: identical to the ML-KEM-768 experiment (as expected)

Exit distribution (naive=100% exit3; static=12.2%/63.3%/24.5%;
adaptive=14.1%/65.7%/20.2%) and every miss-rate number (raw and
natural-frequency-reweighted) are byte-identical to the ML-KEM-768 run.
This is a correctness check, not a new finding: the crypto variant only
changes the interleaving schedule's *cost*, never which images are
processed or what the perception chain decides for them, so any
divergence would have indicated a bug. None found.

## Artifacts

- `flash_debug/build_{naive,static,adaptive}.elf`
- `tools/policy_results_{naive,static,adaptive}.csv`
- `pqclean/` -- swapped to PQClean's `ml-kem-1024/clean` (same swap
  mechanism as `H:\z_thesis\swap.ps1`, applied manually)
