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


DOC.add_heading("Lab notes: PQC benchmarks on the two boards", level=0)
p("Zain. M.Sc. Autonomous Systems. Supervisors: Prof. Houben and Prof. Tschofenig.")
p("Boards: MCXN947 (Cortex-M33, 150 MHz) and ESP32-S3 (Xtensa LX7, 240 MHz). These are my "
  "working notes. Every number in them is printed by code in the repo, and nothing is quoted "
  "from a paper.")

h("Why I ran any of this")
p("I wanted a straight answer to one question. When the handshake moves off classical ECDH and "
  "ECDSA and onto ML-KEM and ML-DSA, what does that cost on a small MCU, and can we live with it. "
  "The usual answer is \"PQC is slow\", but that mostly comes from servers and desktop libraries, "
  "so I measured it here instead.")
p("The second half is whether the cost can be paid less often, or hidden, or squeezed alongside a "
  "real-time loop on one core. That turned into the later experiments.")

h("The rig")
p("Timing is hardware counters. DWT->CYCCNT on the MCX, the CCOUNT register on the ESP32. Divide "
  "cycles by the clock and you've got microseconds. Both boards run free while I capture. Leave "
  "the debugger attached or the serial line open and the numbers drift, so I unplug them first.")
p("For stack I paint the task stack with 0xEE at boot and then look for the deepest byte that "
  "survived. Peak use, no guessing.")
p("Energy is a PPK2 at 10 kHz, 3.3 V, in series with the board supply. On the MCX that means the "
  "J24 rail, on the ESP32 the 3V3 pin. Small warning if you try this: with the J24 jumper off, "
  "LinkServer refuses to flash and says \"Target Operation Failed\", which reads like a dead board "
  "and is actually just the jumper. Cost me an afternoon.")
p("Sample counts are 100 per KEM operation and 2000 per signing test, fresh randomness on every "
  "sign.")
p("One thing isn't matched and I'd rather say it than paper over it: bare-metal ML-KEM is built at "
  "-O0, ML-DSA at -O2, and the classical suite at -O2. So the PQC side of the migration numbers is "
  "pessimistic.")

h("1. The classical reference (SecureMark-TLS)")
p("This is the official EEMBC self-hosted suite. 14 components, basically a TLS 1.2 handshake: "
  "AES-128 in ECB and CCM, SHA-256, ECDH P-256, ECDSA P-256. mbedTLS 3.6.3 on the MCX, the "
  "ESP-IDF mbedTLS on the ESP32, -O2 on both.")
p("MCX came out at 5472.08 marks. ESP32 at 1895.06. Both pass 14 of 14 CRC checks, and that's the "
  "whole point, because a score without the CRC passes isn't comparable to the published EEMBC "
  "numbers.")
p("Three things fought me before it would run. mbedTLS aborted the ECDH call until I gave it an "
  "RNG for point blinding; without one it returns MBEDTLS_ERR_ECP_BAD_INPUT_DATA, which sounds "
  "like bad input and is really a missing RNG. EEMBC passes the peer key as raw X||Y, so you have "
  "to prepend the SEC1 0x04 byte yourself. And the signature has to be DER encoded, not raw r||s, "
  "or the CRC fails and you go looking for a bug that isn't there.")
code([
    "bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh build",
    "bash codebase/projects/securemark_tls_esp32s3/scripts/build.sh -p COM17 flash",
])
p("Watch for 14 lines where crc equals expected_crc, then \"SecureMark-TLS Score is 1895.064 "
  "marks\". The MCX version builds under MCUXpresso and flashes with LinkServer; its score sits in "
  "results/securemark_score.txt.")

h("2. ML-KEM and ML-DSA on their own")
p("PQClean, bare metal on the MCX, no OS in the way.")
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
p("Nothing here is tight. The heaviest stack is ML-KEM-1024 decapsulation at 23.4 KB and there's "
  "512 KB of SRAM, so key exchange isn't the problem.")
p("Signing is the problem.")
table(["Level", "Median (ms)", "Worst case (ms)", "Worst / median"],
      [["ML-DSA-44", "43.7", "262.9", "6.0x"],
       ["ML-DSA-65", "75.7", "611.1", "8.1x"],
       ["ML-DSA-87", "99.6", "475.7", "4.8x"]])
p("The median is fine. The tail isn't, and it isn't small: ML-DSA-65 touched 611 ms once out of "
  "2000. The reason is rejection sampling, the signer draws a candidate and throws it away until "
  "one passes. A design that budgets the median will pass every quick test and then miss a "
  "deadline in the field.")
p("Keypair and verify, if useful: ML-DSA-44 is 16.6 and 17.6 ms, ML-DSA-65 is 29.1 and 29.5, "
  "ML-DSA-87 is 49.2 and 50.3.")
code([
    "python codebase/projects/mlkem_bench/results/eembc_style/analyze_perf_memory.py",
    "python codebase/projects/mlkem_bench/results/eembc_style/analyze_energy.py",
])

h("3. Classical against PQC, same handshake shape")
p("To compare fairly I put both sides in the same shape: one key exchange, one signature, two "
  "verifications. Classical is ECDH plus one ECDSA sign plus two ECDSA verifies. PQC is the same "
  "with ML-KEM and ML-DSA.")
table(["Board", "Suite", "Latency (ms)", "Delta"],
      [["MCXN947", "Classical ECDH + ECDSA P-256", "166.1", "reference"],
       ["MCXN947", "PQC L1 (ML-KEM-512 + ML-DSA-44)", "151.0", "-9.1%"],
       ["MCXN947", "PQC L3 (ML-KEM-768 + ML-DSA-65)", "250.7", "+50.9%"],
       ["MCXN947", "PQC L5 (ML-KEM-1024 + ML-DSA-87)", "375.2", "+125.9%"],
       ["ESP32-S3", "Classical ECDH + ECDSA P-256", "495.2", "reference"],
       ["ESP32-S3", "PQC L1 (ML-KEM-512 + ML-DSA-44)", "88.8", "-82.1%"],
       ["ESP32-S3", "PQC L3 (ML-KEM-768 + ML-DSA-65)", "134.2", "-72.9%"],
       ["ESP32-S3", "PQC L5 (ML-KEM-1024 + ML-DSA-87)", "187.1", "-62.2%"]])
p("Level 1 is the one people don't expect. PQC is 9.1% faster on the MCX. The reason is the "
  "verifies: ML-DSA verify costs about a third of ECDSA verify and the handshake does two of "
  "them, which more than covers the heavier key exchange. Levels 3 and 5 do cost more, up to "
  "+126% at L5. On the ESP32 every level is faster, 62 to 82%, but that says more about its "
  "software ECC than about lattice math being cheap. It isn't.")
p("Two caveats, both real. The KEM half of the table was measured at -O0, so the PQC column is "
  "worse than it needs to be and matched -O2 should close part of the L3 gap. And there's no "
  "classical energy column at all, because SecureMark-TLS hasn't been on the PPK2 yet. PQC energy "
  "does exist (6.63 mJ for an ML-KEM-768 handshake) but I'm not filling a column that only has "
  "one side.")
code([
    "python codebase/projects/securemark_tls_mcxn947/migration_compare.py",
    "python codebase/projects/securemark_tls_esp32s3/cross_platform_compare.py",
])
p("First prints -9.1% and +50.9% for the MCX, second prints -82.1, -72.9, -62.2 for the ESP32.")

h("4. DTLS Connection ID (this one is a model)")
p("Keep this separate from the measurements, because it's arithmetic on measured energy, not a "
  "capture. The question: what if the device resumes with a Connection ID instead of doing a full "
  "handshake every time it wakes up. Cell is a CR2032, 225 mAh.")
table(["Board", "Wake ups / day", "Full handshake (mJ)", "With CID (mJ)", "Saving"],
      [["MCXN947", "24", "1340.9", "1297.9", "3.2%"],
       ["MCXN947", "2880", "6685.2", "1301.5", "80.5%"],
       ["ESP32-S3", "24", "1735.1", "1315.6", "24.2%"],
       ["ESP32-S3", "2880", "53991.6", "1478.7", "97.3%"]])
p("At 24 wake ups a day on the MCX it saves 3%, which is nothing. At 2880 a day it's 80%, and on "
  "the ESP32 97%, which stretches the coin cell from 88 days to about 1740. The pattern is dull "
  "but useful: resumption matters more the busier the device is, and more on the board with the "
  "expensive handshake.")
code(["python codebase/projects/securemark_tls_mcxn947/dtls_cid_model.py"])

h("5. Sharing the core, and blurring the power trace")
p("Two questions. Can a handshake run next to a 30 fps loop, so 33.3 ms per frame. And can the "
  "power trace be made less useful to someone who's listening.")
p("The deadline half works, and it works well. Chop the handshake into pieces that fit in the "
  "gaps between frames rather than blocking a frame. The joint scheduler, which picks both the "
  "security level and the exit depth, gets through the test set in 45.9 s and 2079 mJ with zero "
  "missed deadlines. The naive policy takes 78.4 s and 3382 mJ and misses 70. Fixed early-exit "
  "policies land in between and still miss 70.")
p("The power half works less well. Dummy crypto at p=0.3 drops an attacker's accuracy at telling "
  "which operation is running from 100% to 75%. A variant that only dummies when the network "
  "exits early gets to 70%. At ML-KEM-768 the dummies stop being free and the misses come back. "
  "So you can blur the trace, you can't erase it, and you pay for the blur.")
code([
    "python codebase/training_archive/training/conformal/joint_scheduler.py",
    "python codebase/training_archive/training/conformal/selective_obfuscation.py",
])
p("In the first, the learned line on the test split is the one to read: 45920.7 ms, 2078.9 mJ, "
  "0 misses.")

h("6. Same code, two very different cores")
p("I ran one Zephyr build of ML-DSA on both boards to settle whether the tail is the chip or the "
  "algorithm.")
p("The worst over median comes out 7.1x, 6.0x and 5.9x for 44, 65 and 87. Same on the Cortex-M33 "
  "and the Xtensa. Not similar, identical.")
p("So the tail is the algorithm, and it follows you onto faster hardware. A quicker core drags "
  "the whole distribution down and leaves the ratio where it was. The scheduling problem doesn't "
  "go away when you buy a better board.")

h("How the six fit together")
p("I ran them in this order for a reason. Section 1 is the reference, section 2 is the new cost, "
  "section 3 puts them side by side and is the actual migration answer. Section 4 asks how often "
  "you have to pay it. Section 5 asks whether it can share the core and whether it leaks. Section "
  "6 checks the tail isn't a quirk of one board.")
p("Two of them lean hard on the earlier ones. Without the baseline the percentages mean nothing. "
  "And without the tail measurement the scheduler would have been built around the median, which "
  "is the number that looks safe right up until it misses.")

h("What's not finished")
p("STM32N6570 builds, loads, and then prints nothing on the console. I haven't found it yet, so "
  "it isn't in the results.")
p("No classical energy. SecureMark-TLS hasn't been on the PPK2.")
p("Bare-metal ML-KEM is -O0, so the PQC side of section 3 is pessimistic on purpose.")
p("The deadline number depends on which capture you read. Zero misses is the joint scheduler on "
  "the test set. The 1230-frame interleaved capture shows about 10% for the three fixed policies, "
  "which is a harder run and its own number, not a contradiction.")

h("Where the code is")
table(["Experiment", "Folder", "Command", "Expect"],
      [["SecureMark", "securemark_tls_mcxn947, securemark_tls_esp32s3", "build.sh / flash",
        "5472.08 / 1895.06, 14/14 CRC"],
       ["Primitives", "mlkem_bench, mldsa_bench_nxp", "analyze_perf_memory.py", "tables above"],
       ["Migration", "securemark_tls_mcxn947, securemark_tls_esp32s3", "migration_compare.py",
        "-9.1% / +50.9%"],
       ["DTLS CID", "securemark_tls_mcxn947", "dtls_cid_model.py", "daily_energy.csv"],
       ["Scheduler", "training/conformal", "joint_scheduler.py", "45920.7 ms, 0 misses"],
       ["Obfuscation", "training/conformal", "selective_obfuscation.py", "100% to 75%"],
       ["Cross-board tail", "pqc_bench_zephyr", "Zephyr build", "7.1x / 6.0x / 5.9x"]])
p("The migration, CID and analyze scripts all run from the stored data on any PC. The two "
  "SecureMark ports, the raw benchmark runs and the PPK2 captures need the boards.")

out = r"H:\z_thesis\fixes\PQC_lab_notes_v2.docx"
DOC.save(out)
print("wrote", out)
print("paragraphs:", len(DOC.paragraphs), "tables:", len(DOC.tables))
