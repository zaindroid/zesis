# Free-Running Interleaved Energy Capture — PPK2 Protocol

**Board:** FRDM-MCXN947 (Cortex-M33 @ 150 MHz, eIQ Neutron NPU)
**Purpose:** Measure genuine on-device energy for the three policies
(NAIVE / STATIC / ADAPTIVE) with the interleaved ML-KEM-768 + perception
workload, using a **free-running** firmware (no host UART during capture).

**Why free-running matters:** the earlier n=140 capture was host-driven
(frames streamed over UART) — on-device compute was <1% of the trace, so
energy deltas were invalid (inverted). This protocol fixes that.

---

## 1. What the firmware does (verified)

On **reset**, the firmware:
1. Prints `FREERUN: <POLICY>` + `WORKLOAD_START` (USART0 debug console)
2. Runs **140 frames** (embedded images, 94/140 = 67.1% safety-critical)
   with an ML-KEM-768 crypto step every 10 frames
   (140/10 = 14 crypto steps → 4 handshake cycles: keypair→encap→decap)
3. Buffers every frame result in RAM (exit, tier, timings)
4. Prints `WORKLOAD_DONE handshakes=4`, `RESULTS_BEGIN`, the 140 result
   rows, `RESULTS_END`

**Policies** (compile-time, one binary each):
- **NAIVE** — always run all 3 segments to exit 3
- **STATIC** — certified menu α=0.05, fixed tier (exit1/exit3 only; exit2
  not certified at 0.05 → never used)
- **ADAPTIVE** — α=0.05 normally; shifts to certified α=0.10 tier near
  crypto steps (enables exit2 only in tier 10)

## 2. Binaries (verified to contain the 140-frame image data)

| Policy | Binary | Size |
|---|---|---|
| NAIVE | `tools/hw_freerun/freerun_naive_final.bin` | 2,016,256 B |
| STATIC | `tools/hw_freerun/freerun_static_final.bin` | 2,016,256 B |
| ADAPTIVE | `flash_debug/gtsrb_multiexit_cm33_core0.bin` (or `tools/hw_freerun/freerun_adaptive_final.bin`) | 2,016,256 B |

Flash via LinkServer: `LinkServer.exe flash -p 0V5USKFHVAZTY auto load "<bin>:0x00000000"`

## 3. PPK2 setup (per the lab methodology)

1. **J24 jumper removed** — isolate the MCU current rail (IDD_MCU / P3V3_MCU)
2. **PPK2 in Ampere Meter mode**, connected across J24
   (current path: PPK2 SMPS → J24 → board)
3. **Assumed voltage: 3.3 V** (PPK2 source; consistent with the analysis script)
4. **Serial DISCONNECTED during capture** (no USB-UART to host — the
   firmware is free-running, it doesn't need the host)
5. Board powered via PPK2 (or via ST-Link USB power for convenience —
   but PPK2 must be in the current path to measure the MCU rail)

## 4. Capture procedure (per policy)

For each policy (NAIVE, STATIC, ADAPTIVE):

1. **Flash** the policy binary (LinkServer, serial OK to connect here)
2. **Disconnect** the serial/USB-UART from the host
3. **Arm the PPK2** capture (Ampere Meter, 10 kHz sampling, >10 s window —
   the 140-frame workload + 4 handshakes completes in ~2–4 s)
4. **Press the board's RESET button** (this starts the free-running workload)
5. Wait for the capture to finish (~5 s), stop PPK2
6. **Reconnect serial**, read the buffered results
   (`WORKLOAD_DONE`, `RESULTS_BEGIN` ... 140 rows ... `RESULTS_END`)
7. Save: `ppk_<policy>_raw.csv` (PPK2 export) + `policy_results_<policy>.csv`

Repeat for all three policies.

## 5. Analysis (existing script)

`results/interleaved/analyze_interleaved.py`:
- Active-window detection (smoothed median/percentile thresholding)
- Energy = trapz(current) × 3.3 V → mJ
- Per-policy: wall-clock, total energy, deadline misses (33 ms @ 30 fps),
  exit distribution, per-exit safety-critical miss rate
- **Adaptive-vs-naive** and **adaptive-vs-static** deltas
- **Certified-bound check**: per-exit SC miss rate among accepted ≤ α

Run: `python3 results/interleaved/analyze_interleaved.py` with the new
captures in `results/interleaved/`.

## 6. Caveats (honest)

- **140 frames, 4 handshakes** (not 1200/40): the full workload needs
  8.3 MB QSPI flash (not confirmed populated). The 140-frame embedded
  subset preserves the safety-critical ratio (67.1%) and is **free-running
  valid** — the energy deltas are now meaningful even if the sample is
  smaller.
- The **NPU is not used** — the three exit segments run on the CPU
  (Cortex-M33) via TFLite Micro. The NPU path (eIQ) is a separate
  experiment (option B in the thesis roadmap).
- Trigger GPIO (P0_31) exists but the **PPK2 trace itself** is the primary
  measurement; the GPIO gate is optional.
