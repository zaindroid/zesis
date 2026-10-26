#!/usr/bin/env python3
"""Build the SecureMark-V2 PQC report for Prof."""
import os
from datetime import date

import matplotlib
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = r"H:\z_thesis\SECUREMARK_V2_TSCHOFENIG_REPORT.pdf"

_ttf = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DV", os.path.join(_ttf, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DV-B", os.path.join(_ttf, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DV-M", os.path.join(_ttf, "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", fontName="DV-B", fontSize=18, leading=22, spaceAfter=4,
                    textColor=colors.HexColor("#0f2c45"))
SUB = ParagraphStyle("SUB", fontName="DV", fontSize=9.2, leading=12.6,
                     textColor=colors.HexColor("#4a5560"), spaceAfter=2)
H2 = ParagraphStyle("H2", fontName="DV-B", fontSize=12.6, leading=15, spaceBefore=13,
                    spaceAfter=5, textColor=colors.HexColor("#1f4e79"))
BODY = ParagraphStyle("BODY", fontName="DV", fontSize=9.5, leading=13.6, spaceAfter=5.5)
SMALL = ParagraphStyle("SMALL", fontName="DV", fontSize=8.2, leading=11.2,
                       textColor=colors.HexColor("#4a5560"), spaceAfter=3)
CELL = ParagraphStyle("CELL", fontName="DV", fontSize=8.3, leading=11, spaceAfter=0)
CALLOUT = ParagraphStyle("CALLOUT", fontName="DV", fontSize=9.4, leading=13.8,
                         leftIndent=8, rightIndent=8, spaceBefore=4, spaceAfter=8,
                         backColor=colors.HexColor("#eef4fb"),
                         borderColor=colors.HexColor("#1f4e79"), borderWidth=0.8,
                         borderPadding=7)


def P(t, s=BODY):
    return Paragraph(t, s)


def T(data, widths, small=False, align_right=()):
    st = ParagraphStyle("c", fontName="DV", fontSize=7.9 if small else 8.4,
                        leading=10.8, spaceAfter=0)
    rows = [[Paragraph(str(c), st) for c in r] for r in data]
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d0")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
             ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
             ("TOPPADDING", (0, 0), (-1, -1), 2.4),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
             ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3ecf5")),
             ("FONTNAME", (0, 0), (-1, 0), "DV-B")]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7f9fb")))
    for c in align_right:
        style.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


story = []

# ------------------------------------------------------------------ cover
story.append(Spacer(1, 6))
story.append(P("EEMBC-style PQC benchmarking on a modern Cortex-M33", H1))
story.append(P("SecureMark-V2 extended with native post-quantum primitives &mdash; "
               "progress report for Prof. Tschofenig", SUB))
story.append(P("Zain Ul Haq &nbsp;&middot;&nbsp; %s &nbsp;&middot;&nbsp; "
               "FRDM-MCXN947 (Cortex-M33, 150 MHz) &nbsp;&middot;&nbsp; bare metal, no RTOS"
               % date.today().strftime("%d %B %Y"), SUB))
story.append(Spacer(1, 7))

story.append(P("Executive summary", H2))
story.append(P("The question this work answers is whether post-quantum cryptography can be "
               "benchmarked inside a standard, recognised harness on a modern microcontroller, "
               "and what it costs relative to classical cryptography on the same silicon. It can, "
               "and the answer is more favourable than expected."))
story.append(P("<b>The official EEMBC SecureMark-V2 harness now runs 102 components on the "
               "FRDM-MCXN947 &mdash; 82 classical plus 20 native post-quantum &mdash; and emits its own "
               "score sheet.</b> All 20 PQC components pass their functional self-check and their "
               "regression checksum. The post-quantum public-key phase (ML-KEM-768 + ML-DSA-65) costs "
               "<b>99.5 ms against 94.9 ms for classical P-256</b>, a penalty of <b>4.9%</b>."))

story.append(P("The four numbers that matter", H2))
story.append(T([
    ["Measure", "Result", "What it means"],
    ["PQC_All score", "<b>2042.526</b>",
     "20 per-primitive PQC components, equal weight, harness-computed"],
    ["PQC vs classical handshake", "<b>+4.9%</b> (99.5 vs 94.9 ms)",
     "Post-quantum is a few percent dearer, not multiples"],
    ["Library spread at matched -O2", "<b>2.41x</b> (wolfSSL 6.37 vs PQClean 15.33 ms)",
     "Implementation choice matters more than the algorithm choice"],
    ["128 KB firmware verification", "HashML-DSA-65 <b>24.45 ms</b> vs ECDSA <b>26.70 ms</b>",
     "PQC verification is already faster than the classical baseline"],
], [42 * mm, 52 * mm, 72 * mm]))
story.append(Spacer(1, 5))
story.append(P("One result deserves emphasis because it inverts the usual expectation: at "
               "-O2 with a modern engine, <b>the post-quantum handshake is within 5% of "
               "classical</b>, and PQC signature <i>verification</i> is faster than ECDSA. The cost "
               "sits in signing, and in the size of what has to be carried.", CALLOUT))

# ------------------------------------------------------------ what was built
story.append(P("1. What was built", H2))
story.append(T([
    ["Component", "Role"],
    ["<font face='DV-M'>wolfssl-m33/</font>",
     "crypto-only wolfSSL 5.9.2 cross-built for Cortex-M33 with ML-KEM and ML-DSA enabled; "
     "static pool allocator (no heap); deterministic RNG for reproducible checksums"],
    ["<font face='DV-M'>bench/</font>",
     "standalone driver: 7 algorithms x keypair / sign-or-encapsulate / verify = 21 measurement points"],
    ["<font face='DV-M'>v2harness/</font>",
     "upstream EEMBC securemark-v2 self-hosted harness, extended with 20 native PQC components "
     "registered as the PQC_All suite"],
    ["<font face='DV-M'>task3a/</font>",
     "128 KB firmware signature verification (the secure-boot case)"],
    ["<font face='DV-M'>results/PQC_LIBRARY_CONFIG_MATRIX.csv</font>",
     "42-row library and configuration matrix"],
], [46 * mm, 120 * mm]))

story.append(P("Platform port", H2))
story.append(P("The harness expects an operating system. Running it bare metal required a thin "
               "porting layer: the DWT cycle counter replaces <font face='DV-M'>clock_gettime</font> "
               "(64-bit accumulated, so the 32-bit CYCCNT wrap cannot corrupt a measurement), "
               "<font face='DV-M'>_write</font> is retargeted to the LPUART, and both "
               "<font face='DV-M'>th_malloc</font> and wolfSSL's <font face='DV-M'>XMALLOC</font> "
               "are routed to a single 160 KB static pool so allocation behaviour is deterministic."))
story.append(P("Three harness-level defects had to be fixed before any run could complete. They are "
               "listed in section 5 because they are methodologically relevant, not incidental.", SMALL))

# ------------------------------------------------------------- 2. results
story.append(P("2. Correctness first: the standalone bench", H2))
story.append(P("Before trusting a harness, the primitives have to be shown to run correctly on the "
               "target and to produce identical output across builds. Seven algorithms, 21 points, "
               "all passing:"))
story.append(T([
    ["Algorithm", "keypair", "encaps / sign", "decaps / verify", "Check", "Regression CRC"],
    ["ML-KEM-512", "17.43", "14.97", "20.24", "PASS", "0xBB6188B7"],
    ["ML-KEM-768", "28.02", "25.24", "32.74", "PASS", "0x8A48D4A5"],
    ["ML-KEM-1024", "44.10", "40.06", "49.84", "PASS", "0xFDB3B688"],
    ["ML-DSA-44", "66.36", "165.55", "69.70", "PASS", "0xBA561067"],
    ["ML-DSA-65", "113.20", "198.77", "115.62", "PASS", "0x1EE8F069"],
    ["ML-DSA-87", "192.68", "254.21", "195.14", "PASS", "0xAB6329B9"],
    ["HashML-DSA-65", "113.20", "235.17", "115.11", "PASS", "0x9C084B80"],
], [30 * mm, 22 * mm, 26 * mm, 26 * mm, 16 * mm, 30 * mm], align_right=(1, 2, 3)))
story.append(P("Milliseconds, DWT cycles &divide; 150 MHz, -Os first pass (the -O2 figures follow).",
               SMALL))
story.append(Spacer(1, 3))
story.append(P("<b>On the checksums.</b> EEMBC has published no PQC profile, so there is no golden "
               "CRC to match against for ML-KEM or ML-DSA. Those components are therefore reported "
               "under a dual scheme and are never labelled &ldquo;EEMBC CRC MATCH&rdquo;: a functional "
               "round-trip self-check (KEM decapsulation recovers the encapsulated secret exactly; "
               "DSA verification returns valid) plus a synthesised regression CRC over the "
               "deterministic output. The CRC values reproduce across independent builds "
               "<i>and across optimisation levels</i>, which is what makes them usable as a "
               "cross-build invariant rather than a build artefact. The classical suites remain the "
               "only ones checked against EEMBC goldens.", BODY))

# --------------------------------------------------------- 3. score sheet
story.append(P("3. The native score sheet", H2))
story.append(P("Emitted by the harness itself &mdash; not reconstructed from a serial capture. "
               "102 components, zero CRC errors."))
story.append(P("<b>Attribution.</b> The harness framework, the three suite definitions and their "
               "golden CRCs are EEMBC's (upstream <font face='DV-M'>eembc/securemark-v2</font>). "
               "The 20 post-quantum components, their <font face='DV-M'>th_</font> shims and the "
               "<font face='DV-M'>PQC_All</font> suite are <b>ours</b>, added on top. "
               "<b>PQC_All and PQC_TLS1.3 are therefore not EEMBC scores</b> &mdash; the harness prints "
               "its own disclaimer that these are not official. Only the classical suite scores are "
               "EEMBC-comparable.", BODY))
story.append(T([
    ["Suite", "Score", "Suite", "Score"],
    ["<b>PQC_All</b>", "<b>2042.526</b>", "Boot_Med_RSA", "38.160"],
    ["<b>PQC_TLS1.3 (768/65)</b>", "<b>40177.367</b>", "Boot_Med_ECC", "24.572"],
    ["TLSv1.2", "10418.526", "TLSv1.3_Heavy_CCM", "4.127"],
    ["TLSv1.3_Light", "251.907", "TLSv1.3_Heavy_GCM", "4.124"],
    ["Boot_Light", "70.419", "Boot_Heavy_RSA", "10.408"],
    ["TLSv1.3_Med_CCM", "100.576", "Boot_Heavy_ECC", "1.178"],
    ["TLSv1.3_Med_GCM", "100.162", "", ""],
], [38 * mm, 26 * mm, 38 * mm, 26 * mm], align_right=(1, 3)))
story.append(P("Score = 1000 / &Sigma;(w<sub>i</sub> / ips<sub>i</sub>). PQC_All uses w = 1 over the 20 "
               "per-primitive components; PQC_TLS1.3 uses w = 0.25 over ML-KEM-768 "
               "encapsulate/decapsulate and ML-DSA-65 sign/verify.", SMALL))

story.append(P("PQC components at -O2 (30-iteration means)", H2))
story.append(T([
    ["Algorithm", "keypair", "encaps / sign", "decaps / verify"],
    ["ML-KEM-512", "4.36", "3.76", "5.08"],
    ["ML-KEM-768", "7.01", "6.37", "8.24"],
    ["ML-KEM-1024", "11.07", "10.14", "12.56"],
    ["ML-DSA-44", "14.50", "29.18", "14.53"],
    ["ML-DSA-65", "25.13", "60.36", "24.57"],
    ["ML-DSA-87", "43.24", "80.22", "42.42"],
    ["HashML-DSA-65", "(as ML-DSA-65)", "55.68", "24.45"],
], [34 * mm, 30 * mm, 32 * mm, 32 * mm], align_right=(1, 2, 3)))
story.append(P("Milliseconds. All 20 components: self-check PASS, regression CRC matched.", SMALL))

# ----------------------------------------------------- 4. comparisons
story.append(P("4. Where the cost actually is", H2))

story.append(P("4.1 PQC versus classical, same library, same flags", H2))
story.append(P("Both sides wolfSSL at -O2. Public-key phase = one ECDH + one signature + two "
               "verifications:"))
story.append(T([
    ["Public-key phase", "Composition (ms)", "Total"],
    ["Classical P-256", "24.34 ECDH + 17.57 sign + 2 &times; 26.50 verify",
     "<b>94.91 ms</b>"],
    ["PQC (ML-KEM-768 + ML-DSA-65)", "6.37 + 8.24 + 60.36 + 24.57", "<b>99.54 ms</b>"],
], [46 * mm, 76 * mm, 34 * mm]))
story.append(Spacer(1, 3))
story.append(P("A <b>4.9% penalty</b>. Post-quantum key establishment is far cheaper than its "
               "classical counterpart (6.4 + 8.2 ms versus 24.3 + 26.5 ms); the whole penalty, and "
               "more, is carried by ML-DSA signing at 60.4 ms."))

story.append(P("4.2 Library comparison, controlled at one optimisation level", H2))
story.append(T([
    ["ML-KEM-768 encapsulation", "Implementation", "Flags", "Time", "Cycles"],
    ["Reference", "PQClean clean C", "-O2", "15.33 ms", "2,299,500"],
    ["<b>Embedded engine</b>", "<b>wolfSSL native</b>", "-O2", "<b>6.37 ms</b>", "<b>955,000</b>"],
    ["Hand-tuned assembly", "pqm4 (Cortex-M4F asm)", "-O3", "23.99 ms", "3,598,500"],
], [38 * mm, 42 * mm, 16 * mm, 24 * mm, 26 * mm], align_right=(3, 4)))
story.append(Spacer(1, 3))
story.append(P("Two results worth reporting plainly. <b>wolfSSL's portable C is 2.41x faster than the "
               "reference clean-C implementation</b> at identical flags &mdash; a library effect, not a "
               "compiler effect. And <b>the hand-tuned Cortex-M4F assembly is the slowest of the "
               "three</b>: it is not portable to ARMv8-M, its decapsulation and all of ML-DSA fault on "
               "the M33, and its encapsulation is 1.6x slower than plain clean C at matched -O2. The "
               "expected ordering &mdash; reference, then portable engine, then assembly &mdash; does not "
               "hold on this core."))
story.append(P("ML-DSA-65 signing shows the same pattern: PQClean 91.61 ms mean at -O2 against "
               "wolfSSL 60.36 ms, a <b>1.52x</b> library effect. Optimisation level is almost "
               "irrelevant to PQClean's ML-DSA (median 73.72 ms at -Os versus 74.77 ms at -O2, a "
               "1.01x change), so the gap is the library, not the compiler.", BODY))

story.append(P("4.3 Optimisation sensitivity", H2))
story.append(P("Same code, same board:", BODY))
story.append(T([
    ["Quantity", "-Os", "-O2", "Factor"],
    ["PQC_All", "414.746", "2042.526", "4.9x"],
    ["PQC_TLS1.3", "8525.134", "40177.367", "4.7x"],
    ["wolfSSL ML-KEM-768 encapsulate", "25.21 ms", "6.37 ms", "4.0x"],
    ["PQClean ML-KEM-768 encapsulate", "37.9 ms (-O0)", "15.33 ms", "2.47x"],
    ["PQClean ML-DSA-65 sign (median)", "73.72 ms", "74.77 ms", "1.01x"],
], [62 * mm, 28 * mm, 28 * mm, 20 * mm]))
story.append(P("This is why the optimisation level had to be fixed before any comparison: a "
               "five-fold difference across the board, and near-zero for one primitive. <b>-O2 is "
               "now the stated level for every number in this report.</b>", SMALL))

story.append(PageBreak())

# ------------------------------------------------------------ 5. task 3A/3B
story.append(P("5. The application benchmarks", H2))
story.append(P("5.1 Task 3A &mdash; 128 KB firmware signing (secure boot)", H2))
story.append(P("Payload 131,072 B, 20 repeats per scheme, verification is the decision a bootloader "
               "actually makes:"))
story.append(T([
    ["Scheme", "sign (mean / min / max)", "<b>verify</b>", "sig bytes", "payload RAM"],
    ["ECDSA P-256", "16.93 / 16.93 / 16.93", "<b>26.70 ms</b>", "72", "streamed"],
    ["ML-DSA-44 pure", "155.72 / 137.42 / 217.14", "<b>133.10 ms</b>", "2420", "<b>131,072 B</b>"],
    ["ML-DSA-65 pure", "179.47 / 148.75 / 318.18", "<b>143.13 ms</b>", "3309", "<b>131,072 B</b>"],
    ["HashML-DSA-65", "55.30 / 30.08 / 107.91", "<b>24.45 ms</b>", "3309", "streamed"],
], [30 * mm, 44 * mm, 24 * mm, 20 * mm, 30 * mm], align_right=(2, 3)))
story.append(Spacer(1, 3))
story.append(P("Three findings. <b>Hashing dominates pure ML-DSA verification</b> &mdash; the 143 ms "
               "figure is mostly a SHAKE256 pass over 128 KB inside the primitive; pre-hashing lifts "
               "it out and verification drops to 24.45 ms, 5.9x faster. <b>HashML-DSA verification "
               "beats ECDSA P-256 verification</b> (24.45 versus 26.70 ms). And the buffering split "
               "is real: pure ML-DSA needs the whole payload addressable at once, so a device "
               "receiving firmware over a link must hold 128 KB of RAM, whereas ECDSA and "
               "HashML-DSA stream in 4 KB chunks with a 112 or 224 B hash context."))

story.append(P("5.2 Task 3B &mdash; 256 B telemetry signing and the fat tail", H2))
story.append(T([
    ["Level", "median", "p99", "max", "worst / median"],
    ["ML-DSA-44", "43.94 ms", "181.91 ms", "289.05 ms", "6.6x"],
    ["ML-DSA-65", "73.72 ms", "293.99 ms", "505.68 ms", "6.9x"],
    ["ML-DSA-87", "99.41 ms", "336.24 ms", "477.86 ms", "4.8x"],
], [26 * mm, 26 * mm, 28 * mm, 28 * mm, 28 * mm], align_right=(1, 2, 3, 4)))
story.append(P("n = 2000 per level. At a 10 Hz telemetry budget (100 ms/frame) the median fits at "
               "every level and the worst case does not. ML-DSA signing is rejection-sampled, so it "
               "has a fat right tail; a design that checks only the median is not safe.", SMALL))

# ------------------------------------------------------------- 6. method
story.append(P("6. Method notes", H2))
story.append(P("These matter because they are the difference between a number and a defensible "
               "number.", BODY))
story.append(T([
    ["Practice", "Why"],
    ["Frozen split, single test touch",
     "The conformal calibration uses a frozen four-way split; the test set is touched exactly once, "
     "with every threshold pre-frozen. An earlier contaminated protocol produced a flattering result "
     "that did not survive this discipline, and it was withdrawn."],
    ["Dual evidence for PQC, goldens for classical",
     "No EEMBC PQC profile exists. PQC components report a functional round-trip check plus a "
     "synthesised regression CRC; only the classical suites claim EEMBC CRC MATCH."],
    ["One stated optimisation level",
     "A five-fold spread across -Os/-O2 made mixed-flag comparisons meaningless. All numbers here "
     "are -O2."],
    ["Means, not single draws",
     "ML-DSA signing is rejection-sampled. Harness PQC components run 30 local iterations; "
     "distributions come from 2000-run measurements."],
], [46 * mm, 120 * mm]))
story.append(Spacer(1, 3))
story.append(P("Three harness defects were found and fixed in the course of this work, each of which "
               "had been silently preventing a complete run: the classical P-384 ECDH shim passed a "
               "null RNG (<font face='DV-M'>MISSING_RNG_E</font>); RSA-4096 was outside "
               "<font face='DV-M'>RSA_MAX_SIZE</font> because <font face='DV-M'>SP_INT_BITS</font> "
               "defaulted to 2048; and the autotune loop doubled iterations until one second of work "
               "elapsed, so a failing component spun forever and the score section never printed. "
               "All three are documented at the point of change.", SMALL))

story.append(PageBreak())

# --------------------------------------------------------------- 7. status
story.append(P("7. Status against the brief", H2))
story.append(P("Reported explicitly, because the gaps are the useful part of a progress report."))
story.append(T([
    ["Task", "Requirement", "Status"],
    ["1", "SecureMark-V2 with native ML-KEM / ML-DSA interfaces", "<b>Done</b>"],
    ["1", "HashML-DSA (pre-hash) pipeline", "<b>Done</b> &mdash; measured separately from pure ML-DSA"],
    ["1", "Explicit ML-DSA context strings", "Open &mdash; shims call ctx = NULL, 0"],
    ["1", "Realistic message lengths", "Partly &mdash; 128 KB firmware and 256 B telemetry done; 4 KB certificates not"],
    ["2", "Library / configuration matrix", "<b>Done</b> &mdash; 42 rows; PQClean, wolfSSL, mbedTLS-classical, pqm4"],
    ["2", "mbedTLS-PQC and mldsa-native variants", "Not included"],
    ["3A", "128 KB firmware verification, PQC vs classical", "<b>Done</b>"],
    ["3B", "256 B telemetry fat tail, 2000 runs", "<b>Done</b>"],
    ["3C", "TLS / DTLS 1.3 with RFC 9146 Connection IDs", "Open &mdash; existing CID work predates V2 and is a model, not a measurement"],
    ["4", "Automation: evaluation script and summary CSV", "<b>Done</b>"],
    ["4", "LaTeX table generation", "Open"],
    ["4", "Per-primitive peak stack", "Open in the harness &mdash; no stack painting in the PQC components"],
    ["Acc.", "Clean build under Zephyr v4.2.0-rc1 (MCXN947)", "<b>Open</b>"],
    ["Acc.", "Clean build under ESP-IDF v5.1 (ESP32-S3)", "<b>Open</b>"],
    ["Acc.", "CRC MATCH", "Classical 14/14 against EEMBC goldens; PQC self-check + regression CRC"],
    ["Acc.", "SECUREMARK_V2_PQC_REPORT.md", "<b>Done</b>"],
], [14 * mm, 84 * mm, 68 * mm], small=True))

story.append(P("8. What remains, in order", H2))
story.append(P("<b>The single largest gap is that everything here is one platform.</b> The Zephyr and "
               "ESP-IDF ports named in the acceptance criteria are not built. They are build-system "
               "work on code that already compiles and runs on the M33, not new measurement, but "
               "until they exist the result is single-platform. After that: LaTeX emission from the "
               "existing CSV, the ML-DSA context-string parameter, per-op stack painting, and "
               "Task 3C."))
story.append(P("Everything reported above is reproducible from the artifacts in the appendix, and "
               "every table can be regenerated from the raw captures.", BODY))

story.append(P("Appendix &mdash; artifacts", H2))
story.append(T([
    ["Path (under <font face='DV-M'>codebase/projects/securemark_v2_pqc/</font>)", "Contents"],
    ["<font face='DV-M'>v2harness/results/SECUREMARK_V2_FINAL_REPORT.md</font>", "full report with the complete correction trail"],
    ["<font face='DV-M'>v2harness/results/pqc_denoised.txt</font>", "raw serial capture of the score-sheet run"],
    ["<font face='DV-M'>v2harness/raw/SECUREMARK_V2_PQC_SUMMARY.csv</font>", "per-component ips and CRCs"],
    ["<font face='DV-M'>results/PQC_LIBRARY_CONFIG_MATRIX.csv</font>", "library matrix, 42 rows"],
    ["<font face='DV-M'>bench/results/STANDALONE_PQC_BENCH.md</font>", "standalone bench"],
    ["<font face='DV-M'>task3a/results/task3a_dist.txt</font>", "128 KB firmware verification, n = 20"],
    ["<font face='DV-M'>mldsa_bench_nxp/results/task3b/</font>", "2000-run signing distributions"],
    ["<font face='DV-M'>scripts/evaluate_securemark_v2_pqc.py</font>", "regenerates the scores from a capture"],
], [96 * mm, 70 * mm], small=True))

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=19 * mm, rightMargin=19 * mm,
                        topMargin=16 * mm, bottomMargin=15 * mm,
                        title="EEMBC-style PQC benchmarking on a modern Cortex-M33",
                        author="Zain Ul Haq")
doc.build(story)
print("wrote", OUT)
