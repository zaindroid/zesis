# KQ5 Re-run: Real GTSRB Multi-Exit Model (not cifarnet)

Re-runs the feasibility sprint's key experiment (NPU-vs-crypto resource
contention) with the actual trained, INT8-quantized, conformally-calibrated
GTSRB multi-exit segments (`gtsrb_multiexit/segments/`) chained on core 0,
instead of the toy cifarnet demo model originally used for KQ5. Core 1 runs
the same ML-KEM-768 hammering loop as `npu_dc`, unchanged.

Free-running (flash -> reset -> read serial), N=100 iterations per run,
same fixed golden input every iteration (GTSRB test 00000.ppm, true label
16), 150 MHz.

## Result: KQ5's zero-contention finding replicates with the real model

| stage | baseline (crypto idle) mean (us) | contention (crypto hammer) mean (us) | delta (us) | delta (%) |
|---|---|---|---|---|
| segA | 830.23 | 830.25 | +0.02 | +0.002% |
| copy1 | 23.00 | 23.01 | +0.01 | +0.043% |
| segB | 454.42 | 454.49 | +0.07 | +0.015% |
| copy2 | 8.25 | 8.20 | -0.05 | -0.606% |
| segC | 1403.75 | 1403.84 | +0.09 | +0.006% |
| **total** | **2973.04** | **2973.13** | **+0.09** | **+0.003%** |

(std dev ~0.4-0.5us for every stage in both runs; n=100 each;
raw data in `kq5_rerun_baseline_crypto_idle.txt` /
`kq5_rerun_contention_crypto_hammer.txt`)

**The total-latency delta (0.003%) is statistically indistinguishable from
noise and closely matches the original cifarnet-based KQ5 result
(-0.001%).** This confirms the architectural-isolation finding isn't an
artifact of the toy demo model -- it holds for the real, deployed,
certified multi-exit classifier too. Predictions were correct (class 16,
matching true label) with high confidence (exit1=0.986, exit2=0.999,
exit3=1.000) throughout every iteration of both runs.

## A real bug found and fixed along the way

The first attempt at this re-run crash-looped indefinitely (full-chip
reset roughly every 0.9s, never progressing past "Starting core 1
(crypto)..."). Root cause: `npu_dc`'s `CMakeLists.txt` only defines
`CORE1_IMAGE_COPY_TO_RAM` for the **C** compiler (`CC`), not **C++**
(`CX`) --

```cmake
mcux_add_armgcc_configuration(
        CC "-DCORE1_IMAGE_COPY_TO_RAM"
)
```

`main.cpp` is a C++ file, so the macro was silently undefined for it,
meaning the `#ifdef CORE1_IMAGE_COPY_TO_RAM` block containing the memcpy
that actually copies core 1's compiled image from flash into its boot RAM
address (0x2004E000) never compiled in. Core 1 was told to start executing
from that address anyway (`MCMGR_StartCore`), executed uninitialized/stale
RAM, faulted, and (with `MCMGR_HANDLE_EXCEPTIONS=1`) triggered a full
system reset -- repeating forever. **Fixed** by adding `CX
"-DCORE1_IMAGE_COPY_TO_RAM"` alongside the existing `CC` line. This
appears to be a latent bug in the original `npu_dc` project too (same
CMakeLists.txt, unchanged) -- not something introduced by this
integration -- worth flagging separately since it means `npu_dc`'s
`main.cpp` may never have actually been copying its own core1 image either
(untested there since the KQ4/KQ5 measurements didn't depend on
observing this specific print line).

## Also fixed: Neutron driver/converter version alignment

Same fix as `gtsrb_multiexit` (see `tools/golden/DEPLOYMENT_REPORT.md`):
swapped the project-local `libNeutronDriver.a`/`libNeutronFirmware.a` to
the version-matched 3.1.3 build. Note: unlike `gtsrb_multiexit`, this
project's link line pulls in **two** copies of these libraries (the
project-local one and a second one from the shared `mcuxsdk` tree, via the
eIQ tensorflow-lite CMake module) inside a `--start-group`/`--end-group`;
symbol resolution favors whichever appears first in link order, which is
currently still the shared (3.1.1) copy, so the "microcode version
mismatch" warning still appears at boot. Not fixed here since (a) it's
already established (Task 37 on `gtsrb_multiexit`) that this drift doesn't
change predictions or accept/reject decisions, and (b) reordering would
require touching the shared SDK's module wiring, which this session has
deliberately avoided to keep zero blast radius on other NPU projects.

## What this does and doesn't establish

This confirms KQ5's conclusion generalizes to the real deployed model, at
the level of "does the actual model behave the same way, architecturally,
as the toy demo did." It does **not** yet exercise a contention-aware exit
policy or any inter-core signaling -- per the open design question sent to
supervisors (`MILESTONE_REPORT.md`, Section 4), no IPC channel exists
between cores in this build (matches `npu_dc`: `MCMGR` only boots core 1).
That's the next piece, pending framing feedback.
