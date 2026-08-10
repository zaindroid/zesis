# PQC Benchmark Work — Detailed Progress Summary

Covers everything done to build the EEMBC-style ML-KEM (post-quantum
key exchange) benchmark suite: performance, memory, code size, and
energy, across all three security levels (512 / 768 / 1024), on the
FRDM-MCXN947 board. Written as a full record of what was attempted,
what worked, what didn't, and why — for your own reference, separate
from the cleaned-up report package meant for sharing.

---

## 1. Goal

Supervisors approved extending the thesis with a rigorous, EEMBC
SecureMark-style benchmark suite for ML-KEM — covering performance,
memory, and energy, both for standalone crypto operations and (still
pending) for the interleaved crypto+perception use-case scenario. The
explicit requirement was that everything be properly documented and
reproducible, not just raw numbers.

## 2. Performance and memory (completed early, straightforward)

- **Timing**: Cortex-M DWT cycle counter, 100 repetitions per operation
  per variant, free-running (no debugger attached — established as a
  hard rule after earlier experience showing debugger attachment
  distorts timing).
- **Memory**: stack "high-water-mark" technique — paint the unused
  stack with a known pattern before each operation, scan afterward to
  find how deep it actually grew.
- **Code size**: read directly from the linker's memory report.
- All three variants (ML-KEM-512/768/1024) run cleanly, `kem_match=1`
  (correctness verified) on every run. Results cross-validated against
  an earlier, independent feasibility-sprint measurement to within
  0.2ms — strong evidence the methodology is sound.
- **Known build gotcha documented**: `swap.ps1` overwrites the
  *contents* of `pqclean/*.c` but keeps the same filenames, so `ninja`
  can incorrectly treat already-compiled objects as up to date after a
  swap. Fixed by force-deleting the `pqclean` object directory before
  every rebuild after a variant swap.

**Results (performance, full handshake = keypair + encaps + decaps):**

| Variant | Time | Peak stack | Code+data size |
|---|---|---|---|
| ML-KEM-512 | 72.17 ms | 12,344 B | 82,576 B |
| ML-KEM-768 | 115.97 ms | 17,272 B | 83,832 B |
| ML-KEM-1024 | 174.91 ms | 23,384 B | 85,976 B |

## 3. Energy measurement — the long part

This was the bulk of the session's effort. Summarized chronologically.

### 3.1 Finding the right measurement point

- Started with **J25**, believed (from a partial manual excerpt) to be
  the board's main `P3V3_MCU` supply. Wired PPK2 (Nordic Power Profiler
  Kit II) in Ampere Meter mode after desoldering the two 0-ohm
  resistors (R151, R212) normally carrying that rail's current.
- **J25 turned out to be wrong.** Live PPK2 trace stayed flat at
  ~144 µA regardless of whether crypto was running — proven with a
  multimeter and by watching the trace against the serial monitor
  simultaneously.
- Got the *actual* schematic (`90818-MCXN947SH.pdf`) and the official
  Hardware User Guide's jumper table (much more reliable than the
  earlier partial excerpt). This revealed the real topology: **J24**
  feeds `P3V3_MCU` from the board's main `P3V3` rail (default: shorted
  jumper cap, no resistor); J25/J26/J27/J28 are four *separate*,
  smaller downstream sub-rails (`VDD_IO_USB`/`VDD_ANA`/`VDD_BAT`/
  `VDD_CORE_SYS`) branching off `P3V3_MCU`, each DNP-by-default with
  its own 0-ohm resistor. J25 was never the main supply at all.
- Switched to **J24**: pulled its jumper cap (no desoldering needed —
  simpler than J25), wired PPK2 across the two pads. This produced a
  current trace that clearly correlates with crypto activity (~13 mA
  idle, ~16 mA active) — confirmed as the correct point.

### 3.2 Wiring/instrument troubleshooting along the way

- **PPK2 mode confusion**: distinguished "Source Meter" (PPK2 supplies
  its own voltage — wrong for this setup) from "Ampere Meter" (passive
  pass-through, correct — the board's own USB power supplies the rail,
  PPK2 only measures current through it).
- **Board wouldn't boot with the ammeter connected, worked fine when
  the jumper was shorted.** Root cause turned out to be simple: the
  board just needed a fresh USB replug every time the jumper was
  swapped for the ammeter connection (a power/enumeration state issue,
  not a burden-voltage or wiring problem as first suspected).
- **Serial monitor connected = distorted current trace.** Found
  empirically that having a serial terminal open at all (even printing
  nothing) visibly disturbs the PPK2 trace. Procedure from then on:
  disconnect serial before capturing, reconnect only afterward to pull
  buffered results for a correctness cross-check.

### 3.3 GPIO trigger pin for per-operation boundaries

- Firmware's `ENERGY_MODE` build toggles a GPIO pin around each
  operation (mirrors SecureMark-TLS's own "GPIO for external
  triggering" approach), intended to let PPK2's digital channel mark
  exact per-op boundaries.
- Original placeholder trigger pin (onboard red LED) was replaced with
  a proper Arduino-header pin once the official pinout table was
  available: **D2 / `P0_29`**, confirmed conflict-free.
- **Bug found and fixed**: the pin never toggled. Root cause — `P0_29`
  is never configured by the project's `pin_mux.c`, so its PORT mux
  sits at reset default, which on this chip family is "disabled/
  analog," not GPIO. `GPIO_PinInit()` alone (direction/data registers)
  has no effect without an explicit `PORT_SetPinConfig(...,
  kPORT_MuxAsGpio, ...)` call first. Fixed in `TriggerInit()`.
- **Still unresolved**: even after that fix, verified via a successful
  flash, the trigger pin has not been observed to toggle in any
  capture on record (PPK2's digital-channel data is constant zero
  throughout). Ruled out: wrong pin (checked against the official
  table), PPK2 digital-channel display setting, wiring (checked on a
  second board too). Root cause not found. Would need a scope directly
  on the pin to diagnose further.
- **Workaround adopted**: since exact per-op boundaries aren't
  available, total measured energy for the whole 100-rep run is split
  across keypair/encaps/decaps proportionally to each operation's
  share of DWT cycles (already measured precisely). This is a modeling
  assumption (uniform power draw per cycle across op types), not an
  independently verified split — documented explicitly everywhere the
  energy numbers are reported.

### 3.4 Board A's hardware fault and the switch to Board B

- After wiring changes around J24, board A's SWD debug connection
  stopped working entirely (`Could not connect to core` / `Probe not
  open`), while the board's UART and general operation stayed
  completely healthy — proving the target chip itself was fine, only
  the debug port was affected.
- Extensive troubleshooting, none of which fixed it: J19 (SWD enable
  jumper) checked untouched, J21 (MCU-Link ISP jumper) used to
  successfully reflash the probe's own firmware (v3.128 → v3.172,
  verified working), other applications checked for holding the probe,
  multiple full power cycles (including a 30-second cold cycle),
  different USB cables/ports, a stale Windows driver cache cleared and
  re-enumerated, and a full uninstall of a SEGGER J-Link installation
  that was a plausible driver-conflict suspect (timing lined up, but
  uninstalling it made no difference).
- Also tried entering the target chip's own ROM bootloader (ISP mode
  via the `SW3`/"ISP" button and the board's second USB port) as an
  alternative flashing path independent of SWD — didn't produce a
  usable enumeration either.
- **Conclusion**: board A has a genuine hardware fault on its SWD path,
  unrelated to the software/setup. A spare board (**board B**) was
  substituted and confirmed working immediately (clean flash, no SWD
  issues) — used for all subsequent captures (ML-KEM-768, ML-KEM-1024,
  and a second independent ML-KEM-512 capture for cross-validation).

### 3.5 Final energy results

Two caveats apply to every number below:
1. Supply voltage assumed at 3.3V (PPK2 Ampere Meter mode doesn't
   report the DUT's actual voltage).
2. Per-operation split is the proportional-cycle-count model described
   above, not an independently measured boundary.

| Variant | Board | Idle baseline | Active window | Total energy (100 reps) | Per-handshake |
|---|---|---|---|---|---|
| ML-KEM-512 | A | 13.45 mA | 7.95 s | 414.08 mJ | 4140.8 µJ |
| ML-KEM-512 | B | 14.20 mA | 7.97 s | 426.13 mJ | 4261.3 µJ |
| ML-KEM-768 | B | 14.06 mA | 12.32 s | 662.89 mJ | 6628.9 µJ |
| ML-KEM-1024 | B | 14.21 mA | 18.19 s | 975.84 mJ | 9758.4 µJ |

ML-KEM-512's two-board agreement (within ~3%) is good reproducibility
evidence, especially notable since it was captured on two physically
different chips.

Per-operation breakdown (proportional split, ML-KEM-512 uses the mean
of both boards):

| Variant | keypair | encaps | decaps |
|---|---|---|---|
| ML-KEM-512 | ~1156 µJ (27.5%) | ~1360 µJ (32.4%) | ~1685 µJ (40.1%) |
| ML-KEM-768 | 1864.9 µJ (28.1%) | 2169.2 µJ (32.7%) | 2594.8 µJ (39.1%) |
| ML-KEM-1024 | 2843.4 µJ (29.1%) | 3192.2 µJ (32.7%) | 3722.8 µJ (38.2%) |

Energy scales with security level in roughly the same proportion as
timing (~1.6× then ~1.47×) — expected, since mean active current stays
in a narrow 14–17 mA band across all three variants.

## 4. Deliverables produced

- **`BENCHMARK_METHODOLOGY.md`** and **`results/eembc_style/
  PQC_BENCHMARK_REPORT.md`** — the full, detailed working record
  (including the debugging history above), kept alongside the project
  source. Untouched by any of the cleanup work below.
- **`results/eembc_style/analyze_perf_memory.py`** /
  **`analyze_energy.py`** — analysis scripts, generate
  `perf_memory_summary.csv` and `energy_summary.csv` from raw captures.
- **`PQC_Benchmark_Report.docx`** (`H:\z_thesis\`) — a full written
  report in plain language for the professor: results tables, charts,
  raw PPK2 waveform plots (styled to match the PPK2 app's own look),
  hardware/software versions, and complete build/reproduction
  instructions, all self-contained in one document.
- **`PQC_Benchmark_Package.zip`** (`H:\z_thesis\`) — a standalone,
  shareable package alongside the report: a cleaned/simplified but
  fully buildable copy of the firmware project (`mlkem_bench/`), the
  two analysis scripts (comments trimmed, methodology explanations
  left only in the Word report), and all raw result data. Verified
  free of any AI/tool mentions. The original project files were never
  modified in producing any of this — everything was written fresh
  into the separate package location.

## 5. Open items / natural next steps

- **Trigger pin still doesn't toggle** — the biggest remaining
  credibility gap in the energy numbers. Needs a scope directly on
  `P0_29` to diagnose further.
- **Voltage is assumed, not measured** — could be closed by adding a
  direct voltmeter reading during capture, or sourcing a known fixed
  voltage instead of relying on the board's own regulator.
- **Interleaved use-case energy** (`gtsrb_policy_singlecore`'s naive/
  static/adaptive policies under the fixed 1230-frame + 41-handshake
  workload) — not yet captured. This is the number most directly tied
  to the thesis's central claim and should be the next priority.
- **J28 (`VDD_CORE_SYS`)** — a more surgically precise measurement
  point (core-only current, excluding USB-IO/analog/VBAT) than J24's
  combined number, identified but not yet attempted.
- Possible strengthening experiments discussed but not started:
  classical-crypto baseline comparison (e.g. X25519) on the same
  board, optimized-vs-reference implementation comparison, a second
  board/MCU family for cross-architecture evidence, and a basic timing
  side-channel check using varied (non-deterministic) inputs.
