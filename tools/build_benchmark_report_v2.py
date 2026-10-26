from docx import Document
from docx.shared import Pt, Inches

DOC = Document()
st = DOC.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(8)


def h(t, lvl=1):
    DOC.add_heading(t, level=lvl)


def p(t):
    DOC.add_paragraph(t)


def code(lines):
    for ln in lines:
        par = DOC.add_paragraph()
        par.paragraph_format.space_after = Pt(0)
        par.paragraph_format.left_indent = Inches(0.3)
        r = par.add_run(ln)
        r.font.name = "Consolas"
        r.font.size = Pt(9.5)


def table(headers, rows):
    t = DOC.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, hd in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = hd
        for run in c.paragraphs[0].runs:
            run.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = str(v)
            for run in cells[i].paragraphs[0].runs:
                run.font.size = Pt(9)
    DOC.add_paragraph()


DOC.add_heading("EEMBC-Style Comparison of Classical and Post-Quantum Cryptography on Two "
                "IoT Edge MCUs", level=0)
p("Zain Ul Haq. M.Sc. Autonomous Systems, Hochschule Bonn-Rhein-Sieg. Supervisors: "
  "Prof. Dr. Houben and Prof. Dr. Tschofenig.")

h("1. Objective")
p("This report measures what a TLS 1.2 public-key handshake costs on two microcontrollers, first "
  "with classical ECDH and ECDSA over P-256 and then with the NIST post-quantum replacements "
  "ML-KEM and ML-DSA. The measurements follow EEMBC methodology. SecureMark-TLS supplies the "
  "classical reference and the same 14-component structure is used for the post-quantum "
  "substitution, so the two can be put side by side.")
p("The migration cost depends on the board and on the security level. At NIST Level 1 on the NXP "
  "MCXN947 the post-quantum handshake is 9.1% faster than the classical one, because the two "
  "signature verifications in the handshake become much cheaper. At Level 3 and Level 5 it is "
  "slower, by 50.9% and 125.9%. On the ESP32-S3 every level comes out faster, between 62% and "
  "82%, which says more about the cost of its software ECC than about the cost of lattice "
  "arithmetic.")
p("The code for every section is in the accompanying repository, and each section below ends with "
  "the folder, the build settings and the command needed to reproduce its numbers. Everything "
  "except the on-board runs executes on a PC from the stored data.")

h("2. Method")
h("2.1 Platforms", 2)
table(["Property", "NXP FRDM-MCXN947", "ESP32-S3"],
      [["Core", "Cortex-M33, 150 MHz", "Xtensa LX7, 240 MHz"],
       ["Flash / SRAM", "2 MB / 512 KB", "8 MB / 512 KB"],
       ["PQC implementation", "PQClean", "PQClean"],
       ["Classical stack", "mbedTLS 3.6.3", "ESP-IDF mbedTLS"]])
h("2.2 Measurement harness", 2)
p("Latency comes from hardware cycle counters: DWT->CYCCNT on the MCXN947 and the CCOUNT "
  "register on the ESP32-S3, converted to microseconds using each board's clock. Every timing run "
  "is taken with the debugger and the serial line detached; either one attached introduces "
  "noticeable jitter in the readings.")
p("Peak stack use is measured by painting the task stack with the byte 0xEE at boot and scanning "
  "for the deepest byte that a run left untouched, so the memory figures are measured peak rather "
  "than estimated.")
p("Energy is captured with a Nordic PPK2 sampling at 10 kHz at 3.3 V, in series with the board "
  "supply. On the MCXN947 this is the J24 rail; on the ESP32-S3 it is the 3V3 pin. Captures are "
  "taken free-running so the measurement covers the computation and nothing else.")
p("Sample counts are 100 repetitions for each KEM operation and 2000 for each signing test, with "
  "fresh randomness on every signing call. The signing runs are what expose the latency tail "
  "discussed in section 4.3.")
p("The harness code is the same across the firmware projects: a cycle counter shim (dwt.h on the "
  "NXP side, esp_timer on the ESP32), the 0xEE stack painter, and the PPK2 analyser "
  "(codebase/projects/mlkem_bench/results/eembc_style/analyze_energy.py).")
p("One setting is not matched and it should be kept in mind for section 4. The bare-metal ML-KEM "
  "library is compiled at -O0, while ML-DSA and the classical SecureMark primitives are compiled "
  "at -O2. The post-quantum column therefore carries more cost than it would at matched "
  "optimisation, which makes the reported overhead an upper bound. Section 4.1 gives the exact "
  "flags.")

h("3. The PQC-extended SecureMark-TLS profile")
p("The classical profile is the official EEMBC self-hosted SecureMark-TLS suite, 14 components "
  "that model a TLS 1.2 handshake with mbedTLS. The post-quantum variant keeps the same protocol "
  "structure and replaces the public-key primitives.")
h("3.1 Primitive mapping", 2)
table(["Classical phase (P-256)", "Post-quantum equivalent"],
      [["ECDH key exchange", "ML-KEM keypair, encapsulation and decapsulation"],
       ["ECDSA signatures", "ML-DSA signing"],
       ["ECDSA verification", "ML-DSA verification"]])
p("Classical 128-bit security (P-256) is compared against NIST Level 1 (ML-KEM-512 with "
  "ML-DSA-44), Level 3 (ML-KEM-768 with ML-DSA-65) and Level 5 (ML-KEM-1024 with ML-DSA-87).")
h("3.2 Scoring", 2)
p("The EEMBC SecureMark score is 1000 divided by the weighted sum of the component processing "
  "times, so a larger score means less time per primitive. Every component is also checked against "
  "a reference CRC, and a score is only comparable to published figures if all checks pass.")
p("Both boards pass 14 of 14 CRC checks. The MCXN947 scores 5472.08 marks and the ESP32-S3 scores "
  "1895.06 marks. These are the classical baselines used in section 4.")
p("Code and settings. The MCXN947 port is codebase/projects/securemark_tls_mcxn947, built through "
  "the MCUXpresso SDK CMake flow with the Arm GNU toolchain. Its mbedTLS sources are compiled at "
  "-O2 through a per-file compile option, which that library needs for its inline MULADDC assembly "
  "on this core; the rest of the project builds at -O0. The ESP32-S3 port is "
  "codebase/projects/securemark_tls_esp32s3, built with ESP-IDF v5.4 and "
  "CONFIG_COMPILER_OPTIMIZATION_PERF=y. Both ports carry the three fixes described in the "
  "repository notes: an RNG for ECP point blinding, the SEC1 0x04 prefix on the peer key, and DER "
  "encoding of the signature. To reproduce:")
code([
    "bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh build",
    "bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh -p COM17 flash",
])
p("Expect 14 lines where crc equals expected_crc, then the score line. The MCXN947 project flashes "
  "with LinkServer and its score is stored in results/securemark_score.txt.")

h("4. Classical and post-quantum handshake comparison")
p("The comparison uses an equivalent public-key phase on each side: one key exchange, one "
  "signature and two verifications. On the classical side that is ECDH, one ECDSA sign and two "
  "ECDSA verifies. The post-quantum side uses ML-KEM and ML-DSA in the same shape, so the two "
  "differ only in the primitives.")
h("4.1 NXP FRDM-MCXN947 (150 MHz)", 2)
table(["Suite", "Latency (ms)", "Delta"],
      [["Classical, ECDH + ECDSA P-256", "166.1", "reference"],
       ["PQC Level 1, ML-KEM-512 + ML-DSA-44", "151.0", "-9.1%"],
       ["PQC Level 3, ML-KEM-768 + ML-DSA-65", "250.7", "+50.9%"],
       ["PQC Level 5, ML-KEM-1024 + ML-DSA-87", "375.2", "+125.9%"]])
p("The Level 1 result is the one that needs explaining. ML-DSA verification costs about a third "
  "of ECDSA verification, and the handshake performs two verifications, which more than covers "
  "the heavier ML-KEM key exchange and leaves the handshake 9.1% faster. Levels 3 and 5 grow the "
  "key exchange faster than the verification saving can offset.")
h("4.2 ESP32-S3 (240 MHz)", 2)
table(["Suite", "Latency (ms)", "Delta"],
      [["Classical, ECDH + ECDSA P-256", "495.2", "reference"],
       ["PQC Level 1, ML-KEM-512 + ML-DSA-44", "88.8", "-82.1%"],
       ["PQC Level 3, ML-KEM-768 + ML-DSA-65", "134.2", "-72.9%"],
       ["PQC Level 5, ML-KEM-1024 + ML-DSA-87", "187.1", "-62.2%"]])
p("The ESP32-S3 is faster at every level after migration. The absolute saving is large, but it "
  "comes mostly from the classical side being expensive on this core, where ECC runs in software. "
  "It does not mean lattice arithmetic is cheap; the post-quantum absolute times are still the "
  "tens of milliseconds shown above.")
h("4.3 The signing tail", 2)
p("Handshake budgets tend to be built from average times, and for ML-DSA that is unsafe. The "
  "signing median and worst case, over 2000 draws per level at 150 MHz, are:")
table(["Level", "Median (ms)", "Worst case (ms)", "Worst / median"],
      [["ML-DSA-44", "43.7", "262.9", "6.0x"],
       ["ML-DSA-65", "75.7", "611.1", "8.1x"],
       ["ML-DSA-87", "99.6", "475.7", "4.8x"]])
p("The worst case reaches six to eight times the median. The cause is rejection sampling inside "
  "the signing routine, which draws and discards candidates until one satisfies the norm bounds, "
  "so the tail is a property of the algorithm. Section 7 confirms the same ratios appear on both "
  "cores. A scheduler that budgets the median will meet its deadline in testing and miss it in the "
  "field.")
p("Code and settings. The two analysis scripts are "
  "codebase/projects/securemark_tls_mcxn947/migration_compare.py and "
  "codebase/projects/securemark_tls_esp32s3/cross_platform_compare.py. Both run on a PC from the "
  "stored per-operation times and need no board. Their inputs are the SecureMark times above "
  "(mbedTLS at -O2) plus the bare-metal PQC numbers, where ML-KEM comes from "
  "codebase/projects/mlkem_bench built at -O0 and ML-DSA from codebase/projects/mldsa_bench_nxp "
  "built at -O2.")
code([
    "python codebase/projects/securemark_tls_mcxn947/migration_compare.py",
    "python codebase/projects/securemark_tls_esp32s3/cross_platform_compare.py",
])
p("Expect -9.1% and +50.9% on the MCXN947, and -82.1, -72.9 and -62.2 on the ESP32-S3. To "
  "re-measure the signing tail rather than reuse the stored CSV, build the bench at the level you "
  "want and read the percentiles from results/mldsa*_sign_raw.csv:")
code(["cmake -DMLDSA_LEVEL=65 -DCMAKE_C_FLAGS=-O2 ...   # then flash and capture the serial output"])

h("5. Energy")
h("5.1 Session resumption with DTLS Connection IDs", 2)
p("Running the full handshake on every wake-up is the dominant energy cost at high duty cycles. "
  "This section models a 24-hour deployment on a CR2032 cell (225 mAh) and compares a full "
  "handshake each wake-up against resuming with a DTLS Connection ID, which replaces the "
  "public-key phase with symmetric session resumption. The per-handshake energy fed into the model "
  "is measured; the model itself is arithmetic on that number and not a separate capture.")
table(["Board", "Wake-ups / day", "Full handshake (mJ)", "With CID (mJ)", "Saving"],
      [["MCXN947", "24", "1340.9", "1297.9", "3.2%"],
       ["MCXN947", "288", "1834.9", "1298.2", "29.2%"],
       ["MCXN947", "2880", "6685.2", "1301.5", "80.5%"],
       ["ESP32-S3", "24", "1735.1", "1315.6", "24.2%"],
       ["ESP32-S3", "288", "6565.6", "1330.7", "79.7%"],
       ["ESP32-S3", "2880", "53991.6", "1478.7", "97.3%"]])
p("At the lowest rate the saving is small, 3.2% on the MCXN947. As the wake-up rate rises the "
  "full handshake becomes the entire budget and the CID saving grows to 97.3% on the ESP32-S3, "
  "which extends the cell from about 88 days to about 1740.")
h("5.2 Energy per handshake (ULPMark style)", 2)
p("For the ML-KEM-768 handshake the measured energy is 6.63 mJ with the PQClean reference code, "
  "which is 151 handshakes per joule. An M4F-optimised build of the same handshake measures "
  "3.00 mJ, or 333 handshakes per joule. The optimised figure is a partial score: the optimised "
  "decapsulation path faults on this core, so only the keypair and encapsulation phases were "
  "measured (section 7 discusses the faults).")
p("Code and settings. The battery model is "
  "codebase/projects/securemark_tls_mcxn947/dtls_cid_model.py and runs on a PC from the measured "
  "per-handshake energy. The energy itself comes from PPK2 captures analysed by "
  "codebase/projects/mlkem_bench/results/eembc_style/analyze_energy.py, and the M4F comparison "
  "from codebase/projects/pqm4_bench_mcxn947 (Arm GNU, -O0, with the linker stack region raised to "
  "0x20000). To reproduce the model:")
code(["python codebase/projects/securemark_tls_mcxn947/dtls_cid_model.py"])
p("The script writes results/dtls_cid/daily_energy.csv with every wake-up rate for both boards.")

h("6. Joint scheduling of perception and cryptography")
p("A single core has to run the perception loop and the handshake together. The loop used here has "
  "a 33.3 ms frame budget. The handshake is sliced into non-blocking pieces that execute in the "
  "slack between frames. The scheduler decides two things per frame: which ML-KEM security level "
  "to run and how deep to run the multi-exit perception network.")
table(["Policy", "Total time (s)", "Energy (mJ)", "Deadline misses"],
      [["Naive, always full depth", "78.4", "3382", "70"],
       ["Static early exit", "69.6", "3206", "70"],
       ["Adaptive early exit", "67.9", "3173", "70"],
       ["Learned joint", "45.9", "2079", "0"]])
p("The learned scheduler cuts the time and energy by roughly 40% and removes the missed "
  "deadlines, which the fixed policies all leave at 70.")
p("The two decisions are not the same kind of problem. Security level is a choice among three "
  "discrete points with known costs, and a simple budget-matching rule picks as well as anything "
  "learned, so it is kept as a rule. The exit decision sits on a continuous confidence axis, and "
  "here the learned isotonic risk curves fit operating points to the measured data that a fixed "
  "threshold cannot locate.")
p("Code and settings. The scheduler is "
  "codebase/training_archive/training/conformal/joint_scheduler.py. It runs on a PC and takes the "
  "measured per-exit and per-security-level costs as fixed inputs, so the table reproduces without "
  "a board:")
code(["python codebase/training_archive/training/conformal/joint_scheduler.py"])
p("Read the learned line on the test split: 45920.7 ms, 2078.9 mJ and 0 misses.")

h("7. Verification and compliance")
p("Fixed workload. Policy runs use a 1230-frame sequence with one handshake step every ten frames, "
  "which is 123 steps or 41 full handshakes. The frame sequence is drawn from the frozen test "
  "split by codebase/training_archive/training/build_freerun_workload.py.")
p("Sampling. Signing is measured over 2000 iterations per level with a distinct message and fresh "
  "randomness on each call, and key exchange over at least 100 iterations per operation.")
p("Energy calibration. All energy figures come from PPK2 captures taken free-running at 10 kHz, so "
  "the debugger and serial activity do not contribute.")
p("Cross-core consistency. The same Zephyr build of ML-DSA was run on both boards. The "
  "worst-to-median ratios, 7.1x, 6.0x and 5.9x for levels 44, 65 and 87, are identical on the "
  "Cortex-M33 and the Xtensa. That rules out the silicon as the source of the tail.")
p("Numeric agreement between the board and the PC reference. The board's INT8 tensors are not "
  "bit-exact against the TFLite reference and differ by 1 to 4 LSB, growing slightly with depth:")
table(["Tensor", "Max difference (LSB)"],
      [["exit1 logits", "1"],
       ["block3 features", "2"],
       ["exit2 logits", "3"],
       ["block6 features", "4"],
       ["exit3 logits", "3"]])
p("The drift was traced to fixed-point accumulation inside the Neutron NPU. Driver and converter "
  "version skew was ruled out experimentally: after matching the driver to the converter version "
  "the boot warning disappeared and the drift stayed byte-for-byte identical. A full audit of "
  "whether this drift ever changes the decided class across the whole validation set has not been "
  "done; the golden comparison covers a small set of inputs, so a decision-flip audit across the "
  "1230 frames is listed as open work rather than claimed.")
p("Implementation limit. The optimised M4F code path faults on this Cortex-M33 part, which is why "
  "the optimised energy figures in section 5.2 cover only the phases that complete. The fault "
  "registers and the disassembly that locate it are recorded in "
  "codebase/projects/pqm4_bench_mcxn947/results/PQM4_M4F_M33_POSTMORTEM.md.")
p("Code and settings. The cross-core ratios come from codebase/projects/pqc_bench_zephyr, one "
  "Zephyr build at -Os run on both boards, with CONFIG_THREAD_STACK_INFO enabled so the "
  "per-operation stack peaks can be read. The numeric-agreement figures come from "
  "codebase/projects/gtsrb_multiexit/tools/golden, which compares the board's INT8 tensors against "
  "the TFLite reference for the same inputs:")
code([
    "west build -b frdm_mcxn947/mcxn947/cpu0      # and esp32s3_devkitc/esp32s3/procpu",
    "python codebase/projects/gtsrb_multiexit/tools/golden/compare_golden.py",
])

h("8. References")
p("EEMBC SecureMark-TLS, the classical TLS 1.2 benchmark used for the baseline.")
p("EEMBC ULPMark, the energy-per-operation metric used to express section 5.2.")
p("PQClean, the reference post-quantum implementations benchmarked here.")
p("NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA), the standards for the post-quantum primitives.")
p("IETF RFC 9146, DTLS Connection ID, the mechanism modelled in section 5.1.")

out = r"H:\z_thesis\fixes\PQC_benchmark_report.docx"
DOC.save(out)
print("wrote", out, "| paragraphs:", len(DOC.paragraphs), "tables:", len(DOC.tables))
