# EEMBC SecureMark-Style ML-KEM Benchmark: Methodology

This document specifies, precisely enough for independent reproduction,
how every number in `results/eembc_style/` was produced. It follows the
structure of EEMBC's SecureMark-TLS benchmark (performance + memory +
energy, per-operation, on real hardware, free-running) but targets
ML-KEM instead of SecureMark-TLS's classical ECC/AES/SHA suite, since no
public EEMBC profile currently covers post-quantum KEMs (checked
July 2026 — see `RELATED_WORK_CANDIDATES.md` in `H:\z_thesis\`).

**This is not an official EEMBC score.** SecureMark's published scores use
committee-voted per-operation weights that are not public; this report
gives raw, transparent per-operation numbers plus one clearly-labeled,
openly-justified weighted aggregate (Section 5) — not a number claiming
comparability to a real SecureMark score.

---

## 1. Hardware and firmware under test

- **Board**: NXP FRDM-MCXN947 (dual Cortex-M33 @ 150 MHz, single core used
  for this benchmark — `mlkem_bench` project, single-core, no NPU
  involvement).
- **Toolchain**: Arm GNU 14.2.1 (per this lab's established environment,
  see the global handoff doc).
- **Crypto implementation**: PQClean's `clean` (portable C, not
  hand-optimized assembly) reference implementation of ML-KEM, at all
  three NIST security levels (512 / 768 / 1024). Deliberately the
  *portable* reference, not pqm4's `m4`/`m4f` assembly-optimized variants
  — an honest baseline, not a best-case number. Swapped between variants
  via `H:\z_thesis\swap.ps1 <512|768|1024>`.
- **Randomness**: PQClean's `randombytes.c` is replaced with a
  deterministic xorshift stub (`// INSECURE - BENCHMARKING ONLY` marked in
  source) — standard practice for this lab, makes runs bit-for-bit
  reproducible; explicitly not a security property and never presented as
  one.

## 2. What "one benchmark run" means

Firmware (`hello_world.c`) does, per variant:

1. A DWT cycle-counter sanity check (`dwt_sanity`) — a fixed 1000-iteration
   busy loop, its cycle count printed first, so a reader can sanity-check
   the timer is behaving before trusting any other number in the run.
2. 100 repetitions of: paint the stack (for that op's high-water-mark
   measurement, see Section 4) → reset the cycle counter → run the
   operation (`keypair` / `encaps` / `decaps`) → read the cycle count →
   read the stack high-water-mark → print both as one CSV line.
3. `kem_match`: verifies the encapsulated and decapsulated shared secrets
   are byte-identical (i.e. the crypto actually worked correctly on this
   run, not just ran without crashing) — every run in
   `results/eembc_style/` has `kem_match,1`; any future run without this
   should be treated as producing no valid data.

## 3. Performance measurement (timing)

- **Timer**: ARM Cortex-M `DWT->CYCCNT` (cycle-accurate hardware counter),
  the same mechanism used for every other timing number in this lab
  (`dwt.h`/`dwt_init()`/`dwt_reset()`/`dwt_get()`).
- **Free-running rule (sacred in this lab, see global handoff doc)**:
  flash → physically power-cycle/replug the debug probe if needed to clear
  it → let the target run completely undebugged → capture serial output
  via `capture_serial.ps1` after pressing the physical reset button.
  Debugger-attached timing was established early in this project to
  distort results significantly and is never used for a reported number.
- **Reported values**: mean and standard deviation over 100 repetitions,
  converted from cycles to microseconds using the fixed 150 MHz core
  clock. Standard deviation is small relative to the mean throughout
  (<1% in every case observed) — this is a deterministic algorithm on a
  single-core target with no OS-level scheduling noise, so tight
  variance is expected, not a sign of insufficient sample size.

## 4. Memory measurement (peak stack usage)

**Stack high-water-mark via "stack painting"** — a standard embedded
technique (the same idea as FreeRTOS's `uxTaskGetStackHighWaterMark`,
implemented here directly against the linker's stack-region symbols since
this firmware has no RTOS):

1. Before the operation under test runs, fill every word of the unused
   stack region (from `__StackLimit` up to `current_sp - 128 bytes`,
   the 128-byte gap being a safety margin so the paint operation itself
   never overwrites the live call frame that's about to invoke the
   operation) with a fixed pattern (`0xAAAAAAAA`).
2. Run the operation.
3. Scan from `__StackLimit` upward until the pattern is no longer intact —
   that's the deepest point the stack ever reached during the operation.
   `stack_hwm_bytes` = distance from that point to `__StackTop`.

`__StackLimit`/`__StackTop` come directly from the linker script (visible
in any build's `output.map`, e.g. `__StackTop = ORIGIN(m_data) +
LENGTH(m_data)`, `__StackLimit = __StackTop - STACK_SIZE`) — a 32,768-byte
(32 KiB) region for this project's linker configuration, confirmed by the
firmware's own printed `stack_region_bytes,32768` line at the start of
every run.

**Why measure it this way and not with `-fstack-usage`**: GCC's
`-fstack-usage` (already enabled in this project's build flags) reports
each *function's own* frame size statically, which undercounts real
worst-case stack depth for recursive or deeply-nested call chains and
doesn't observe what the CPU actually does at runtime. The high-water-mark
technique measures the real, dynamic peak — the number that actually
matters for "will this fit in a device with X KB of RAM," which is the
question a memory benchmark needs to answer.

**Constant across repetitions, by construction**: the same input sizes and
same (deterministic) RNG state pattern lead to the same code path every
time, so `stack_hwm_bytes` is identical across all 100 repetitions within
a run (verified — the analysis script asserts this and would flag any
run where it wasn't true, which would indicate data-dependent stack usage
worth investigating separately).

## 5. Code size (flash + RAM footprint)

Not measured at runtime — read directly from the linker's own
authoritative memory-region report, printed by `ninja` at the end of every
build (`m_text` = flash/code region; `m_data` = actual statically-placed
RAM sections, `.data`+`.bss` — this does NOT include the stack/heap
region, which is only symbolically reserved via linker arithmetic
(`__StackLimit`/`__StackTop`) and never appears as an allocated section in
GCC's "Used Size" report). The ~1.5 KB per-variant differences in `m_data`
are therefore genuinely attributable to the differently-sized ML-KEM
public-key/secret-key/ciphertext static buffers declared in
`hello_world.c` (larger security levels → larger keys/ciphertexts), not to
any change in stack/heap accounting. Transcribed into `CODE_SIZE_BYTES`
in `analyze_perf_memory.py`.

## 6. Energy measurement

**Status: working end-to-end, all three variants captured. ML-KEM-512
verified on two independent boards. Per-operation split is currently a
modeling assumption, not a hardware-verified boundary — see caveats
below.**

### How the measurement point was found (worth keeping for the record)

The first attempt used **J25**, initially believed (from a partial
manual excerpt) to break the `P3V3_MCU` rail itself. Physically verified
(multimeter voltage/continuity, then live PPK2 trace against the serial
monitor) that current on this jumper stayed dead flat (~144 µA)
regardless of whether crypto operations were running — proof this was
the wrong rail, not a wiring mistake.

The official FRDM-MCXN947 jumper table (from the Hardware User Guide,
not just the schematic) clarified the real topology: **J24** feeds
`P3V3_MCU` from the board's main `P3V3` rail (default: shorted jumper
cap), and **J25/J26/J27/J28** individually break out `VDD_IO_USB`/
`VDD_ANA`/`VDD_BAT`/`VDD_CORE_SYS` respectively *from* `P3V3_MCU` (each
DNP by default, current normally carried by a 0-ohm resistor). So J25
was never on the core's supply path at all — it was one of those four
downstream, secondary sub-rails.

**J24 was tried next and works**: pulling its jumper cap (no
desoldering — J24 uses a removable cap, not a populated resistor) and
inserting the PPK2 in Ampere-Meter mode across the two pads produces a
current trace that clearly correlates with crypto activity (~13-14 mA
idle baseline, ~16-17 mA during active handshakes, clean transitions).
Confirmed on two separate physical boards (see below) with consistent
results.

Note **J28 (`VDD_CORE_SYS`) is the more surgically precise point** if a
core-only number (excluding USB-IO/analog/VBAT current) is wanted later
— not yet attempted, since J24's combined number was judged good enough
for a first representative result.

### Wiring procedure (J24, confirmed working)

1. Locate **J24** (schematic page 6, "USB & PWR" section) and remove its
   jumper cap — reversible, no soldering.
2. Multimeter sanity check across the two now-open pads (voltage, then
   continuity) before connecting PPK2, same discipline as any other
   jumper on this board.
3. PPK2 in **Ampere Meter mode** (not Source Meter — the board's own USB
   power still supplies the rail; PPK2 only measures the pass-through
   current). Wire VIN to the LDO/`P3V3`-side pad, VOUT to the
   `P3V3_MCU`-side pad, GND common.
4. **Disconnect the serial terminal before capturing** — empirically,
   having a serial connection open (even printing nothing) visibly
   distorts the PPK2 current trace on this setup. Reconnect serial only
   after the capture window has closed, to retrieve buffered results for
   a correctness cross-check.
5. Flashing new firmware requires the board's normal (non-ammetered)
   power path — bridge J24 with a jumper wire for the flash step, then
   remove it again before capturing.

### Firmware

- Build with `cmake -DMLKEM_ENERGY_MODE=ON` (default `OFF`) for
  `hello_world.c`'s `ENERGY_MODE` variant. Toggles a GPIO trigger pin
  around each operation (mirroring SecureMark-TLS's own
  "GPIO for external triggering" approach), buffers all 300 results (100
  reps × 3 ops) and prints them only after the full loop completes
  (UART TX current would otherwise contaminate the trace).
- **Trigger pin**: `P0_29` (Arduino header D2, per the official pinout
  table — confirmed clean, no conflicts). Required an explicit
  `PORT_SetPinConfig(..., .mux = kPORT_MuxAsGpio, ...)` call in
  `TriggerInit()`, since this pin's PORT mux reset-default is
  "disabled/analog," not GPIO, on this chip family — `GPIO_PinInit()`
  alone (direction/data registers only) silently has no effect on the
  physical pin without it.
- **Known unresolved issue**: even after that fix and a verified
  successful flash, the trigger pin has **not been observed to toggle**
  in either capture on record (PPK2's `D0-D7` digital-channel column is
  constant `00000000` throughout both raw CSVs). Root cause not
  identified — ruled out: wrong pin (confirmed against the official
  header table), PPK2 digital-channel display setting, wiring
  (re-checked on a second board). Worth revisiting with a scope on the
  pin directly if precise per-op boundaries are needed later.

### Analysis, in the absence of a working trigger

Since per-op edges aren't available, `analyze_energy.py` locates the
single continuous "active" plateau covering the whole 100-rep run
(boxcar-smoothed threshold detection, to survive the ~10 kHz switching-
regulator ripple on the raw signal), integrates charge over that window,
and converts to energy. Total per-handshake energy is then split across
keypair/encaps/decaps **in proportion to each operation's share of DWT
cycles** — a modeling assumption (uniform power draw per cycle across
op types), not an independent measurement. See the script's docstring
for the full reasoning.

**Two caveats that must travel with any number quoted from this
section**:
1. **Voltage is assumed (3.3V), not measured** — PPK2 Ammeter mode is a
   passive pass-through and doesn't report the DUT's actual rail
   voltage.
2. **Per-operation split is modeled, not measured**, per above.

### Results

| Variant | Board | Idle baseline | Active window | Expected (DWT) | Total energy (100 reps) | Per-handshake |
|---|---|---|---|---|---|---|
| ML-KEM-512 | A (original) | 13.45 mA | 7.95s | 7.22s | 414.08 mJ | 4140.8 µJ |
| ML-KEM-512 | B (spare) | 14.20 mA | 7.97s | 7.22s | 426.13 mJ | 4261.3 µJ |
| ML-KEM-768 | B | 14.06 mA | 12.32s | 11.60s | 662.89 mJ | 6628.9 µJ |
| ML-KEM-1024 | B | 14.21 mA | 18.19s | 17.49s | 975.84 mJ | 9758.4 µJ |

ML-KEM-512 agreement within ~3% across two independent physical boards
— good reproducibility evidence despite the trigger/voltage caveats
above. 768/1024 captured on board B only (board A was already retired
by the time these were run — see hardware note below). All active
windows run somewhat longer than the DWT-predicted duration, consistent
across variants (~10-4% over) — likely a combination of threshold-
detection edge slop and the `ENERGY_MODE` build's `InterOpGap`
busy-waits adding real time between operations that the DWT-only
timing measurement doesn't include.

Raw captures: `energy/mlkem512_board{A,B}_raw.csv`,
`energy/mlkem768_boardB_raw.csv`, `energy/mlkem1024_boardB_raw.csv`.

**Hardware note**: board A developed a genuine SWD debug-port fault
partway through this investigation (`Could not connect to core`,
consistent across every software/driver/firmware remediation tried —
J19/J21 jumpers, USB cables/ports, full power cycles, probe firmware
reflash, Windows driver cache, a SEGGER J-Link install). Board A's UART
and general operation remained completely healthy throughout; only SWD
programming was affected. Switched to a spare board (B) to continue.

### Still to do

- Should also be captured for the **interleaved use-case scenario**
  (`gtsrb_policy_singlecore`'s naive/static/adaptive policies), not just
  standalone crypto ops — total energy to complete the fixed 1230-frame +
  41-handshake workload, per policy, is the number that actually connects
  to this thesis's central claim (does the certified-anytime policy save
  energy, not just time, under real contention).
- If time permits: diagnose the trigger-pin issue (oscilloscope/logic
  probe directly on the physical pin) to replace the proportional-split
  model with real per-op boundaries, and/or repeat on J28 (`VDD_CORE_SYS`)
  for a core-only number.

## 7. Reproducing this benchmark from scratch

```powershell
# from H:\z_thesis
.\swap.ps1 512        # or 768, or 1024
# then, in the project directory, clean-rebuild (see the note below on
# why a full clean of the pqclean object directory is necessary)
Remove-Item -Recurse -Force codebase\projects\mlkem_bench\debug\CMakeFiles\mlkem_bench_cm33_core0.dir\pqclean
cd codebase\projects\mlkem_bench\debug
ninja
# flash via LinkServer, then free-running capture via
# gtsrb_multiexit\tools\golden\capture_serial.ps1 (any project's copy of
# this script works identically -- it's a generic UART capture tool)
```

**Known gotcha, recorded here since it cost real time**: `swap.ps1`
overwrites the *contents* of the `pqclean/*.c` files but keeps the same
*filenames* — `ninja`'s dependency tracking (by file mtime/hash on some
setups, observed here) can incorrectly treat the already-compiled
`.c.obj` files as up to date after a swap, silently linking the PREVIOUS
variant's object code even though the source was replaced. This produces
either a link error (undefined reference to the new variant's symbol
names, as happened when swapping 1024→768 in this session) or, worse,
a *silent* wrong-variant binary if the two variants happen to export
compatible-looking symbols. **Always force-delete the pqclean object
directory before rebuilding after a swap** (see command above) — don't
trust incremental build correctness across a `swap.ps1` invocation.
