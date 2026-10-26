#!/usr/bin/env python3
"""Generate a model visualisation from models/architectures.py."""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = r"H:\z_thesis\MODEL_FILES"
EXPECTED_PARAMS = 104721          # counted from the checkpoint's layers group

INPUT, CLASSES, STEM = 48, 43, 16
CH = {"A": 32, "B": 40, "C": 176}


def block_params(cin, cout):
    """dw + dwbn + pw + pwbn, exactly as _depthwise_separable_block builds it."""
    return 3 * 3 * cin + 4 * cin + cin * cout + 4 * cout


def head_params(cin):
    return cin * CLASSES + CLASSES


# name, stage, cin, cout, stride, spatial_out
BLOCKS = [
    ("block1",  "A", STEM,    STEM,    1, 24),
    ("block2",  "A", STEM,    CH["A"], 2, 12),
    ("block3",  "A", CH["A"], CH["A"], 1, 12),
    ("block4",  "B", CH["A"], CH["B"], 2, 6),
    ("block5",  "B", CH["B"], CH["B"], 1, 6),
    ("block6",  "B", CH["B"], CH["B"], 1, 6),
    ("block7",  "C", CH["B"], 64,      1, 6),
    ("block8",  "C", 64,      CH["C"], 2, 3),
    ("block9",  "C", CH["C"], CH["C"], 1, 3),
    ("block10", "C", CH["C"], CH["C"], 1, 3),
]
EXITS = [("exit1", 2, CH["A"], 12, "30%"),
         ("exit2", 5, CH["B"], 6,  "60%"),
         ("exit3", 9, CH["C"], 3,  "100%")]

stem_params = 3 * 3 * 3 * STEM + 4 * STEM
backbone = stem_params + sum(block_params(b[2], b[3]) for b in BLOCKS)
heads = sum(head_params(e[2]) for e in EXITS)
total = backbone + heads

if abs(total - EXPECTED_PARAMS) > 0:
    raise SystemExit("param mismatch: computed %d, checkpoint says %d"
                     % (total, EXPECTED_PARAMS))

# ----------------------------------------------------------------- text files
lines = ["Multi-exit GTSRB model - layer summary",
         "Rebuilt from models/architectures.py; total verified against the",
         "checkpoint best_joint.weights.h5 (layers group = %s params)."
         % "{:,}".format(EXPECTED_PARAMS),
         "",
         "Input %dx%dx3 INT8 | %d classes | exits at blocks 3/6/10 = 30/60/100%%"
         % (INPUT, INPUT, CLASSES),
         "",
         "%-5s %-16s %-16s %-6s %10s" % ("#", "layer", "output", "stride", "params"),
         "-" * 58]
row = 1
lines.append("%-5d %-16s %-16s %-6d %10s"
             % (row, "stem_conv", "24x24x%d" % STEM, 2, "{:,}".format(3 * 3 * 3 * STEM)))
row += 1
lines.append("%-5d %-16s %-16s %-6s %10s"
             % (row, "stem_bn", "24x24x%d" % STEM, "-", "{:,}".format(4 * STEM)))
for name, stage, cin, cout, stride, sout in BLOCKS:
    for suffix, c, prm in (("_dw", cin, 3 * 3 * cin), ("_dwbn", cin, 4 * cin),
                           ("_pw", cout, cin * cout), ("_pwbn", cout, 4 * cout)):
        row += 1
        lines.append("%-5d %-16s %-16s %-6d %10s"
                     % (row, name + suffix, "%dx%dx%d" % (sout, sout, c),
                        stride if suffix == "_dw" else 1, "{:,}".format(prm)))
for name, idx, cin, sp, pct in EXITS:
    row += 1
    lines.append("%-5d %-16s %-16s %-6s %10s"
                 % (row, name + "_gap", "%dx%d" % (sp, cin), "-", "0"))
    row += 1
    lines.append("%-5d %-16s %-16s %-6s %10s"
                 % (row, name, str(CLASSES), "-", "{:,}".format(head_params(cin))))
lines += ["-" * 58,
          "backbone:   %s" % "{:,}".format(backbone),
          "exit heads: %s" % "{:,}".format(heads),
          "TOTAL:      %s   (matches the checkpoint exactly)" % "{:,}".format(total),
          "",
          "Device sizes, INT8 per-channel PTQ:",
          "  segA  (exit1, stage A)    16,736 B",
          "  segB  (stage B)           21,168 B",
          "  segC  (stage C)          125,896 B",
          "  full 3-exit model        158,144 B",
          "",
          "Validation accuracy: exit1 0.733 | exit2 0.923 | exit3 0.931 | baseline 0.945"]
open(os.path.join(OUT, "model_summary.txt"), "w", encoding="utf-8").write("\n".join(lines))

with open(os.path.join(OUT, "model_layers.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["index", "layer", "kind", "stage", "channels", "stride",
                "output_shape", "params"])
    i = 1
    w.writerow([i, "stem_conv", "conv", "stem", STEM, 2, "24x24x%d" % STEM, 3 * 3 * 3 * STEM])
    i += 1
    w.writerow([i, "stem_bn", "bn", "stem", STEM, 1, "24x24x%d" % STEM, 4 * STEM])
    for name, stage, cin, cout, stride, sout in BLOCKS:
        for suffix, kind, c, st, prm in (("_dw", "depthwise", cin, stride, 3 * 3 * cin),
                                         ("_dwbn", "bn", cin, 1, 4 * cin),
                                         ("_pw", "pointwise", cout, 1, cin * cout),
                                         ("_pwbn", "bn", cout, 1, 4 * cout)):
            i += 1
            w.writerow([i, name + suffix, kind, stage, c, st,
                        "%dx%dx%d" % (sout, sout, c), prm])
    for name, idx, cin, sp, pct in EXITS:
        i += 1
        w.writerow([i, name + "_gap", "globalavgpool", "-", cin, "-", "%dx%d" % (sp, cin), 0])
        i += 1
        w.writerow([i, name, "dense", "-", CLASSES, "-", str(CLASSES), head_params(cin)])

# --------------------------------------------------------------------- diagram
COL = {"stem": "#5b6b7d", "A": "#2f6fb5", "B": "#1f9d55", "C": "#c9761b"}
fig, ax = plt.subplots(figsize=(13.0, 12.0))
ax.set_xlim(0, 100)
ax.set_ylim(0, 106)
ax.axis("off")

CX, BW, BH, PITCH = 30, 34, 6.0, 7.2
TITLE_Y = 102.5
ax.text(CX, TITLE_Y, "GTSRB multi-exit model", ha="center", fontsize=17, fontweight="bold")
ax.text(CX, TITLE_Y - 2.5,
        "MobileNetV1-flavoured  |  10 depthwise-separable blocks  |  exits at 30% / 60% / 100%",
        ha="center", fontsize=9.2, color="#444")
ax.text(CX, TITLE_Y - 4.6,
        "input 48x48x3  ->  43 classes  |  %s parameters  |  INT8 per-channel PTQ"
        % "{:,}".format(total), ha="center", fontsize=9.2, color="#444")


def draw_box(y, label, sub, sub2, colour):
    ax.add_patch(FancyBboxPatch((CX - BW / 2, y - BH), BW, BH,
                                boxstyle="round,pad=0.3,rounding_size=0.7",
                                linewidth=0.9, edgecolor=colour, facecolor=colour))
    ax.text(CX, y - 2.1, label, ha="center", va="center", fontsize=9.5,
            color="white", fontweight="bold")
    if sub:
        ax.text(CX, y - 3.9, sub, ha="center", va="center", fontsize=7.7, color="#eef2f6")
    if sub2:
        ax.text(CX, y - 5.1, sub2, ha="center", va="center", fontsize=7.0, color="#dbe4ee")


y = 92.0
pos = {}
draw_box(y, "image", "48 x 48 x 3", "", "#33404f")
pos["image"] = y
ax.add_patch(FancyArrowPatch((CX, y - BH), (CX, y - PITCH), arrowstyle="-|>",
                             mutation_scale=9, color="#96a2b0", lw=1.1))
y -= PITCH
draw_box(y, "stem_conv + bn", "24 x 24 x 16   stride 2", "%s params" % "{:,}".format(stem_params),
         COL["stem"])
pos["stem"] = y
prev = "stem"

for name, stage, cin, cout, stride, sin_unused in [(b[0], b[1], b[2], b[3], b[4], b[5]) for b in BLOCKS]:
    y -= PITCH
    draw_box(y, name, "%d x %d x %d%s" % (sin_unused, sin_unused, cout,
                                          "   stride 2" if stride == 2 else ""),
             "%s params" % "{:,}".format(block_params(cin, cout)), COL[stage])
    pos[name] = y
    ax.add_patch(FancyArrowPatch((CX, pos[prev] - BH), (CX, y), arrowstyle="-|>",
                                 mutation_scale=9, color="#96a2b0", lw=1.1))
    prev = name


def bracket(top_y, bot_y, text, colour):
    x = CX - BW / 2 - 5.2
    ax.plot([x, x], [top_y - BH / 2, bot_y - BH / 2], color=colour, lw=2.4)
    ax.text(x - 2.0, (top_y + bot_y) / 2 - BH / 2, text, rotation=90,
            ha="center", va="center", fontsize=10, color=colour, fontweight="bold")


bracket(pos["block1"], pos["block3"], "STAGE A", COL["A"])
bracket(pos["block4"], pos["block6"], "STAGE B", COL["B"])
bracket(pos["block7"], pos["block10"], "STAGE C", COL["C"])

for name, idx, cin, sp, pct in EXITS:
    anchor = BLOCKS[idx][0]
    ya = pos[anchor] - BH / 2
    xe = CX + BW / 2
    xh = 73.0
    ax.add_patch(FancyArrowPatch((xe, ya), (xh - 9.5, ya), arrowstyle="-|>",
                                 mutation_scale=11, color="#b3261e", lw=1.6))
    ax.add_patch(FancyBboxPatch((xh - 9.5, ya - 2.6), 25, 5.2,
                                boxstyle="round,pad=0.3,rounding_size=0.6",
                                linewidth=1.1, edgecolor="#b3261e", facecolor="#fdeceb"))
    ax.text(xh + 3.0, ya + 0.95, "%s   GAP -> Dense(%d)" % (name, CLASSES),
            ha="center", va="center", fontsize=8.7, color="#7f1d1d", fontweight="bold")
    ax.text(xh + 3.0, ya - 1.35, "%d x %d -> logits   %s params"
            % (sp, sp, "{:,}".format(head_params(cin))),
            ha="center", va="center", fontsize=7.4, color="#8a4b48")
    ax.text(xe + 1.5, ya + 1.9, pct, fontsize=7.7, color="#b3261e", fontweight="bold")

ax.text(50, 3.0,
        "Every operator is on the eIQ Neutron NPU whitelist: Conv2D (standard / depthwise / pointwise), ReLU6, MaxPool,\n"
        "GlobalAvgPool, FullyConnected, Add, BatchNorm. BatchNorm folds into the preceding convolution at TFLite conversion.\n"
        "Exit heads emit raw logits; softmax and tau thresholding run CPU-side after NPU dispatch.",
        ha="center", va="center", fontsize=7.9, color="#4a5560")

plt.tight_layout()
png = os.path.join(OUT, "model_architecture.png")
plt.savefig(png, dpi=150, bbox_inches="tight", facecolor="white")
plt.close()

print("TOTAL params %s  (checkpoint agrees)" % "{:,}".format(total))
print("wrote", png)
print("wrote", os.path.join(OUT, "model_summary.txt"))
print("wrote", os.path.join(OUT, "model_layers.csv"))
