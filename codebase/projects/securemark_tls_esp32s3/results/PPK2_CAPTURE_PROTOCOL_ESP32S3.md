# SecureMark-TLS PPK2 Energy Capture — ESP32-S3 (DevKitC-1)

The ESP32-S3 DevKitC-1 has **no J24-style rail-break header** like the NXP
board, so the PPK2 is used in **power-supply mode**: it powers the board's
3.3 V rail directly while measuring the current. This works cleanly here
because (unlike the FRDM-MCXN947) the ESP32-S3 DevKitC has **no on-board
debugger sharing the rail** — the only other 3.3 V consumer is the CP2102
UART bridge, which is 5 V-powered and off when USB is disconnected.

## Firmware state (already prepared)

- The ESP32-S3 currently runs the **free-running SecureMark-TLS -O2 firmware**
  (14/14 CRC, score 1895). It starts the benchmark automatically at boot.
- The full run takes **~225 s (3.5-4 min)**, then the board idles.
- **Do NOT connect any USB to the ESP32-S3 during capture.**

## Wiring (PPK2 → ESP32-S3 DevKitC-1)

The DevKitC-1 has two 40-pin header rows. Use the pins labelled on the
silkscreen:

| PPK2 | ESP32-S3 DevKitC-1 |
|------|--------------------|
| **VOUT** (supply output, set to **3.3 V**) | **3V3** pin (one of the two 3V3 pins on the headers) |
| **GND** | **GND** pin (any GND) |

1. **Disconnect ALL USB** from the ESP32-S3 board (both the "UART" USB and
   the native "USB" connector) so the on-board regulator has no input and the
   PPK2 is the sole power source.
2. Set the PPK2 (nRF Connect / Power Profiler) to **Power Supply mode**,
   **3.3 V**.
3. Connect PPK2 **VOUT → 3V3 pin**, PPK2 **GND → GND pin** (keep leads short;
   the board draws bursts up to ~150 mA).
4. The board should power on (LED on). **Do NOT press EN yet.**

## Capture procedure

1. Start the PPK2 recording (10 kHz, log to CSV).
2. Press the board **EN (reset) button** so the benchmark starts at a known
   time (this is equivalent to the reset-button start used on the NXP board).
3. Wait **~4 minutes** (the run is ~225 s; you can stop at ~270 s — the
   current drops to the idle level after the run completes).
4. Stop the recording and export the CSV.

Expected signature: ~4 minutes of elevated current (roughly 30-60 mA above
the ~15-20 mA idle baseline, with the ECDSA-verify phase the longest), then a
drop back to idle.

## Notes / caveats

- The benchmark prints to the USB Serial/JTAG console, which is **off during
  capture** (USB disconnected) — that is exactly what we want (no serial
  current). The run is confirmed by the current trace, not the console.
- Do **not** use Ampere-meter mode across a header (there is no rail break);
  supply mode is the correct method for this board.
- If the board has an RGB LED that the bootloader blinks, ignore the first
  ~1 s of the trace.
- After capture: reconnect USB to COM17 for the next flash.

## Deliverable

- Save the CSV to `H:\z_thesis\energy resulkts\ppk_securemark_esp32s3_<ts>.csv`
- Tell the assistant the filename; it will run the analyzer
  (`securemark_tls_mcxn947/analyze_securemark_energy.py`) and produce the
  cross-platform energy table.
