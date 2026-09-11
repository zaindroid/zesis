#!/usr/bin/env python3
"""Experiment 1: DTLS Connection-ID life-cycle energy amortization model.

A 24-hour battery-powered deployment where an IoT client wakes up N times per
day. Two clients:
  - NAIVE: performs a full post-quantum handshake on EVERY wake-up (session
    timeout / network drop -> re-handshake).
  - CID  : standards-compliant DTLS Connection IDs keep the session alive;
    only symmetric AES-GCM runs after the initial handshake.

All energies are MEASURED on the thesis boards (PPK2, incremental above idle):
  - PQC handshake (ML-KEM-768 + ML-DSA-87): MCX 1.87 mJ, ESP32-S3 18.24 mJ
  - PQC handshake (ML-KEM-768 + ML-DSA-44): MCX 0.89 mJ, ESP32-S3 8.66 mJ
  - Classical ECC handshake (ECDH+1 sign+2 verify): MCX 1.36 mJ, ESP32 48.27 mJ
  - Symmetric AEAD per record (AES-CCM-168 proxy): MCX 2.76 uJ, ESP32 58.6 uJ
  - Conservative symmetric upper bound (AES-GCM on 4.6 kB, measured in the
    split-inference bench): MCX 1.0 mJ
Sleep current is a parameter (deep-sleep 1-50 uA typical); battery CR2032
225 mAh @ 3.0 V (2430 J) and 500 mAh LiPo @ 3.7 V (6660 J).
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os, csv

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "dtls_cid")
os.makedirs(OUT, exist_ok=True)

# ---------- measured energies (J) ----------
HS = {  # handshake energy per event, per platform / variant
    "MCX":  {"pqc87": 1.87e-3, "pqc44": 0.89e-3, "classic": 1.36e-3},
    "ESP32": {"pqc87": 18.24e-3, "pqc44": 8.66e-3, "classic": 48.27e-3},
}
REC = {  # symmetric AEAD per record (J)
    "MCX":  {"ccm168": 2.76e-6, "gcm46k": 1.0e-3},   # conservative upper bound
    "ESP32": {"ccm168": 58.6e-6, "gcm46k": None},    # not measured -> skip
}
V = 3.0

def sleep_energy_j(islp_ua, hours_active_h):
    return islp_ua * 1e-6 * V * (24.0 - hours_active_h) * 3600.0

def run_model(board, variant, rec_kind, n_wake, islp_ua, t_active_s=0.1):
    """Return (E_naive_J, E_cid_J) per day."""
    e_hs = HS[board][variant]
    e_rec = REC[board][rec_kind] or 0.0
    hours_active = n_wake * t_active_s / 3600.0
    e_slp = sleep_energy_j(islp_ua, hours_active)
    e_naive = n_wake * (e_hs + e_rec) + e_slp
    e_cid = e_hs + n_wake * e_rec + e_slp
    return e_naive, e_cid

# ---------- 1) cumulative energy over 24 h (hourly wake-ups, 5 uA sleep) ----------
t_h = np.arange(0, 25, 1.0)
rows = []
for board, bname in (("MCX", "MCXN947"), ("ESP32", "ESP32-S3")):
    for variant, vname in (("pqc87", "PQC 768+87"), ("classic", "classical")):
        e_hs = HS[board][variant]
        e_rec = REC[board]["ccm168"]
        cum_naive = np.cumsum(np.concatenate(([0], [e_hs + e_rec] * 24)))
        cum_cid = np.cumsum(np.concatenate(([e_hs], [e_rec] * 24)))
        plt.plot(t_h, cum_naive * 1e3, "-o", label=f"{bname} {vname} naive")
        plt.plot(t_h, cum_cid * 1e3, "--s", label=f"{bname} {vname} CID")
plt.xlabel("time (h)"); plt.ylabel("cumulative comm energy (mJ)")
plt.title("DTLS Connection-ID: cumulative energy, hourly wake-ups, 5 uA sleep")
plt.legend(fontsize=7); plt.grid(alpha=0.3)
plt.savefig(os.path.join(OUT, "cumulative_hourly.png"), dpi=120); plt.close()

# ---------- 2) daily energy vs wake-up frequency ----------
ns = [24, 48, 96, 288, 1440, 2880]   # hourly .. every 30 s
print("=" * 92)
print("DAILY COMM+COMM-SLEEP ENERGY (mJ) vs wake-ups/day  [sleep 5 uA, t_active 0.1 s]")
print("=" * 92)
print(f"{'board':8s} {'variant':10s} {'N=24':>8s} {'N=96':>8s} {'N=288':>8s} {'N=1440':>8s}")
csv_rows = []
for board, bname in (("MCX", "MCXN947"), ("ESP32", "ESP32-S3")):
    for variant, vname in (("pqc87", "PQC 768+87"), ("pqc44", "PQC 768+44"), ("classic", "classical")):
        e_hs = HS[board][variant]; e_rec = REC[board]["ccm168"]
        vals_n = []; vals_c = []
        for n in ns:
            e_naive, e_cid = run_model(board, variant, "ccm168", n, 5.0)
            vals_n.append(e_naive * 1e3); vals_c.append(e_cid * 1e3)
        print(f"{bname:8s} {vname:10s} "
              + " ".join(f"{vals_n[i]:6.1f}/{vals_c[i]:6.1f}" for i in (0, 1, 2, 3)))
        for n, vn, vc in zip(ns, vals_n, vals_c):
            csv_rows.append([board, vname, n, round(vn, 3), round(vc, 3),
                             round(100 * (vn - vc) / vn, 2)])
with open(os.path.join(OUT, "daily_energy.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["board", "variant", "wakeups_per_day",
                                   "naive_mJ", "cid_mJ", "savings_pct"])
    w.writerows(csv_rows)

# ---------- 3) crossover: wake-up rate where handshake energy ~ sleep energy ----------
print("\nCROSSOVER: wake-ups/day where comm (handshake) energy = deep-sleep energy")
print(f"{'board':8s} {'variant':10s} {'E_hs (mJ)':>10s} {'N* at 5uA':>10s} {'N* at 1uA':>12s} {'period':>10s}")
for board, bname in (("MCX", "MCXN947"), ("ESP32", "ESP32-S3")):
    for variant, vname in (("pqc87", "PQC 768+87"), ("pqc44", "PQC 768+44"), ("classic", "classical")):
        e_hs = HS[board][variant]
        for islp in (5.0, 1.0):
            e_slp = sleep_energy_j(islp, 0.0)   # ~1.3 J @5uA, 0.26 J @1uA
            nstar = e_slp / e_hs
            if islp == 5.0:
                period = 24 * 3600 / nstar
                print(f"{bname:8s} {vname:10s} {e_hs*1e3:10.2f} {nstar:10.0f} "
                      f"{(e_slp/1e-6*1e-6/e_hs if False else 0):>12} {period:6.0f} s")
# clean crossover table
print("\n(wake-up period at which handshake energy = sleep energy @ 5 uA deep sleep)")
for board, bname in (("MCX", "MCXN947"), ("ESP32", "ESP32-S3")):
    for variant, vname in (("pqc87", "PQC 768+87"), ("classic", "classical")):
        e_hs = HS[board][variant]
        e_slp5 = sleep_energy_j(5.0, 0.0)
        n5 = e_slp5 / e_hs
        print(f"  {bname:8s} {vname:10s}: every {24*3600/n5:6.0f} s "
              f"({24*3600/n5/60:.1f} min)  -> {n5:.0f} wake-ups/day")

# ---------- 4) battery life (days) ----------
print("\nBATTERY LIFE (days) on CR2032 (225 mAh @ 3.0 V = 2430 J) and 500 mAh LiPo (6660 J)")
print(f"{'board':8s} {'variant':10s} {'N':>5s} {'batt':>7s} {'naive':>7s} {'CID':>7s} {'gain':>6s}")
for batt_j, bname_b in ((2430.0, "CR2032"), (6660.0, "LiPo")):
    for board, bname in (("MCX", "MCXN947"), ("ESP32", "ESP32-S3")):
        for variant, vname in (("pqc87", "PQC 768+87"),):
            for n in (24, 288, 1440):
                e_n, e_c = run_model(board, variant, "ccm168", n, 5.0)
                d_n = batt_j / e_n; d_c = batt_j / e_c
                print(f"{bname:8s} {vname:10s} {n:5d} {bname_b:7s} {d_n:6.1f} {d_c:6.1f} "
                      f"{d_c/d_n-1:5.0%}")

print(f"\nplots + CSV written to {OUT}")
