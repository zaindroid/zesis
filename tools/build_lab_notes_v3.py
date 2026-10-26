from docx import Document
from docx.shared import Pt, Inches

DOC = Document()
st = DOC.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(6)


def h(t, lvl=1):
    DOC.add_heading(t, level=lvl)


def p(t):
    DOC.add_paragraph(t)


def bullet(t):
    DOC.add_paragraph(t, style="List Bullet")


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


DOC.add_heading("PQC on the two boards, lab notes", level=0)
p("Zain. M.Sc. Autonomous Systems. Prof. Houben, Prof. Tschofenig.")
p("MCXN947 (Cortex-M33, 150 MHz) and ESP32-S3 (Xtensa LX7, 240 MHz). Measured on the hardware, "
  "every number traceable to a file in the repo.")

h("What I set out to measure")
p("What does the handshake cost once it moves off ECDH/ECDSA and onto ML-KEM/ML-DSA, on an MCU, "
  "and can we live with it. Most published PQC costs come from servers or desktop builds, so I "
  "measured here instead. The later sections are about paying that cost less often, hiding it, and "
  "fitting it beside a real-time loop on one core.")

h("Setup")
p("Time comes from hardware counters, DWT->CYCCNT on the MCX and CCOUNT on the ESP32, then "
  "cycles divided by the clock. I capture with the debugger and the serial line detached; with "
  "either attached the numbers drift.")
p("Stack: paint the task stack with 0xEE at boot, scan for the deepest surviving byte after the "
  "run.")
p("Energy: PPK2, 10 kHz, 3.3 V, in series with the supply. J24 rail on the MCX, the 3V3 pin on "
  "the ESP32.")
p("100 reps per KEM operation, 2000 per signing test, fresh randomness each sign.")
p("Flags are not matched across the board. Bare-metal ML-KEM is -O0, ML-DSA is -O2, SecureMark is "
  "-O2. That puts the KEM numbers on the pessimistic side and I haven't gone back to fix it yet.")

h("1. SecureMark-TLS, the classical reference")
p("Official EEMBC self-hosted suite, 14 components in TLS 1.2 shape: AES-128 ECB and CCM, "
  "SHA-256, ECDH P-256, ECDSA P-256. mbedTLS 3.6.3 on the MCX, the ESP-IDF mbedTLS on the ESP32, "
  "-O2 on both.")
p("MCX scored 5472.08 marks, ESP32 1895.06, and both pass 14 of 14 CRCs. The CRC passes are what "
  "make the score usable next to the published EEMBC numbers.")
p("Getting it to run took three fixes. mbedTLS wants an RNG for point blinding on the ECDH call; "
  "pass a null and it aborts with MBEDTLS_ERR_ECP_BAD_INPUT_DATA. EEMBC hands the peer key over as "
  "raw X||Y, so the SEC1 0x04 byte has to be prepended before parsing. And the signature has to be "
  "DER encoded, since the CRC is computed over DER and not over raw r||s.")
code([
    "bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh build",
    "bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh -p COM17 flash",
])
p("Look for 14 lines where crc matches expected_crc, then the score line. On the MCX the project "
  "builds under MCUXpresso and flashes with LinkServer; the score file is "
  "results/securemark_score.txt.")

h("2. ML-KEM and ML-DSA, bare metal")
table(["Operation", "Mean cycles", "Time (ms)", "Stack HWM (B)", "Text (B)", "Data (B)"],
      [["ML-KEM-512 keypair", "2,978,432", "19.86", "8,960", "41,648", "40,928"],
       ["ML-KEM-512 encaps", "3,503,918", "23.36", "11,592", "41,648", "40,928"],
       ["ML-KEM-512 decaps", "4,342,471", "28.95", "12,344", "41,648", "40,928"],
       ["ML-KEM-768 keypair", "4,893,951", "32.63", "13,056", "41,432", "42,400"],
       ["ML-KEM-768 encaps", "5,692,464", "37.95", "16,200", "41,432", "42,400"],
       ["ML-KEM-768 decaps", "6,809,160", "45.39", "17,272", "41,432", "42,400"],
       ["ML-KEM-1024 keypair", "7,644,704", "50.96", "18,176", "41,944", "44,032"],
       ["ML-KEM-1024 encaps", "8,582,539", "57.22", "21,832", "41,944", "44,032"],
       ["ML-KEM-1024 decaps", "10,008,989", "66.73", "23,384", "41,944", "44,032"]])
p("Stack peaks at 23.4 KB, on 1024 decapsulation, against 512 KB of SRAM, so key exchange has "
  "room. Signing is the awkward one. Medians are 43.7, 75.7 and 99.6 ms for 44, 65 and 87; worst "
  "cases are 262.9, 611.1 and 475.7 ms, which is 6.0x, 8.1x and 4.8x the median. ML-DSA-65 hit "
  "611 ms once in 2000 draws.")
p("The cause is rejection sampling: the signer keeps drawing candidates until one passes, so the "
  "tail is inherent. Budget the median and every quick test looks fine, right up to the missed "
  "deadline.")
p("Keypair and verify, for reference: ML-DSA-44 16.6 and 17.6 ms, ML-DSA-65 29.1 and 29.5, "
  "ML-DSA-87 49.2 and 50.3.")
code([
    "python codebase/projects/mlkem_bench/results/eembc_style/analyze_perf_memory.py",
    "python codebase/projects/mlkem_bench/results/eembc_style/analyze_energy.py",
])

h("3. Classical against PQC, one handshake each")
p("Both sides in the same shape, one key exchange plus one signature plus two verifications. The "
  "classical side is ECDH, ECDSA sign, and two ECDSA verifies; the PQC side is the same with "
  "ML-KEM and ML-DSA.")
table(["Board", "Suite", "Latency (ms)", "Delta"],
      [["MCXN947", "Classical ECDH + ECDSA P-256", "166.1", "reference"],
       ["MCXN947", "PQC L1 (ML-KEM-512 + ML-DSA-44)", "151.0", "-9.1%"],
       ["MCXN947", "PQC L3 (ML-KEM-768 + ML-DSA-65)", "250.7", "+50.9%"],
       ["MCXN947", "PQC L5 (ML-KEM-1024 + ML-DSA-87)", "375.2", "+125.9%"],
       ["ESP32-S3", "Classical ECDH + ECDSA P-256", "495.2", "reference"],
       ["ESP32-S3", "PQC L1 (ML-KEM-512 + ML-DSA-44)", "88.8", "-82.1%"],
       ["ESP32-S3", "PQC L3 (ML-KEM-768 + ML-DSA-65)", "134.2", "-72.9%"],
       ["ESP32-S3", "PQC L5 (ML-KEM-1024 + ML-DSA-87)", "187.1", "-62.2%"]])
p("Level 1 is the counterintuitive one: PQC is 9.1% faster on the MCX. The two verifications do "
  "it, since an ML-DSA verify costs about a third of an ECDSA verify. Levels 3 and 5 do cost more, "
  "up to 126% at L5. On the ESP32 every level is faster, by 62 to 82%, which says more about "
  "its software ECC rather than about cheap lattice arithmetic.")
p("Two caveats I want visible. The KEM half was measured at -O0, so the PQC column is worse than "
  "it needs to be. And there is no classical energy column, because SecureMark-TLS has not been on "
  "the PPK2 yet; the PQC side does have energy (6.63 mJ for an ML-KEM-768 handshake).")
code([
    "python codebase/projects/securemark_tls_mcxn947/migration_compare.py",
    "python codebase/projects/securemark_tls_esp32s3/cross_platform_compare.py",
])
p("The first prints -9.1% and +50.9% for the MCX. The second prints -82.1, -72.9 and -62.2 for "
  "the ESP32.")

h("4. DTLS Connection ID, a model rather than a capture")
p("Arithmetic on the measured handshake energy, not a measurement of its own, so keep it separate. "
  "The question is what happens if the device resumes with a Connection ID instead of doing a full "
  "handshake each wakeup, on a CR2032 at 225 mAh.")
p("At 24 wakeups a day the MCX saves 3% and the ESP32 24%. Push to 2880 a day and the MCX saves "
  "80%, the ESP32 97%, which takes the coin cell from 88 days to roughly 1740. The saving scales "
  "with how often the device wakes, and it's larger on the board whose handshake is expensive.")
code(["python codebase/projects/securemark_tls_mcxn947/dtls_cid_model.py"])

h("5. Sharing one core, and the power trace")
p("The handshake is cut into pieces that run in the gaps between 33.3 ms frames instead of "
  "blocking a frame. The joint "
  "scheduler, which picks both the security level and the exit depth, finishes the test set in "
  "45.9 s and 2079 mJ with no missed deadlines; the naive policy takes 78.4 s and 3382 mJ and "
  "misses 70. Fixed early-exit policies sit between those two and still miss 70.")
p("On leakage, dummy cryptographic operations at p=0.3 take an attacker's accuracy at identifying "
  "the running operation from 100% down to 75%. Dummying only when the network exits early reaches "
  "70%. The defense isn't free: at ML-KEM-768 the misses reappear, so the trace can be blurred "
  "but not erased, and the blur costs energy.")
code([
    "python codebase/training_archive/training/conformal/joint_scheduler.py",
    "python codebase/training_archive/training/conformal/selective_obfuscation.py",
])
p("In the first script, read the learned line on the test split.")

h("6. The same code on both cores")
p("One Zephyr build of ML-DSA, run on the Cortex-M33 and on the Xtensa, to decide whether the "
  "signing tail belongs to the silicon or to the algorithm. Worst over median comes out 7.1x, 6.0x "
  "and 5.9x for 44, 65 and 87, and those ratios are the same on both boards.")
p("So the tail is the algorithm. A faster core pulls the whole distribution down and leaves the "
  "ratio untouched, which means the deadline problem travels with the code onto better hardware.")

h("How the six connect")
p("One is the reference, two is the new cost, three compares them. Four asks how often the "
  "handshake has to be paid, five whether it can share the core and whether it leaks, six whether "
  "the tail is a board quirk. The dependencies are real: without one the percentages mean nothing, "
  "and without two's tail the scheduler in five would have been tuned to the median.")

h("Open items")
bullet("STM32N6570 builds and flashes but prints nothing on the console. Unresolved, left out of the results.")
bullet("No classical energy, since SecureMark-TLS has not been captured on the PPK2.")
bullet("ML-KEM bare metal is -O0, which makes section 3 pessimistic.")
bullet("Zero misses is the joint scheduler on the test set. The 1230-frame interleaved capture shows about 10% for the three fixed policies, a harder run and a separate figure.")

h("Where the code sits")
bullet("securemark_tls_mcxn947/ and securemark_tls_esp32s3/: SecureMark ports, migration_compare.py, cross_platform_compare.py, dtls_cid_model.py")
bullet("mlkem_bench/ and mldsa_bench_nxp/: primitive benchmarks and their raw CSVs")
bullet("training/conformal/: joint_scheduler.py, selective_obfuscation.py")
bullet("pqc_bench_zephyr/: the cross-board ML-DSA run")
p("The migration, CID, analyze and scheduler scripts run on a PC from the stored data. The "
  "SecureMark ports, the raw benchmark runs and the PPK2 captures need the boards.")

out = r"H:\z_thesis\fixes\PQC_lab_notes_v3.docx"
DOC.save(out)
print("wrote", out, "| paragraphs:", len(DOC.paragraphs), "tables:", len(DOC.tables))
