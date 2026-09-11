# 03 — Classical Baseline (EEMBC SecureMark-TLS) + Migration

- `mcxn947/` — official EEMBC SecureMark-TLS: **5472 marks, 14/14 CRC pass**.
- `esp32s3/` — same benchmark: **1895 marks (-O2), 14/14 CRC pass**.
- `migration/` — classical→PQC TLS handshake ECC-phase migration:
  MCX −35…+38%, ESP32 **−62…−82%** (PQC cheaper on ESP32); energy
  per-handshake (ULPMark-style) both boards; DTLS-CID life-cycle daily energy.

Raw: `../data/serial_captures/serial_securemark_tls_*`,
`../data/energy_ppk2/energy_securemark_tls_*`.
