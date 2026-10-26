#!/usr/bin/env python3
"""Build TRAINING_EVIDENCE.pdf from the saved training artifacts."""
import csv
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

TRAIN = r"H:\z_thesis\codebase\training_archive\training"
OUT = r"H:\z_thesis\TRAINING_EVIDENCE.pdf"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=17, spaceAfter=8,
                    textColor=colors.HexColor("#12263a"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12.5, spaceBefore=12,
                    spaceAfter=5, textColor=colors.HexColor("#1f4e79"))
BODY = ParagraphStyle("BODY", parent=ss["BodyText"], fontSize=9.6, leading=13.4,
                      alignment=TA_LEFT, spaceAfter=5)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.4, leading=11.4,
                       textColor=colors.HexColor("#444444"))
CODE = ParagraphStyle("CODE", parent=BODY, fontName="Courier", fontSize=8.2,
                      leading=10.6, backColor=colors.HexColor("#f4f4f4"),
                      borderPadding=5, spaceBefore=3, spaceAfter=6)
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.3, leading=11, spaceAfter=0)


def p(t, s=BODY):
    return Paragraph(t, s)


def table(data, widths, header=True, small=False):
    st = ParagraphStyle("c", parent=CELL, fontSize=8.0 if small else 8.4)
    rows = [[Paragraph(str(c), st) for c in r] for r in data]
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def img(path, max_w):
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    scale = max_w / w
    return Image(path, width=max_w, height=h * scale)


# ---- read the real numbers -------------------------------------------------
def col(tag, key):
    rows = list(csv.DictReader(open(os.path.join(TRAIN, "results", "logs", tag, "history.csv"))))
    return [float(r[key]) for r in rows]


me = {k: col("multiexit", k) for k in
      ("val_exit1_acc", "val_exit2_acc", "val_exit3_acc", "val_loss")}
bl_acc = col("baseline", "val_acc")
bl_loss = col("baseline", "val_loss")
mins = [min(me["val_exit1_acc"][i], me["val_exit2_acc"][i], me["val_exit3_acc"][i])
        for i in range(len(me["val_loss"]))]

story = []
story.append(p("Model training - evidence pack", H1))
story.append(p("Certified anytime perception under post-quantum cryptographic load"
               "<br/>Generated %s from the saved training artifacts." % date.today().isoformat(), SMALL))
story.append(Spacer(1, 6))

# ---- 0. scope -------------------------------------------------------------
story.append(p("0. Scope: what is trained and what is not", H2))
story.append(p("One component was trained with gradient descent; the rest are a statistical fit, "
               "a simulator over measured costs, or measurements. Stating this precisely is part "
               "of the result."))
story.append(table([
    ["Component", "What it actually is", "Gradient-trained?"],
    ["Multi-exit perception model", "3-exit MobileNetV1, Keras, 100 epochs", "<b>Yes</b> - train/train.py"],
    ["Baseline control model", "Same backbone, single final exit", "<b>Yes</b> - train/train.py"],
    ["Learned exit policy (conformal)", "Isotonic / PAVA risk curves fitted on the calibration split",
     "No - statistical fit"],
    ["Joint PQC + exit scheduler", "Trace-driven simulator over measured costs", "No"],
    ["ML-DSA latency tails", "Measured distributions, 2000 runs per level", "No"],
], [46 * mm, 78 * mm, 44 * mm]))
story.append(Spacer(1, 5))
story.append(p("<b>There is no jointly-trained PQC + perception neural network.</b> Only two scripts "
               "in the tree perform gradient training (train.py, quantize.py), and both train the "
               "perception model. The layer that decides which security level and which exit to use "
               "is analytical: a simulator driven by real measured costs, which is the stronger "
               "choice when every cost in it is a measurement rather than a learned proxy.", BODY))

# ---- 1. model -------------------------------------------------------------
story.append(p("1. The trained model", H2))
story.append(table([
    ["Property", "Value"],
    ["Input", "48 x 48 x 3, INT8-quantised"],
    ["Classes", "43 (GTSRB)"],
    ["Depth", "10 depthwise-separable blocks in 3 stages"],
    ["Exit placement", "<b>exactly 30% / 60% / 100%</b> of block depth (blocks 3, 6, 10)"],
    ["Stage widths", "stem 16 -&gt; A 32 -&gt; B 40 -&gt; C 176"],
    ["Operators", "Conv2D (std / depthwise / pointwise), ReLU6, MaxPool, GlobalAvgPool, FC, Add, BatchNorm"],
    ["Excluded", "SE blocks, attention, swish, in-graph softmax"],
    ["Exit heads", "raw logits; softmax + tau thresholding applied CPU-side after NPU dispatch"],
], [34 * mm, 134 * mm]))
story.append(Spacer(1, 5))
story.append(p("<b>Capacity is deliberately unequal across exits.</b> Stage B was narrowed from 64 to "
               "40 channels and stage C widened from 128 to 176 <i>because</i> at 64 channels exits 2 "
               "and 3 converged to within about 1 percentage point by epoch 15 and stayed there - the "
               "exit-collapse failure mode, for the exit2/exit3 pair. Head placement is exact rather "
               "than approximate: blocks 3, 6 and 10 of 10 give 30 / 60 / 100%.", BODY))

# ---- 2. config ------------------------------------------------------------
story.append(PageBreak())
story.append(p("1b. Architecture", H2))
_arch = r"H:\z_thesis\MODEL_FILES\model_architecture.png"
if os.path.exists(_arch):
    story.append(img(_arch, 168 * mm))
    story.append(p("One box per depthwise-separable block. Each block is "
                   "depthwise conv + BatchNorm + pointwise conv + BatchNorm. "
                   "Exits tap the trunk after blocks 3, 6 and 10 (30% / 60% / 100%). "
                   "Total 104,721 parameters, verified against the checkpoint.", SMALL))
else:
    story.append(p("(architecture diagram not found)", SMALL))
story.append(PageBreak())
story.append(p("2. Training configuration", H2))
story.append(p("train/configs/multiexit.yaml", CODE))
story.append(p("seed: 20260728<br/>model: multiexit<br/>batch_size: 128<br/>epochs: 100<br/>"
               "learning_rate: 0.001<br/>val_track_fraction: 0.1<br/>"
               "exit_loss_weights: {exit1: 1.0, exit2: 1.0, exit3: 1.0}", CODE))
story.append(p("<b>Loss.</b> BranchyNet joint loss, L = sum_k w_k * CE(exit_k), equal weights w_k = 1.0. "
               "Equal weighting follows the brief; per-exit weighting is the documented lever if the "
               "accuracy spread needs rebalancing.", BODY))
story.append(p("<b>Validation split.</b> Track-aware and taken from the training set only. GTSRB frames "
               "are named &lt;trackID&gt;_&lt;frameID&gt;.ppm with roughly 30 near-duplicate frames per physical "
               "sign, so a random split would leak the same sign into train and validation. "
               "val_track_fraction 0.1 holds out whole tracks. Calibration and test splits are untouched "
               "by training.", BODY))
story.append(p("<b>Baseline control.</b> train/configs/baseline.yaml: identical backbone, single final "
               "exit, single cross-entropy. Used to measure what joint multi-exit training costs the "
               "final classifier.", BODY))

story.append(PageBreak())

# ---- 3. curves ------------------------------------------------------------
story.append(p("3. Training curves", H2))
story.append(p("Source: results/logs/{multiexit,baseline}/history.csv, one row per epoch. "
               "Regenerate with <font face='Courier'>python make_plots.py</font>.", SMALL))
for fn, cap in (("multiexit_accuracy_curves.png",
                 "Per-exit training and validation accuracy."),
                ("multiexit_loss_curves.png",
                 "Per-exit training and validation loss."),
                ("multiexit_vs_baseline.png",
                 "Multi-exit joint training vs the single-exit baseline control.")):
    story.append(Spacer(1, 4))
    story.append(img(os.path.join(TRAIN, "results", "plots", fn), 168 * mm))
    story.append(p(cap, SMALL))

story.append(PageBreak())

# ---- 4. numbers -----------------------------------------------------------
story.append(p("4. Key numbers", H2))
story.append(p("Read from the history files at build time.", SMALL))
story.append(table([
    ["Metric", "Epoch 0", "Final (100)", "Best", "Best epoch"],
    ["val exit1 accuracy", "%.3f" % me["val_exit1_acc"][0], "%.3f" % me["val_exit1_acc"][-1],
     "<b>%.3f</b>" % max(me["val_exit1_acc"]), str(me["val_exit1_acc"].index(max(me["val_exit1_acc"])))],
    ["val exit2 accuracy", "%.3f" % me["val_exit2_acc"][0], "%.3f" % me["val_exit2_acc"][-1],
     "<b>%.3f</b>" % max(me["val_exit2_acc"]), str(me["val_exit2_acc"].index(max(me["val_exit2_acc"])))],
    ["val exit3 accuracy", "%.3f" % me["val_exit3_acc"][0], "%.3f" % me["val_exit3_acc"][-1],
     "<b>%.3f</b>" % max(me["val_exit3_acc"]), str(me["val_exit3_acc"].index(max(me["val_exit3_acc"])))],
    ["val loss (summed over exits)", "%.3f" % me["val_loss"][0], "%.3f" % me["val_loss"][-1],
     "<b>%.3f</b>" % min(me["val_loss"]), str(me["val_loss"].index(min(me["val_loss"])))],
], [52 * mm, 24 * mm, 26 * mm, 24 * mm, 24 * mm]))
story.append(Spacer(1, 4))
story.append(table([
    ["Baseline control", "Epoch 0", "Final (100)", "Best", "Best epoch"],
    ["val accuracy", "%.3f" % bl_acc[0], "%.3f" % bl_acc[-1], "<b>%.3f</b>" % max(bl_acc),
     str(bl_acc.index(max(bl_acc)))],
    ["val loss", "%.3f" % bl_loss[0], "%.3f" % bl_loss[-1], "<b>%.3f</b>" % min(bl_loss),
     str(bl_loss.index(min(bl_loss)))],
], [52 * mm, 24 * mm, 26 * mm, 24 * mm, 24 * mm]))

story.append(p("What the curves show", H2))
story.append(p("<b>1. All three exits learn and stay ordered:</b> exit3 (%.3f) &gt; exit2 (%.3f) &gt; "
               "exit1 (%.3f). The ordering is what makes the anytime behaviour meaningful - if the exits "
               "collapsed together there would be nothing to trade off."
               % (max(me["val_exit3_acc"]), max(me["val_exit2_acc"]), max(me["val_exit1_acc"])), BODY))
story.append(p("<b>2. The spread is wide and stable</b> - about %.0f points between exit1 and exit3. "
               "That is the deliberate capacity handicap working."
               % (100 * (max(me["val_exit3_acc"]) - max(me["val_exit1_acc"]))), BODY))
story.append(p("<b>3. Joint multi-exit training costs the final exit about %.1f points</b> (%.3f vs "
               "%.3f for the baseline). That is the price of the anytime property, and it is the number "
               "to quote when asked whether early exits are free."
               % (100 * (max(bl_acc) - max(me["val_exit3_acc"])), max(me["val_exit3_acc"]), max(bl_acc)), BODY))
story.append(p("<b>4. Both runs peak near epoch 94-96</b> and drift slightly afterwards; training to 100 "
               "epochs is past the optimum.", BODY))

story.append(p("Checkpoint selection", H2))
story.append(p("best_joint.weights.h5 is chosen by a MaxOfMinCheckpoint callback that maximises "
               "min(val_exit1_acc, val_exit2_acc, val_exit3_acc) - it protects the weakest exit rather "
               "than the average. On this run that lands at <b>epoch %d</b> (min-of-exits = %.3f, set by "
               "exit1)." % (mins.index(max(mins)), max(mins)), BODY))
story.append(p("Available: best.weights.h5, best_exit3_epoch71.weights.h5, "
               "best_exit3_frozen_epoch_NA.weights.h5, best_joint.weights.h5, final.weights.h5.", SMALL))

story.append(PageBreak())

# ---- 5. pipeline ----------------------------------------------------------
story.append(p("5. From trained weights to device segments", H2))
story.append(table([
    ["Step", "Script", "Output"],
    ["Train", "train/train.py", "results/checkpoints/multiexit/*.weights.h5"],
    ["Quantise (INT8 per-channel PTQ)", "train/quantize.py", "results/tflite/exit{1,2,3}_int8.tflite"],
    ["Split into standalone per-exit segments", "-", "results/segments/seg{A,B,C}_int8.tflite"],
    ["Quantisation accuracy check", "-", "results/quantize_accuracy_report.csv"],
], [52 * mm, 40 * mm, 76 * mm]))
story.append(Spacer(1, 4))
story.append(p("Segment sizes: segA 16,736 B, segB 21,168 B, segC 125,896 B. All three share one trained "
               "graph; they are separate .tflite files so each can run standalone on device.", BODY))

# ---- 6. not trained -------------------------------------------------------
story.append(p("6. Components that are not gradient-trained", H2))
story.append(p("<b>Learned exit policy.</b> conformal/learned_exit_policy.py fits isotonic (PAVA, "
               "decreasing) risk curves risk_k(c) = P(safety-critical AND wrong | conf_k = c) on the "
               "calibration split only, then selects the shallowest exit whose risk is under the target "
               "alpha. It is a monotone curve fit with a guarantee argument, not a trained network. "
               "Output: results/learned_policy/risk_curves.json.", BODY))
story.append(p("<b>Joint scheduler.</b> conformal/joint_scheduler.py is a trace-driven simulator. State "
               "per frame: conf1, conf2, cryptoImminent, budgetUsed. Decision per frame: which exit. "
               "Decision per handshake: which ML-KEM level (512 / 768 / 1024). All costs are measured:", BODY))
story.append(p("exit1 = 0.80 ms, exit2 = 1.24 ms, exit3 = 2.34 ms      (MCXN947, on device)<br/>"
               "ML-KEM handshake: 512 = 72.17 ms, 768 = 115.97 ms, 1024 = 174.91 ms", CODE))
story.append(p("<b>Correction to apply before quoting the scheduler.</b> Those ML-KEM figures are the "
               "bare-metal PQClean numbers. The later -O2 wolfSSL harness measured the same ML-KEM-768 "
               "handshake at <b>21.62 ms</b> - 5.4x faster. The scheduler's \"infeasible at level 768\" "
               "conclusion flips to feasible at the real cost, so the report should be re-run against "
               "the faster numbers before it is presented.", BODY))
story.append(p("<b>Conformal certification itself</b> is not learned: it is the split-conformal quantile "
               "calculation over the calibration split, reported in results/conformal_tau_table.csv and "
               "results/coverage_validation_table.csv.", BODY))

# ---- 7. files -------------------------------------------------------------
story.append(p("7. Files", H2))
story.append(table([
    ["Purpose", "Path"],
    ["Raw per-epoch history", "training/results/logs/multiexit/history.csv"],
    ["Baseline history", "training/results/logs/baseline/history.csv"],
    ["Config", "training/train/configs/multiexit.yaml"],
    ["Model definition", "training/models/architectures.py"],
    ["Checkpoints", "training/results/checkpoints/multiexit/"],
    ["Certification results", "training/results/conformal_tau_table.csv"],
    ["Plot regeneration", "python make_plots.py (in training/)"],
], [40 * mm, 128 * mm]))

doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=20 * mm, rightMargin=20 * mm,
                        topMargin=16 * mm, bottomMargin=16 * mm,
                        title="Model training - evidence pack",
                        author="Zain Ul Haq")
doc.build(story)
print("wrote", OUT)
print("pages:", len(story), "flowables")
