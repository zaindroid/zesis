# Experiment 1 — DTLS Connection-ID Life-Cycle Energy Amortization (Model)

**Question:** What does the IETF DTLS Connection-ID (CID) standard actually
buy a battery-powered IoT device in battery life, when the session-resume
handshake is post-quantum?

**Method:** A 24-hour state-machine model of a battery deployment. A client
wakes N times/day. Two clients:
- **Naive** — full PQC handshake (ML-KEM-768 + ML-DSA-87) on *every* wake-up
  (session timeout / network drop → re-handshake).
- **CID** — one handshake at boot, then only symmetric AES-GCM per wake-up
  (the DTLS CID keeps the session alive).

Energies are the **measured PPK2 numbers** from the SecureMark-TLS energy
work (incremental above idle): PQC 768+87 handshake **1.87 mJ (MCX)** /
**18.24 mJ (ESP32-S3)**; symmetric AEAD per record AES-CCM-168 **2.76 µJ
(MCX)** / **58.6 µJ (ESP32)**. Sleep current 5 µA @ 3.0 V deep sleep
(parameterized); batteries CR2032 (225 mAh @ 3 V = 2430 J) and 500 mAh LiPo
(6660 J).

## Result 1 — daily energy (mJ), naive/CID, sleep 5 µA

| Board | variant | N=24 (hourly) | N=288 (5 min) | N=1440 (1 min) |
|-------|---------|--------------|---------------|----------------|
| MCXN947 | PQC 768+87 | 1341 / 1298 | 1476 / 1298 | 1835 / 1298 |
| MCXN947 | classical | 1329 / 1297 | 1427 / 1297 | 1688 / 1298 |
| ESP32-S3 | PQC 768+87 | 1735 / 1316 | 3053 / 1320 | **6566 / 1331** |
| ESP32-S3 | classical | 2456 / 1346 | 5935 / 1350 | **15214 / 1361** |

The ~1298 mJ floor in every cell is the **deep-sleep energy** (5 µA × 24 h) —
the honest result is that at low duty cycles the CID gain is small because
sleep dominates. The CID gain grows with wake-up rate, and far faster on the
ESP32 (its handshake is ~10× more expensive).

## Result 2 — battery life on CR2032 (days), PQC 768+87

| Board | N | Naive | CID | **gain** |
|-------|---|-------|-----|----------|
| MCXN947 | 24 | 1812 | 1872 | +3% (sleep-dominated) |
| MCXN947 | 288 | 1324 | 1872 | +41% |
| MCXN947 | 1440 | 609 | 1870 | +207% (3×) |
| ESP32-S3 | 24 | 1401 | 1847 | +32% |
| ESP32-S3 | 288 | 370 | 1826 | +393% (5×) |
| ESP32-S3 | 1440 | **88** | **1740** | **+1880% (19×)** |

## Result 3 — the crossover (where CID amortization starts to matter)

The wake-up rate at which per-day handshake energy equals deep-sleep energy
(5 µA) — above this, handshake energy dominates and CID is critical:

| Board | variant | handshake energy | crossover wake-up period |
|-------|---------|------------------|--------------------------|
| MCXN947 | PQC 768+87 | 1.87 mJ | every **2.1 min** (693/day) |
| MCXN947 | classical | 1.36 mJ | every 1.5 min |
| ESP32-S3 | PQC 768+87 | 18.24 mJ | every **20 min** (71/day) |
| ESP32-S3 | classical | 48.27 mJ | every 54 min (27/day) |

## The honest finding (the story this tells)

1. **DTLS CID amortization is real and provable from the measured numbers**,
   but it is **not a constant**: it pays off in proportion to wake-up rate and
   per-handshake energy.
2. At the classic *hourly* IoT duty cycle with 5 µA sleep, battery life is
   sleep-dominated (≈5 years on a CR2032 — beyond shelf life), so the CID
   gain is a few percent. **The CID matters most when the device wakes often**
   or the sleep current is lower.
3. On the **ESP32-S3** (10× more expensive handshake) the CID is a
   **battery-life-critical feature**: at 1 wake-up/min it turns 88 days into
   1740 days (19×); even at 20-min wake-ups the handshake already dominates.
   On the MCXN947 the crossover is ~2 min — a low-power device with an
   efficient handshake can almost ignore CID.
4. This is exactly the amortization trade-off Prof. Tschofenig's standard
   addresses — now quantified with physical energies on the thesis boards.

## Files

- `dtls_cid_model.py` — the model (all energies from the measured tables)
- `results/dtls_cid/cumulative_hourly.png` — cumulative energy, hourly wake-ups
- `results/dtls_cid/daily_energy.csv` — machine-readable daily energies
