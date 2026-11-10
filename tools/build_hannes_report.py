#!/usr/bin/env python3
"""pqm4 re-run report for Hannes, written in the same plain register as the email."""
import os
from datetime import date

import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

OUT = r"H:\z_thesis\PQC_BENCHMARK_REPORT_HANNES.pdf"

_t = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DV", os.path.join(_t, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DV-B", os.path.join(_t, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DV-M", os.path.join(_t, "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")

H1 = ParagraphStyle("H1", fontName="DV-B", fontSize=14.5, leading=18, spaceAfter=2,
                    textColor=colors.HexColor("#1a1a1a"))
SUB = ParagraphStyle("SUB", fontName="DV", fontSize=8.8, leading=11.6,
                     textColor=colors.HexColor("#666666"), spaceAfter=1)
H2 = ParagraphStyle("H2", fontName="DV-B", fontSize=10.5, leading=13.2, spaceBefore=7,
                    spaceAfter=2, textColor=colors.HexColor("#1f4e79"))
BODY = ParagraphStyle("BODY", fontName="DV", fontSize=8.9, leading=11.9, spaceAfter=4)
NOTE = ParagraphStyle("NOTE", fontName="DV", fontSize=8.0, leading=10.5,
                      textColor=colors.HexColor("#555555"), spaceAfter=4)
CELL = ParagraphStyle("CELL", fontName="DV", fontSize=8.6, leading=11, spaceAfter=0)



CODE = ParagraphStyle("CODE", fontName="DV-M", fontSize=7.6, leading=10.2,
                      spaceBefore=2, spaceAfter=3, leftIndent=6,
                      backColor=colors.HexColor("#f4f4f4"), borderPadding=4)


def Code(t):
    return Paragraph(t.replace(" ", "&nbsp;").replace(chr(10), "<br/>"), CODE)

def P(t, s=BODY):
    return Paragraph(t, s)


def T(data, widths, right=()):
    rows = [[Paragraph(str(c), CELL) for c in r] for r in data]
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.HexColor("#888888")),
             ("LINEBELOW", (0, 0), (-1, 0), 0.4, colors.HexColor("#bbbbbb")),
             ("LINEBELOW", (0, -1), (-1, -1), 0.6, colors.HexColor("#888888")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3),
             ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("TOPPADDING", (0, 0), (-1, -1), 2.6),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
             ("FONTNAME", (0, 0), (-1, 0), "DV-B")]
    for c in right:
        style.append(("ALIGN", (c, 1), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


story = []
story.append(P("pqm4 benchmark re-run: ML-KEM-768 on the FRDM-MCXN947", H1))
story.append(P("Zain Ul Haq &nbsp;&middot;&nbsp; %s &nbsp;&middot;&nbsp; Cortex-M33 at 150 MHz, "
               "bare metal, all figures at -O2"
               % date.today().strftime("%d %B %Y"), SUB))
story.append(Spacer(1, 6))

story.append(P("The earlier 23.99 ms for ML-KEM-768 encapsulate came from a build with the SDK "
               "debug preset, which applies no optimisation flag, and was being compared against "
               "PQClean at -O2. That was not a matched comparison, so I re-ran it."))

story.append(P("What I did", H2))
story.append(P("I pinned pqm4 to <font face='DV-M'>cc2c1b9</font>, the commit your lockfile uses, "
               "applied <font face='DV-M'>patches/pqm4/0001-securemark-instrumentation.patch</font>, "
               "and rebuilt at -O2. I checked the compile database afterwards: all 24 pqm4 units "
               "carry -O2, so the level is what reaches the compiler rather than the SDK default."))
story.append(P("Sampling needed a workaround. pqm4 corrupts its state after the first "
               "keypair+encapsulate pair, so a loop hangs at iteration 1. Each sample therefore "
               "comes from its own boot: one keypair+encapsulate, print the cycle counts, reset, "
               "repeat. I captured 323 boots for m4fspeed and 321 for m4fstack. The cycle count was "
               "identical in every boot, so there is no scatter to report."))

story.append(P("The loop is in "
               "<font face='DV-M'>zain_pqc/results/pqm4/main.c</font>, guarded by "
               "<font face='DV-M'>#ifdef RESET_LOOP</font>.", NOTE))
story.append(P("Result", H2))
story.append(T([
    ["", "encapsulate", "cycles", "vs PQClean"],
    ["wolfSSL native", "6.37 ms", "955,000", "2.41x"],
    ["pqm4 m4fspeed", "<b>7.15 ms</b>", "1,072,869", "<b>2.14x</b>"],
    ["pqm4 m4fstack", "7.25 ms", "1,087,375", "2.11x"],
    ["PQClean clean C", "15.33 ms", "2,299,500", "1.00x"],
], [50 * mm, 30 * mm, 34 * mm, 30 * mm], right=(1, 2, 3)))
story.append(Spacer(1, 4))
story.append(P("m4fspeed and m4fstack are pqm4's two hand-written Cortex-M4F assembly variants: m4fspeed is "
               "tuned for speed, m4fstack for lower stack usage. They are named for the Cortex-M4F and are "
               "being run on the M33 here. PQClean is the portable C reference and the baseline this table "
               "is normalised against. For ML-KEM encapsulation the two pqm4 variants land within 1.35% of "
               "each other; the trade-off matters more for ML-DSA signing, where it is roughly 3x in pqm4's "
               "own figures.", NOTE))
story.append(Spacer(1, 5))
story.append(P("So pqm4 is the second fastest, not the slowest, and 12% behind wolfSSL. The earlier "
               "conclusion that hand-tuned assembly loses to portable C on this core does not hold."))
story.append(P("One limitation to keep in mind: the RNG seed is fixed per boot, so every boot ran "
               "the same computation. The zero scatter shows the measurement is repeatable, not that "
               "cost is independent of input. For ML-KEM encapsulation the cost is dominated by the "
               "NTT and should not move much, but I did not measure that.", NOTE))

story.append(P("What still doesn't work", H2))
story.append(P("Decapsulation hangs on the first call in both variants. No fault is raised, so it is "
               "a spin rather than an exception. Your framework reports 7.08 ms for that operation on "
               "the same board, and I cannot reproduce it with the single patch at the pinned commit. "
               "If you can share the build configuration behind that figure, that would close the gap."))
story.append(P("ML-DSA on pqm4 is unmeasured, because the KEM path faults before reaching it."))

story.append(PageBreak())
story.append(P("Where the rest stands", H2))
story.append(P("The measurements that were already in place are unchanged:"))
story.append(T([
    ["Handshake, matched operation list", "124.11 ms PQC vs 94.91 ms classical (+30.8%)"],
    ["Where the penalty sits", "sign 60.36 vs 17.57 ms; key establishment 14.61 vs 24.34 ms"],
    ["Harness score, 102 components", "PQC_All 2042.526, zero CRC errors"],
    ["Task 3A, 128 KB firmware", "ECDSA 70.93 ms, HashML-DSA-65 109.79 ms end-to-end"],
    ["Task 3B, 256 B signing", "median 74.77 ms, max 500.57 ms, n=2000"],
], [56 * mm, 100 * mm]))
story.append(Spacer(1, 5))
story.append(P("PQC_All is not an EEMBC score. EEMBC publishes no PQC profile, so those components "
               "report a functional check and a synthesised regression checksum rather than a golden "
               "CRC match. Only the classical suites are EEMBC-comparable.", NOTE))

story.append(P("What's left", H2))
story.append(P("Decapsulation and ML-DSA on pqm4, both blocked on the same two defects. Beyond that "
               "the harness has not been built under Zephyr or ESP-IDF, so everything here is still "
               "single-platform."))

story.append(P("Code and data, branch "
               "<font face='DV-M' size='7.5'>zain_pqc</font>", H2))
story.append(T([
    ["File", "Contents"],
    ["<font face='DV-M' size='7.5'>results/pqm4/main.c</font>, "
     "<font face='DV-M' size='7.5'>CMakeLists.txt</font>",
     "pqm4 bench harness, including the reset-loop sampling mode"],
    ["<font face='DV-M' size='7.5'>results/pqm4/PQM4_O2_SUMMARY.csv</font>",
     "the four-way table above, machine-readable"],
    ["<font face='DV-M' size='7.5'>results/pqm4/pqm4_*_resetloop.txt</font>",
     "raw serial captures, 323 and 321 boots"],
    ["<font face='DV-M' size='7.5'>results/pqm4/README.md</font>",
     "method, the withdrawn figure, the two defects, how to rebuild"],
    ["<font face='DV-M' size='7.5'>results/PQC_LIBRARY_CONFIG_MATRIX.csv</font>",
     "library matrix, pqm4 rows at -O2"],
    ["<font face='DV-M' size='7.5'>results/latex/*.tex</font>", "six tables for the thesis"],
    ["<font face='DV-M' size='7.5'>patches/</font>",
     "<font face='DV-M' size='7.5'>0001-securemark-v2-pqc-components.patch</font>, applies to "
     "<font face='DV-M' size='7.5'>eembc/securemark-v2</font> at "
     "<font face='DV-M' size='7.5'>d21fd8f</font>"],
    ["<font face='DV-M' size='7.5'>REPRODUCE.md</font>", "build, flash and measurement sequence"],
], [68 * mm, 98 * mm]))

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=11 * mm, bottomMargin=10 * mm,
                        title="pqm4 benchmark re-run: ML-KEM-768 on the FRDM-MCXN947",
                        author="Zain Ul Haq")
doc.build(story)
print("wrote", OUT)
