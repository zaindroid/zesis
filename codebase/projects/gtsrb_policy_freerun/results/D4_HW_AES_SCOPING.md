# Experiment #4 — Hardware-AES for Split Inference: Scoping Decision

**Status: NOT integrated (honest engineering decision)**

## Goal
Show that hardware AES-GCM makes Option B's software-only cost (122.7 ms/frame)
negligible (~1 ms), completing the "software vs hardware" story.

## What we found
The FRDM-MCXN947 has NO standalone hardware-AES driver:
- **CASPER** (the crypto accelerator) is an **ECC/RSA modular-math** engine —
  it does NOT do AES.
- **ELS-PKC** (the EdgeLock Secure Enclave crypto library) has AES-GCM but
  requires **468 source files** (session manager, key manager, code-flow
  protection, full ELS stack) to integrate.
- The only other AES path is the ROM-based nboot HAL (bootloader, not
  usable for app-side AES).

## The honest decision
Wiring the full ELS-PKC stack into the freerun project is a **multi-day,
high-risk integration** (468 files, session/flow-protection init, key
management) for a claim that is already well-established: the ELS hardware
AES engine is a known ~100× faster than software AES (it's a dedicated
hardware block; NXP's own docs and benchmarks support this).

**We choose NOT to do this integration** — it doesn't match the thesis value
and risks destabilizing the working benchmark stack. Instead:

## What we state honestly
- The **software-only cost is the real, measured number** (122.7 ms/frame at
  -O3, Option B) — an honest baseline for software PQC-protected split
  inference on this class of MCU.
- The **hardware-AES expectation** (~1 ms) is documented from the ELS
  hardware capability, marked as **expected, not measured**, and left as
  future work (a dedicated ELS-PKC integration project).

## Why this is defensible for the thesis
- The thesis's contribution is the *measurement methodology* + the *honest
  software baseline* + the *privacy-layer design*, not the hardware crypto
  integration.
- Overclaiming a hardware number we didn't measure would violate the
  single-touch/honesty discipline of the frozen protocol.

## Alternative (cheap, if wanted later)
A **memory-mapped AES via the ELS registers** (bypassing the PKC library)
is theoretically possible but undocumented in this SDK — not worth the risk.
