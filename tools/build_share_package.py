#!/usr/bin/env python3
"""Build the clean, shareable THESIS_SHARE/ package.

Organizes reports + results + raw captures by experiment -> board -> results,
renames PPK2 and serial captures descriptively, and writes a manifest.
The working codebase is NOT modified (builds stay intact); this package is
the share-with-professor artifact. Firmware projects are indexed via the
code/ README (they are SDK-tangled and not portable as copies).
"""
import os, shutil, json, sys

SRC = r"H:\z_thesis"
P = os.path.join(SRC, "THESIS_SHARE")

def cp(src, dst):
    s = os.path.join(SRC, src)
    d = os.path.join(P, dst)
    if not os.path.exists(s):
        print(f"  !! missing source: {src}")
        return None
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(s, d)
    return (src, dst, os.path.getsize(d))

manifest = []
def add(src, dst):
    r = cp(src, dst)
    if r: manifest.append(r)

# ---------------------------------------------------------------- 00 overview
OV = "00_thesis_overview"
for f in ["MILESTONE_REPORT.md", "THREE_EXPERIMENTS_THESIS_REPORT.md",
          "MEETING_HANDOUT_CORRECTIONS.md", "EEMBC_ALIGNED_PLAN.md",
          "THESIS_PROPOSAL_DRAFT.md", "UNIFIED_EXPERIMENTS_REPORT.md",
          "RELATED_WORK_CANDIDATES.md"]:
    add(f, f"{OV}/{f}")

# ------------------------------------------------- 01 anytime perception (core)
A1 = "01_anytime_perception"
add("codebase/projects/gtsrb_multiexit/tools/golden/DEPLOYMENT_REPORT.md",
    f"{A1}/report/DEPLOYMENT_REPORT_npu_mcxn947.md")
add("codebase/projects/gtsrb_policy_singlecore/POLICY_EXPERIMENT_REPORT.md",
    f"{A1}/report/POLICY_EXPERIMENT_REPORT_interleaved.md")
add("codebase/projects/gtsrb_policy_singlecore/results/interleaved/interleaved_summary.csv",
    f"{A1}/results/interleaved_summary.csv")
for pol in ["naive", "static", "adaptive"]:
    add(f"codebase/projects/gtsrb_policy_singlecore/results/interleaved/policy_results_{pol}.csv",
        f"{A1}/results/policy_results_{pol}.csv")
add("codebase/projects/gtsrb_policy_freerun/results/interleaved_embedded/FREERUN_ENERGY_REPORT.md",
    f"{A1}/report/FREERUN_ENERGY_REPORT.md")
add("codebase/projects/gtsrb_policy_freerun/results/interleaved_embedded/energy_summary_freerun.csv",
    f"{A1}/results/energy_summary_freerun.csv")
add("codebase/projects/gtsrb_policy_freerun/results/interleaved_embedded/policy_results_naive.csv",
    f"{A1}/results/freerun_policy_results_naive.csv")
add("codebase/projects/gtsrb_policy_freerun/results/interleaved_embedded/policy_results_adaptive.csv",
    f"{A1}/results/freerun_policy_results_adaptive.csv")
add("codebase/projects/gtsrb_policy_freerun/results/interleaved_embedded/policy_results_static.csv",
    f"{A1}/results/freerun_policy_results_static.csv")
add("codebase/projects/gtsrb_policy_singlecore_kem1024/KEM1024_REPORT.md",
    f"{A1}/report/KEM1024_REPORT.md")

# ------------------------------------------------------- 02 PQC benchmarks
A2 = "02_pqc_benchmarks"
# MCXN947
add("codebase/projects/mlkem_bench/results/eembc_style/PQC_BENCHMARK_REPORT.md",
    f"{A2}/mcxn947/MLKEM_BENCHMARK_REPORT.md")
add("codebase/projects/mlkem_bench/results/eembc_style/perf_memory_summary.csv",
    f"{A2}/mcxn947/mlkem_perf_memory_summary.csv")
add("codebase/projects/mlkem_bench/results/eembc_style/energy_summary.csv",
    f"{A2}/mcxn947/mlkem_energy_summary.csv")
add("codebase/projects/mldsa_bench_nxp/results/MLDSA_SIGNING_LATENCY_REPORT.md",
    f"{A2}/mcxn947/MLDSA_SIGNING_LATENCY_REPORT.md")
add("codebase/projects/mldsa_bench_nxp/results/conformal_latency/CONFORMAL_LATENCY_REPORT.md",
    f"{A2}/mcxn947/CONFORMAL_LATENCY_REPORT.md")
add("codebase/projects/pqm4_bench_mcxn947/results/PQM4_M4F_M33_POSTMORTEM.md",
    f"{A2}/mcxn947/PQM4_M4F_M33_POSTMORTEM.md")
add("codebase/projects/pqm4_bench_mcxn947/results/mldsa44_fault.txt",
    f"{A2}/mcxn947/serial_pqm4_mldsa44_fault_registers.txt")
add("codebase/projects/pqm4_bench_mcxn947/results/mldsa44_128k_fault.txt",
    f"{A2}/mcxn947/serial_pqm4_mldsa44_128k_hang.txt")
add("codebase/projects/pqm4_bench_mcxn947/PQM4_VS_PQCLEAN_REPORT.md",
    f"{A2}/mcxn947/PQM4_VS_PQCLEAN_REPORT.md")
# ESP32-S3
add("codebase/projects/gtsrb_multiexit_esp32s3/results/MLDSA_SIGNING_LATENCY_REPORT.md",
    f"{A2}/esp32s3/MLDSA_SIGNING_LATENCY_REPORT.md")
for lv in ["44", "65", "87"]:
    add(f"codebase/projects/gtsrb_multiexit_esp32s3/results/mldsa{lv}_sign_raw.csv",
        f"{A2}/esp32s3/mldsa{lv}_sign_raw.csv")
# Zephyr (both boards)
add("codebase/projects/pqc_bench_zephyr/results/PQC_ZEPHYR_BENCHMARK_REPORT.md",
    f"{A2}/zephyr/PQC_ZEPHYR_BENCHMARK_REPORT.md")
for b in ["mcxn947", "esp32s3"]:
    for lv in ["44", "65", "87"]:
        add(f"codebase/projects/pqc_bench_zephyr/results/{b}_mldsa{lv}_sign.csv",
            f"{A2}/zephyr/{b}_mldsa{lv}_sign.csv")
    add(f"codebase/projects/pqc_bench_zephyr/results/{b}_mlkem768.csv",
        f"{A2}/zephyr/{b}_mlkem768.csv")
# STM32 status
add("codebase/projects/pqc_bench_zephyr/results/STM32N6570DK_STATUS.md",
    f"{A2}/stm32n6570/STM32N6570DK_STATUS.md")

# --------------------------------------------------- 03 classical baseline
A3 = "03_classical_baseline"
add("codebase/projects/securemark_tls_mcxn947/results/SECUREMARK_TLS_REPORT.md",
    f"{A3}/mcxn947/SECUREMARK_TLS_REPORT.md")
add("codebase/projects/securemark_tls_mcxn947/results/securemark_score.txt",
    f"{A3}/mcxn947/securemark_score.txt")
add("codebase/projects/securemark_tls_esp32s3/results/SECUREMARK_ESP32S3_REPORT.md",
    f"{A3}/esp32s3/SECUREMARK_ESP32S3_REPORT.md")
add("codebase/projects/securemark_tls_esp32s3/results/securemark_esp32s3_score.txt",
    f"{A3}/esp32s3/securemark_esp32s3_score.txt")
add("codebase/projects/securemark_tls_mcxn947/results/MIGRATION_COMPARISON.md",
    f"{A3}/migration/MIGRATION_COMPARISON.md")
add("codebase/projects/securemark_tls_esp32s3/results/CROSS_PLATFORM_MIGRATION.md",
    f"{A3}/migration/CROSS_PLATFORM_MIGRATION.md")
add("codebase/projects/securemark_tls_mcxn947/results/SECUREMARK_ENERGY_REPORT.md",
    f"{A3}/migration/SECUREMARK_ENERGY_REPORT_mcxn947.md")
add("codebase/projects/securemark_tls_esp32s3/results/SECUREMARK_ENERGY_CROSS_PLATFORM.md",
    f"{A3}/migration/SECUREMARK_ENERGY_CROSS_PLATFORM.md")
add("codebase/projects/securemark_tls_mcxn947/results/dtls_cid/daily_energy.csv",
    f"{A3}/migration/dtls_cid_daily_energy.csv")

# --------------------------------------------- 04 security side channels
A4 = "04_security_side_channels"
add("codebase/projects/mlkem_bench/results/activity/ACTIVITY_LEAKAGE_REPORT.md",
    f"{A4}/activity_leakage/ACTIVITY_LEAKAGE_REPORT.md")
add("codebase/projects/gtsrb_policy_freerun/results/EXIT_LEAKAGE_REPORT.md",
    f"{A4}/exit_leakage/EXIT_LEAKAGE_REPORT.md")
add("codebase/training_archive/training/results/leakage_aware/LEAKAGE_AWARE_REPORT.md",
    f"{A4}/obfuscation/LEAKAGE_AWARE_REPORT.md")
add("codebase/training_archive/training/results/leakage_aware/SELECTIVE_OBFUSCATION_REPORT.md",
    f"{A4}/obfuscation/SELECTIVE_OBFUSCATION_REPORT.md")
add("codebase/training_archive/training/results/leakage_aware/leakage_aware_summary.json",
    f"{A4}/obfuscation/leakage_aware_summary.json")
add("codebase/training_archive/training/results/leakage_aware/selective_obfuscation_summary.json",
    f"{A4}/obfuscation/selective_obfuscation_summary.json")
add("codebase/projects/gtsrb_policy_freerun/results/B_SPLIT_INFERENCE_REPORT.md",
    f"{A4}/split_inference/B_SPLIT_INFERENCE_REPORT.md")
add("codebase/projects/securemark_tls_mcxn947/results/DTLS_CID_REPORT.md",
    f"{A4}/dtls_cid/DTLS_CID_REPORT.md")
add("codebase/projects/securemark_tls_mcxn947/results/dtls_cid/cumulative_hourly.png",
    f"{A4}/dtls_cid/cumulative_hourly.png")

# ------------------------------------------------------ 05 learned AI angles
A5 = "05_learned_ai_angles"
add("codebase/training_archive/training/results/learned_policy/learned_policy_report.md",
    f"{A5}/learned_exit/LEARNED_POLICY_REPORT.md")
add("codebase/training_archive/training/results/learned_policy/DOUBLE_TOUCH_FIX_REPORT.md",
    f"{A5}/learned_exit/DOUBLE_TOUCH_FIX_REPORT.md")
add("codebase/training_archive/training/results/learned_policy/risk_curves.json",
    f"{A5}/learned_exit/risk_curves.json")
add("codebase/training_archive/training/results/learned_policy/joint_scheduler_summary.csv",
    f"{A5}/joint_scheduler/joint_scheduler_summary.csv")
add("codebase/training_archive/training/results/learned_policy/JOINT_SCHEDULER_REPORT.md",
    f"{A5}/joint_scheduler/JOINT_SCHEDULER_REPORT.md")
# TTCA
add("codebase/training_archive/training/results/ttca/TTCA_STAGE1_REPORT.md",
    f"{A5}/ttca/TTCA_STAGE1_REPORT.md")
add("codebase/training_archive/training/results/ttca/STAGE3_PARETO_AUDIT.md",
    f"{A5}/ttca/STAGE3_PARETO_AUDIT.md")
add("codebase/training_archive/training/results/ttca/ttca_stage1_plots.png",
    f"{A5}/ttca/ttca_stage1_plots.png")
add("codebase/training_archive/training/results/ttca/stage3_pareto_audit.png",
    f"{A5}/ttca/stage3_pareto_audit.png")
add("codebase/training_archive/training/results/ttca/ttca_stage1_summary.csv",
    f"{A5}/ttca/ttca_stage1_summary.csv")
for f in ["aci_softmax.npy", "calib_softmax.npy", "calib_labels.npy"]:
    add(f"codebase/training_archive/training/results/ttca/{f}",
        f"{A5}/ttca/{f}")

# ------------------------------------------------------------- 06 simulations
A6 = "06_simulations"
for sub in ["security_selection_sim", "swarm_coordination_sim"]:
    p = os.path.join(SRC, sub, "results")
    if os.path.isdir(p):
        for f in sorted(os.listdir(p)):
            if f.endswith(".md"):
                add(f"{sub}/results/{f}", f"{A6}/{sub.replace('_sim','')}/{f}")

# ------------------------------------------------- data: energy PPK2 (renamed)
D = "data/energy_ppk2"
add("energy resulkts/ppk_secureMark-TLS.csv", f"{D}/energy_securemark_tls_mcxn947.csv")
add("energy resulkts/ppk-esp32_power captured.csv", f"{D}/energy_securemark_tls_esp32s3.csv")
add("energy resulkts/ppk_m4f_kpenc_768.csv", f"{D}/energy_pqm4_mlkem768_kpenc_mcxn947.csv")
add("energy resulkts/ppk_m4f_kpenc_512.csv", f"{D}/energy_pqm4_mlkem512_kpenc_mcxn947.csv")
add("energy resulkts/ppk_v33.csv", f"{D}/energy_voltage_3p3V_mcxn947.csv")
add("energy resulkts/ppk_v27.csv", f"{D}/energy_voltage_2p7V_mcxn947.csv")
add("energy resulkts/ppk_v24.csv", f"{D}/energy_voltage_2p4V_mcxn947.csv")
add("energy resulkts/ppk_v22.csv", f"{D}/energy_voltage_2p2V_mcxn947.csv")
add("energy resulkts/ppk-20260808T132908_deepcode_learned.csv",
    f"{D}/energy_interleaved_learned_mcxn947.csv")
add("energy resulkts/ppk-20260809T090023_raw_with_p0_31.csv",
    f"{D}/energy_mlkem1024_activity_trigger_mcxn947.csv")
add("energy resulkts/ppk-20260809T195247_No.3.csv",
    f"{D}/energy_exit_leakage_bursts_mcxn947.csv")
for pol in ["naive", "static", "adaptive", "learned"]:
    add(f"codebase/projects/gtsrb_policy_freerun/results/interleaved_embedded/ppk_{pol}_free.csv",
        f"{D}/energy_interleaved_{pol}_140f_mcxn947.csv")

# ------------------------------------------- data: serial captures (renamed)
S = "data/serial_captures"
add("codebase/projects/securemark_tls_mcxn947/results/securemark_selfhosted_raw.txt",
    f"{S}/serial_securemark_tls_mcxn947.txt")
add("codebase/projects/securemark_tls_esp32s3/results/securemark_esp32s3_raw.txt",
    f"{S}/serial_securemark_tls_esp32s3_Os.txt")
add("codebase/projects/securemark_tls_esp32s3/results/securemark_esp32s3_o2_raw.txt",
    f"{S}/serial_securemark_tls_esp32s3_O2.txt")
add("codebase/projects/pqc_bench_zephyr/results/esp32s3_kem.txt",
    f"{S}/serial_zephyr_mlkem768_esp32s3.txt")
add("codebase/projects/pqc_bench_zephyr/results/mcxn947_raw.txt",
    f"{S}/serial_zephyr_pqc_mcxn947.txt")
add("codebase/projects/pqc_bench_zephyr/results/esp32s3_full.txt",
    f"{S}/serial_zephyr_pqc_esp32s3.txt")
for lv in ["512", "768", "1024"]:
    add(f"codebase/projects/mlkem_bench/results/eembc_style/mlkem{lv}_raw.txt",
        f"{S}/serial_mlkem{lv}_mcxn947.txt")
for lv in ["44", "65", "87"]:
    add(f"codebase/projects/mldsa_bench_nxp/results/mldsa{lv}_raw.txt",
        f"{S}/serial_mldsa{lv}_mcxn947.txt")
    add(f"codebase/projects/gtsrb_multiexit_esp32s3/results/mldsa{lv}_raw.txt",
        f"{S}/serial_mldsa{lv}_esp32s3.txt")
add("codebase/projects/gtsrb_policy_freerun/results/split_inference_raw.txt",
    f"{S}/serial_split_inference_mcxn947.txt")

# ------------------------------------------------------------ manifest
with open(os.path.join(P, "MANIFEST.json"), "w") as f:
    json.dump(manifest, f, indent=1)
print(f"\n{len(manifest)} files packaged -> {P}")
total = sum(m[2] for m in manifest)
print(f"total size: {total/1e6:.1f} MB")
missing = [m for m in manifest if m is None]
