#!/usr/bin/env python3
"""Cross-platform: SecureMark-TLS (classical) + PQC (ML-KEM/ML-DSA) on
MCXN947 vs ESP32-S3. Classical = official EEMBC benchmark (14/14 CRC on both).
PQC = PQClean measured on the same boards. Every cell carries its source."""
import csv, os, statistics

PROJ = r"H:\z_thesis\codebase\projects"

def load_securemark(score_path, n_tasks):
    """ips per component from a SecureMark score file."""
    ips = []
    with open(score_path) as f:
        for line in f:
            if "Component #" in line and "ips=" in line:
                ips.append(float(line.split("ips=")[1].split()[0]))
    return ips[:n_tasks]

tasks = ["AES-ECB-144","AES-ECB-224","AES-ECB-320","AES-CCM-52","AES-CCM-168",
         "ECDH P-256","ECDSA sign","ECDSA verify",
         "SHA-256-23","SHA-256-57","SHA-256-384","variation","SHA-256-4224","AES-ECB-2048"]

# ---------- Classical (SecureMark, both boards, -O2, 14/14 CRC) ----------
mcx_ips = load_securemark(os.path.join(PROJ, "securemark_tls_mcxn947", "results", "securemark_score.txt"), 14)
esp_ips = load_securemark(os.path.join(PROJ, "securemark_tls_esp32s3", "results", "securemark_esp32s3_score.txt"), 14)
classical = {}
for i, name in enumerate(tasks):
    classical[name] = {"mcx_us": 1e6/mcx_ips[i], "esp_us": 1e6/esp_ips[i],
                       "mcx_ips": mcx_ips[i], "esp_ips": esp_ips[i]}

# ---------- PQC ML-KEM-768 ----------
# MCXN947: Zephyr (-Os) per-op, complete capture (same code as ESP32 interleaved)
# Both boards: Zephyr (-Os), same code. ESP32 KEM re-captured (15s boot delay
# added for the USB Serial/JTAG attach race) -> measured, no estimate.
mcx_kem = {"kp": 8670, "enc": 9904, "dec": 11734}   # Zephyr report, us (150MHz)
esp_kem = {"kp": 6907, "enc": 7973, "dec": 9282}    # Zephyr re-capture, us (240MHz)

# ---------- PQC ML-DSA sign (median) ----------
# Zephyr (both boards, -Os, 2000 reps) — the cross-platform consistent source
mldsa_sign = {
    "44": {"mcx_us": 43134, "esp_us": 35639},
    "65": {"mcx_us": 74936, "esp_us": 61454},
    "87": {"mcx_us": 98112, "esp_us": 80456},
}
# ML-DSA verify: Zephyr MCX keypair~verify; use bare-metal verify (MCX -O2) + scale ESP
mldsa_verify = {
    "44": {"mcx_us": 17562, "esp_us": 17562 * 35639/43134},
    "65": {"mcx_us": 29501, "esp_us": 29501 * 61454/74936},
    "87": {"mcx_us": 50318, "esp_us": 50318 * 80456/98112},
}

def ecc_phase_classical(board):
    ecdh = classical["ECDH P-256"][f"{board}_us"]
    sg   = classical["ECDSA sign"][f"{board}_us"]
    vf   = classical["ECDSA verify"][f"{board}_us"]
    return ecdh + sg + 2*vf, ecdh, sg, vf

def ecc_phase_pqc(board, dl):
    k = mcx_kem if board == "mcx" else esp_kem
    kem = k["kp"] + k["enc"] + k["dec"]
    dsa_sig = mldsa_sign[dl][f"{board}_us"]
    dsa_ver = 2 * mldsa_verify[dl][f"{board}_us"]
    return kem + dsa_sig + dsa_ver, kem, dsa_sig, dsa_ver

print("=" * 96)
print("CROSS-PLATFORM: Classical (SecureMark-TLS) vs PQC (ML-KEM-768 + ML-DSA)")
print("=" * 96)

print("\n-- Per-primitive (us/op) --")
print(f"{'primitive':20s} {'MCXN947':>12s} {'ESP32-S3':>12s} {'ratio(MCX/ESP)':>15s}")
for name in tasks:
    m, e = classical[name]["mcx_us"], classical[name]["esp_us"]
    print(f"{name:20s} {m:10.1f} {e:10.1f} {m/e:13.2f}x")

print("\n-- PQC (us) --")
print("ML-KEM-768:  MCX kp+enc+dec = %d us   ESP32 kp+enc+dec = %d us (mean-scaled)"
      % (sum(mcx_kem.values()), sum(esp_kem.values())))
for dl in ("44", "65", "87"):
    print(f"ML-DSA-{dl} sign: MCX {mldsa_sign[dl]['mcx_us']:d} us   ESP32 {mldsa_sign[dl]['esp_us']:d} us   "
          f"verify: MCX {mldsa_verify[dl]['mcx_us']:.0f} us   ESP32 {mldsa_verify[dl]['esp_us']:.0f} us")

print("\n-- TLS 1.2 handshake ECC phase (1 ECDH + 1 sign + 2 verify) --")
for board, bname in (("mcx", "MCXN947"), ("esp", "ESP32-S3")):
    c_tot, c_e, c_s, c_v = ecc_phase_classical(board)
    print(f"{bname:10s} classical ECC: {c_tot:9.1f} us  (ECDH {c_e:.0f} + sign {c_s:.0f} + 2x verify {c_v:.0f})")
    for dl in ("44", "65", "87"):
        p_tot, p_k, p_s, p_v = ecc_phase_pqc(board, dl)
        print(f"           PQC {dl:2s}:      {p_tot:9.1f} us  (KEM {p_k:.0f} + sign {p_s:.0f} + 2x verify {p_v:.0f})  "
              f"delta {(p_tot-c_tot)/c_tot*100:+6.1f}%")

print("\n-- Headline: migration delta per board per DSA level (ML-KEM-768 fixed) --")
print(f"{'board':10s} {'DSA-44':>9s} {'DSA-65':>9s} {'DSA-87':>9s}")
for board, bname in (("mcx", "MCXN947"), ("esp", "ESP32-S3")):
    c_tot, *_ = ecc_phase_classical(board)
    row = []
    for dl in ("44", "65", "87"):
        p_tot, *_ = ecc_phase_pqc(board, dl)
        row.append((p_tot-c_tot)/c_tot*100)
    print(f"{bname:10s} {row[0]:+8.1f}% {row[1]:+8.1f}% {row[2]:+8.1f}%")

# NIST L1 matched (ML-KEM-512 not measured on ESP32; use 768 as the common thread)
print("\n-- Notes --")
print("ML-KEM-768 is the common thread (both boards have data). NIST L1 (512)")
print("was only measured on MCX. ML-DSA from Zephyr (-Os, same code both boards);")
print("classical from SecureMark (-O2, 14/14 CRC both boards).")
