# STM32N6570-DK — PQC Benchmark Port Status Report

**Date:** 2026-08-07
**Board:** STM32N6570-DK (STM32N6570 Rev B, Cortex-M55 @ 800 MHz, 4.2 MB SRAM,
128 MB external Octo-SPI flash, TrustZone + RIF security)
**Project:** `pqc_bench_zephyr` (same ML-KEM-768 + ML-DSA-44/65/87 benchmark as
MCXN947 and ESP32-S3 under Zephyr 4.2.0-rc1)

---

## 1. What succeeded

### 1.1 Build — both variants compile cleanly

| Variant | Target | Size | Console |
|---|---|---|---|
| **sb** (serial-boot RAMLOAD) | `stm32n6570_dk/stm32n657xx/sb` | 56,364 B | USART1 (default) |
| **sb + overlay** | same + `stm32n6570_dk.overlay` | 56,364 B | **USART2** (D0/D1) |
| **XIP** (external flash) | `stm32n6570_dk` + sysbuild(mcuboot) | 57,292 B | USART1 |

All build the identical benchmark: ML-KEM-768 (100 reps) + ML-DSA-44/65/87
(2000 sign reps each, 100 keypair/verify each), same PQClean sources, same
instrumentation (rejection-retry counters, `k_cycle_get_32()` timing).

Build system fixes required (all solved):
- MSYS python polluting PATH broke sysbuild board resolution → use Zephyr venv
  west with a clean PATH (`env -u MSYSTEM`)
- `sb` variant default `BOOTLOADER_MCUBOOT` shrinks the RAMLOAD window →
  `-D SB_CONFIG_BOOTLOADER_NONE=y`
- App static RAM (222 KB bss) fits the 512 KB RAMLOAD window after packing
  retry counters to u16 and reducing the bench stack to 144 KB

### 1.2 Board is healthy — NOT bricked, no wipe needed

- The **BOOT1=H requirement is the documented normal behavior** (board doc:
  "To flash: BOOT1=1; To run: BOOT1=0"), not a secure lockout.
- With **BOOT0=0, BOOT1=1** (debug mode), SWD connects and full external-flash
  read/write works.
- **USB DFU** (BOOT0=1, BOOT1=0) loads the app to partition 0x1 and runs it:
  "File download complete ... RUNNING Program ... Start operation achieved
  successfully" (verified multiple times).

### 1.3 External flash programmed

| Address | Content | Status |
|---|---|---|
| `0x70000000` | mcuboot-as-FSBL with ST boot header (`STM2` magic, load/entry) | ✅ flashed |
| `0x70010000` | signed app (`zephyr.signed.bin`) | ✅ flashed |

---

## 2. What is blocked — and why

The app builds, loads, and runs, but **console output cannot be captured**.
Every accessible path was tried:

| Path | Result | Blocker |
|---|---|---|
| SWD + HOTPLUG (BOOT1=H) | Works for flash I/O | — |
| SWD memory read/write (run mode) | **Blocked** | RIF requires Debug Authentication keys (not available) |
| ROM-DFU RAMLOAD (BOOT0=1) | App loads + "RUNNING" | App runs in **secure mode**; no USART output observed (likely faults before console init, or secure context incomplete) |
| XIP external-flash boot (BOOT0=0, BOOT1=0) | No console output | ROM rejects **non-authenticated** (`-nk`) FSBL header for full secure boot; needs ST-signed/authenticated FSBL |
| USB-serial adapter (FTDI, COM12, D0/D1=USART2) | Correct wiring, GND, 115200 | App produces no USART2 output in the ROM-load path |

**Root causes (in order of likelihood):**
1. **The `sb`/secure app crashes or fails to init the console when loaded via
   the ROM's DFU RAM-load** — the Zephyr secure-mode app expects the full
   secure boot context; the ROM DFU path doesn't establish it.
2. **The external-flash boot chain requires an authenticated FSBL** — the STM32N6
   ROM enforces signed boot; the `-nk` (no-key) header is insufficient.
3. **RIF blocks SWD memory access** in non-debug boot states without DA keys.

---

## 3. What would unblock it (options)

1. **ST Debug Authentication keys** — requires an ST enterprise account + NDA +
   the device's provisioning records. Not practical for a dev kit; the kit
   normally ships OPEN (no DA set).
2. **Authenticated FSBL signing** — needs the ST OEM keys (Trusted Package
   Creator / OEMiROT key pair). Not available without ST provisioning.
3. **A known-good reference boot image** — e.g., ST's own `hello_world`-equivalent
   from the STM32Cube FW N6 package (built with the proper ST toolchain + keys),
   which would confirm whether the hardware/secure-chain works at all.
4. **Physical UART probe on USART1 (PE5/PE6)** — already attempted via the ST-Link
   VCOM (COM10); the VCOM bridge is inactive in ROM-boot mode. A direct probe of
   PE5/PE6 with the FTDI adapter (COM12) at the correct pins would bypass the
   VCOM bridge entirely — but PE5/PE6 are the ST-Link bridge pins (not the
   Arduino D0/D1 = USART2).

---

## 4. Status vs the other two boards

| Board | MCXN947 | ESP32-S3 | STM32N6570-DK |
|---|---|---|---|
| Build | ✅ | ✅ | ✅ |
| Flash | ✅ | ✅ | ✅ |
| Run | ✅ | ✅ | ✅ (loaded + RUNNING) |
| **Console capture** | ✅ | ✅ | ❌ (blocked by RIF/secure boot) |
| **Benchmark data** | ✅ complete | ✅ complete | ❌ not captured |

The MCXN947 + ESP32-S3 datasets are complete and cross-validated (worst/median
7.1/6.0/5.9× identical across boards). The STM32N6570-DK port is **built and
ready** but the board's security architecture prevented console capture without
ST provisioning keys.

---

## 5. Artifacts preserved

```
pqc_bench_zephyr/
  build_stm32/pqc_bench_zephyr/zephyr/zephyr.signed.bin   (57 KB, XIP app)
  build_stm32/mcuboot/zephyr/zephyr.fsbl2.bin             (48 KB, FSBL header)
  build_stm32_sb/pqc_bench_zephyr/zephyr/zephyr.bin       (56 KB, sb RAMLOAD)
  build_stm32_sb/pqc_bench_zephyr/zephyr/zephyr.ssbl.bin  (57 KB, signed ssbl)
  stm32n6570_dk.conf                                      (XIP board config)
  stm32n6570_dk.overlay                                   (USART2 console)
  results/stm32n6570_raw.txt                              (empty — no capture)
```

**Recommendation:** the most promising unblock is (4) probing USART1 (PE5/PE6)
directly — the pins the ST-Link VCOM uses — with the FTDI adapter, but they are
not broken out to a user header on this board. If the board can be returned to a
known-good ST demo image (option 3), the secure chain can be validated first.
