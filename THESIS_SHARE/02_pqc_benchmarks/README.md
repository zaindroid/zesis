# 02 — PQC Benchmarks (per board)

- `mcxn947/` — ML-KEM-512/768/1024 (latency/stack/energy), ML-DSA-44/65/87
  (fat-tail, worst/median 6–8×), conformal latency certificates, pqm4
  M4F→M33 post-mortem (CFSR.UNSTKERR).
- `esp32s3/` — ML-DSA-44/65/87 signing (2000 reps/level, 0 verify failures).
- `zephyr/` — the matched cross-platform dataset (same Zephyr code both
  boards): ML-KEM-768 + ML-DSA, worst/median IDENTICAL across boards.
- `stm32n6570/` — status of the STM32 port (buildable; console blocker
  documented).

Raw serial logs: `../data/serial_captures/serial_mlkem*_mcxn947.txt`,
`serial_mldsa*_mcxn947.txt`, `serial_mldsa*_esp32s3.txt`.
