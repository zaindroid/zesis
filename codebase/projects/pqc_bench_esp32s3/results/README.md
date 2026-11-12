# ML-KEM-768 library comparison on the ESP32-S3

The same pairing as the FRDM-MCXN947 four-way table, on the second board. Only
two implementations are measurable here: pqm4 is Cortex-M4F assembly and does not
run on Xtensa, so the two pqm4 variants drop out. What remains is the question the
M33 result could not answer on its own — is the wolfSSL-vs-PQClean gap a property
of the library, or of the core?

## Result

| Board | CPU | Clock | Implementation | keypair | encapsulate | decapsulate | encaps cycles | n | ratio |
|---|---|---|---:|---:|---:|---:|---:|---:|
| FRDM-MCXN947 | Cortex-M33 | 150 MHz | wolfSSL native | 7.01 ms | **6.37 ms** | — | 955,000 | 30 | **2.41x** |
| FRDM-MCXN947 | Cortex-M33 | 150 MHz | PQClean clean C | 13.86 ms | 15.33 ms | — | 2,299,500 | 100 | 1.00x |
| ESP32-S3 | Xtensa LX7 | 240 MHz | wolfSSL native | 4.87 ms | **6.38 ms** | 7.26 ms | 1,530,237 | 50 | **1.36x** |
| ESP32-S3 | Xtensa LX7 | 240 MHz | PQClean clean C | 7.68 ms | 8.68 ms | 9.95 ms | 2,083,436 | 50 | 1.00x |

All at -O2. Zero round-trip failures on either board (KEM decapsulation recovers
the encapsulated secret exactly, checked per iteration).

## What it means

**The ranking holds: wolfSSL is faster than PQClean on both cores.** That part is
robust and reproducible.

**The magnitude does not hold: 2.41x on the Cortex-M33, 1.36x on the Xtensa.**
So the earlier two-library comparison was partly measuring the core, not just the
library. Quoting 2.41x as "the wolfSSL advantage" without a board attached would
overstate it.

The cycle counts explain where the difference comes from. PQClean's encapsulate
costs *fewer* cycles on the Xtensa (2.08M) than on the M33 (2.30M), while
wolfSSL's costs considerably more (1.53M against 955K). The gap narrows because
the reference implementation is relatively better on this core and the optimised
one is relatively worse — which is what one would expect if wolfSSL's advantage
comes from Cortex-M-specific work.

The wall-clock figures invert for the same reason: 6.38 ms on the Xtensa against
6.37 ms on the M33, despite a 1.6x clock advantage, because the Xtensa needs 60%
more cycles to do the same work. Cycle count is the fair cross-architecture metric
here; milliseconds are not.

## Method

Both implementations measured in one firmware, same loop, same deterministic RNG
seed, Xtensa CCOUNT for timing at 240 MHz. PQClean comes from the vendored copy in
`projects/pqc_bench_zephyr/pqclean/mlkem768/` — the exact source already measured
on the M33 — because PQClean upstream's `clean/` variant no longer ships
`verify.c`, which the decapsulation path needs.

## Files

| File | Contents |
|---|---|
| `ESP32S3_LIBRARY_SUMMARY.csv` | the table above, machine-readable |
| `esp32s3_raw.txt` | raw serial capture, 50 iterations of each implementation |

## Reproducing

```bash
cd codebase/projects/pqc_bench_esp32s3
bash scripts/build.sh build
python -m esptool --chip esp32s3 --port <COM> --baud 460800 write_flash \
  0x0 bootloader/bootloader.bin 0x8000 partition_table/partition-table.bin \
  0x10000 pqc_bench_esp32s3.bin
```

The firmware waits 8 s before printing, because output emitted before the host
opens the USB Serial/JTAG port is lost.
