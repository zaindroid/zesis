#!/usr/bin/env python3
"""Classical (SecureMark-TLS) vs PQC (ML-KEM/ML-DSA) migration comparison
on the NXP FRDM-MCXN947 (Cortex-M33 @ 150 MHz). All numbers recomputed
independently from the raw captures/CSVs."""
import csv, os, statistics

PROJ = r"H:\z_thesis\codebase\projects"

# ---------- SecureMark-TLS classical primitives (MCXN947) ----------
# From securemark_score.txt: ips per component. weights from sm_main.c g_task[].
sm_score = {}
with open(os.path.join(PROJ, "securemark_tls_mcxn947", "results", "securemark_score.txt")) as f:
    for line in f:
        if "Component #" in line and "ips=" in line:
            ips = float(line.split("ips=")[1].split()[0])
            crc = line.split("crc=")[1].split()[0]
            sm_score[len(sm_score)] = (ips, crc)

# task table (n, weight) from sm_main.c
tasks = [  # (n, weight, name)
    (144, 1.0, "AES-ECB-144"), (224, 1.0, "AES-ECB-224"), (320, 1.0, "AES-ECB-320"),
    (52, 1.0, "AES-CCM-52"), (168, 1.0, "AES-CCM-168"),
    (0, 1.0, "ECDH P-256"), (0, 1.0, "ECDSA sign"), (0, 2.0, "ECDSA verify"),
    (23, 3.0, "SHA-256-23"), (57, 1.0, "SHA-256-57"), (384, 1.0, "SHA-256-384"),
    (0, 3.0, "variation-001"), (4224, 4.0, "SHA-256-4224"), (2048, 10.0, "AES-ECB-2048"),
]
classical = {}
for i, (n, w, name) in enumerate(tasks):
    ips, crc = sm_score[i]
    classical[name] = {"ips": ips, "us_per_op": 1e6 / ips, "weight": w, "crc": crc}

# ---------- ML-KEM (MCXN947, bare-metal, -O0) ----------
mlkem = {}
with open(os.path.join(PROJ, "mlkem_bench", "results", "eembc_style", "perf_memory_summary.csv")) as f:
    for row in csv.DictReader(f):
        key = row["variant"].replace("ML-KEM-", "")
        mlkem.setdefault(key, {})[row["op"]] = float(row["mean_us"])

# ---------- ML-DSA (MCXN947, bare-metal, -O2) ----------
def dsa_mean(fname, begin, end):
    rows = []
    in_sec = False
    for line in open(fname):
        line = line.strip()
        if line == begin: in_sec = True; continue
        if line == end: in_sec = False; continue
        if in_sec and line and line[0].isdigit():
            rows.append(int(line.split(",")[0]))
    return statistics.mean(rows) / 150.0  # cycles @150MHz -> us

def dsa_sign_median(fname):
    vals = []
    for line in open(fname):
        if line.startswith("cycles"): continue
        vals.append(int(line.split(",")[0]))
    return statistics.median(vals) / 150.0

mldsa = {}
for lvl, name in [("44", "ML-DSA-44"), ("65", "ML-DSA-65"), ("87", "ML-DSA-87")]:
    base = os.path.join(PROJ, "mldsa_bench_nxp", "results")
    kp = dsa_mean(os.path.join(base, f"mldsa{lvl}_raw.txt"), "KP_BEGIN", "KP_END")
    vf = dsa_mean(os.path.join(base, f"mldsa{lvl}_raw.txt"), "VF_BEGIN", "VF_END")
    sg = dsa_sign_median(os.path.join(base, f"mldsa{lvl}_sign_raw.csv"))
    mldsa[lvl] = {"kp_us": kp, "verify_us": vf, "sign_median_us": sg}

# ---------- Security levels (NIST) ----------
# P-256 = L1. ML-KEM-512=L1, 768=L3, 1024=L5. ML-DSA-44=L2, 65=L3, 87=L5.

# ---------- TLS 1.2 handshake crypto phase model (EEMBC 14-phase) ----------
# Per handshake (measured-device perspective), classical:
#   1 x ECDH key exchange, 1 x ECDSA sign, 2 x ECDSA verify, + AES/SHA bulk.
# PQC replacement: ML-KEM (kp+enc+dec on the two endpoints) + ML-DSA sign/verify.
def handshake_classical():
    ecdh = classical["ECDH P-256"]["us_per_op"]
    sg = classical["ECDSA sign"]["us_per_op"]
    vf = classical["ECDSA verify"]["us_per_op"]
    aes_ccm = classical["AES-CCM-168"]["us_per_op"]
    sha = classical["SHA-256-384"]["us_per_op"]
    # EEMBC phase mix: also bulk AES-ECB-2048 (10 ops) + handshake hashing
    bulk = 10 * classical["AES-ECB-2048"]["us_per_op"]
    return {"ecdh_us": ecdh, "sig_us": sg, "ver_us": 2 * vf,
            "aes_ccm_us": aes_ccm, "sha_us": sha, "bulk_us": bulk}

def handshake_pqc(kem_lvl, dsa_lvl):
    kem = mlkem[kem_lvl]
    d = mldsa[dsa_lvl]
    kem_total = kem["keypair"] + kem["encaps"] + kem["decaps"]
    return {"kem_us": kem_total, "dsa_sig_us": d["sign_median_us"],
            "dsa_ver_us": 2 * d["verify_us"]}

print("=" * 78)
print("CLASSICAL vs PQC on FRDM-MCXN947 (Cortex-M33 @ 150 MHz)")
print("=" * 78)
print(f"\n-- SecureMark-TLS (classical, mbedTLS -O2) --")
for k, v in classical.items():
    print(f"  {k:15s} {v['us_per_op']:9.1f} us/op  ({v['ips']:9.1f} ips)  crc={v['crc']}")
print(f"\n-- ML-KEM (PQClean, -O0) --")
for lvl in ("512", "768", "1024"):
    k = mlkem[lvl]
    print(f"  ML-KEM-{lvl}: kp {k['keypair']:7.1f}  enc {k['encaps']:7.1f}  dec {k['decaps']:7.1f}  total {k['keypair']+k['encaps']+k['decaps']:8.1f} us")
print(f"\n-- ML-DSA (PQClean, -O2) --")
for lvl in ("44", "65", "87"):
    d = mldsa[lvl]
    print(f"  ML-DSA-{lvl}: kp {d['kp_us']:7.1f}  sign-med {d['sign_median_us']:7.1f}  verify {d['verify_us']:7.1f} us")

hc = handshake_classical()
print(f"\n-- TLS 1.2 handshake crypto (EEMBC phase model, one device) --")
print(f"  Classical ECC:  ECDH {hc['ecdh_us']:.1f} + sign {hc['sig_us']:.1f} + 2x verify {hc['ver_us']:.1f} = {hc['ecdh_us']+hc['sig_us']+hc['ver_us']:.1f} us")
print(f"  + AES-CCM {hc['aes_ccm_us']:.1f} + SHA {hc['sha_us']:.1f} + bulk AES {hc['bulk_us']:.1f} us (stay classical)")
print()
rows = []
for kl in ("512", "768", "1024"):
    for dl in ("44", "65", "87"):
        hp = handshake_pqc(kl, dl)
        ecc_total = hc["ecdh_us"] + hc["sig_us"] + hc["ver_us"]
        pqc_total = hp["kem_us"] + hp["dsa_sig_us"] + hp["dsa_ver_us"]
        delta = (pqc_total - ecc_total) / ecc_total * 100
        rows.append((kl, dl, pqc_total, ecc_total, delta))
rows.sort(key=lambda r: r[4])
print(f"  {'KEM':8s} {'DSA':8s} {'PQC ECC-phases':>15s} {'Classical':>11s} {'Delta':>8s}")
for kl, dl, pqc, ecc, dlt in rows:
    print(f"  {kl:8s} {dl:8s} {pqc:15.1f} {ecc:11.1f} {dlt:+7.1f}%")

# NIST-level-matched comparison
print(f"\n-- NIST level-matched (fair security comparison) --")
# L1: P-256 (128-bit) vs ML-KEM-512 + ML-DSA-44
ecc_l1 = hc["ecdh_us"] + hc["sig_us"] + hc["ver_us"]
pqc_l1 = handshake_pqc("512", "44")
l1_total = pqc_l1["kem_us"] + pqc_l1["dsa_sig_us"] + pqc_l1["dsa_ver_us"]
print(f"  L1: classical P-256 ECC {ecc_l1:8.1f} us  vs  ML-KEM-512+ML-DSA-44 {l1_total:8.1f} us  ({100*(l1_total-ecc_l1)/ecc_l1:+.1f}%)")
# L3: ML-KEM-768 + ML-DSA-65 (no classical 192-bit equivalent; P-256 is the practical baseline)
pqc_l3 = handshake_pqc("768", "65")
l3_total = pqc_l3["kem_us"] + pqc_l3["dsa_sig_us"] + pqc_l3["dsa_ver_us"]
print(f"  L3: classical P-256 ECC {ecc_l1:8.1f} us  vs  ML-KEM-768+ML-DSA-65 {l3_total:8.1f} us  ({100*(l3_total-ecc_l1)/ecc_l1:+.1f}%)")

# save machine-readable summary
with open(os.path.join(PROJ, "securemark_tls_mcxn947", "results", "migration_summary.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["item", "us_per_op", "source"])
    for k, v in classical.items():
        w.writerow([f"classical_{k}", f"{v['us_per_op']:.2f}", "SecureMark-TLS"])
    for lvl in ("512", "768", "1024"):
        k = mlkem[lvl]
        w.writerow([f"mlkem{lvl}_kp", f"{k['keypair']:.2f}", "mlkem_bench"])
        w.writerow([f"mlkem{lvl}_enc", f"{k['encaps']:.2f}", "mlkem_bench"])
        w.writerow([f"mlkem{lvl}_dec", f"{k['decaps']:.2f}", "mlkem_bench"])
    for lvl in ("44", "65", "87"):
        d = mldsa[lvl]
        w.writerow([f"mldsa{lvl}_kp", f"{d['kp_us']:.2f}", "mldsa_bench_nxp"])
        w.writerow([f"mldsa{lvl}_sign_med", f"{d['sign_median_us']:.2f}", "mldsa_bench_nxp"])
        w.writerow([f"mldsa{lvl}_verify", f"{d['verify_us']:.2f}", "mldsa_bench_nxp"])
print("\nmigration_summary.csv written")
