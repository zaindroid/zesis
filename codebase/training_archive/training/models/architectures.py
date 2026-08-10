"""
Multi-exit MobileNetV1-flavored backbone for GTSRB, targeting the eIQ
Neutron NPU op whitelist:
  Conv2D standard/depthwise/pointwise, ReLU6, MaxPool/GlobalAvgPool,
  FullyConnected, Add, BatchNorm.
No SE-blocks, no attention, no swish, no softmax inside the graph (exit
heads emit raw logits; softmax + tau thresholding happen CPU-side after
NPU dispatch -- see conformal/ and the deploy/ firmware wrapper).

10 depthwise-separable blocks in 3 stages, exits placed at EXACTLY 30%,
60%, 100% of block-depth (blocks 3, 6, 10) so "~30%/~60%/100%" from the
brief is not just approximate. Channel width increases per stage
(16->32->64->96->128) so the early exit sees deliberately weaker/narrower
features than the final exit -- without this handicap, GTSRB is easy
enough that all three exits tend to collapse to near-identical accuracy
(see the brief: "if exits collapse to equal acc, backbone too big ->
shrink"). If training shows collapse anyway, thin CHANNELS below (module-
level constants), not the exit placement -- exit placement is fixed by the
30/60/100 spec above.

Every layer here is on the NPU whitelist. BatchNorm layers fold into the
preceding Conv at TFLite-conversion time (standard TFLite behavior); kept
as separate layers during training/PTQ representative-dataset calibration.
"""
from __future__ import annotations

import tensorflow as tf
from tensorflow.keras import layers, Model

INPUT_SIZE = 48
NUM_CLASSES = 43

# Per-stage output channel widths. Stage A (blocks 1-3, exit1 @ block3),
# Stage B (blocks 4-6, exit2 @ block6), Stage C (blocks 7-10, exit3 @ block10).
STEM_CHANNELS = 16
STAGE_CHANNELS = {
    "A": 32,   # blocks 1-3 ramp 16 -> 32
    "B": 40,   # blocks 4-6 ramp 32 -> 40 (narrowed from 64: at 64ch, exit2 was
               # nearly saturating GTSRB accuracy on its own -- exit2 and exit3
               # converged to within ~1pp of each other by epoch ~15/60 and
               # stayed there, i.e. the "exits collapse" failure mode the brief
               # warns about, just for the exit2/exit3 pair rather than all
               # three. Narrowing B's bottleneck forces exit2 to work with
               # genuinely less capacity.
    "C": 176,  # blocks 7-10 ramp 40 -> 176 (widened from 128, via an
               # intermediate 64 at block7) -- widens the capacity gap on the
               # other side so exit3 has real headroom above exit2.
}


def _conv_bn_relu6(x, filters, kernel_size, strides, name):
    """Standard (non-separable) Conv2D -- used only for the stem."""
    x = layers.Conv2D(filters, kernel_size, strides=strides, padding="same",
                       use_bias=False, name=f"{name}_conv")(x)
    x = layers.BatchNormalization(name=f"{name}_bn")(x)
    x = layers.ReLU(max_value=6.0, name=f"{name}_relu6")(x)
    return x


def _depthwise_separable_block(x, out_channels, strides, name):
    """DW 3x3 -> BN -> ReLU6 -> PW 1x1 -> BN -> ReLU6. The MobileNetV1 unit."""
    x = layers.DepthwiseConv2D(3, strides=strides, padding="same",
                                use_bias=False, name=f"{name}_dw")(x)
    x = layers.BatchNormalization(name=f"{name}_dwbn")(x)
    x = layers.ReLU(max_value=6.0, name=f"{name}_dwrelu6")(x)
    x = layers.Conv2D(out_channels, 1, strides=1, padding="same",
                       use_bias=False, name=f"{name}_pw")(x)
    x = layers.BatchNormalization(name=f"{name}_pwbn")(x)
    x = layers.ReLU(max_value=6.0, name=f"{name}_pwrelu6")(x)
    return x


def _exit_head(x, name):
    """GlobalAvgPool -> FC(NUM_CLASSES). Raw logits, no softmax in-graph."""
    x = layers.GlobalAveragePooling2D(name=f"{name}_gap")(x)
    logits = layers.Dense(NUM_CLASSES, name=name)(x)
    return logits


def build_backbone(inputs):
    """Returns (exit1_features, exit2_features, exit3_features) feature maps
    at block3/block6/block10, before any GAP/FC -- shared by both the
    multi-exit model and the single-output baseline."""
    x = _conv_bn_relu6(inputs, STEM_CHANNELS, 3, strides=2, name="stem")  # 48->24

    # Stage A: blocks 1-3, exit1 @ block3 (30% depth)
    x = _depthwise_separable_block(x, STEM_CHANNELS, strides=1, name="block1")       # 24x24x16
    x = _depthwise_separable_block(x, STAGE_CHANNELS["A"], strides=2, name="block2")  # 24->12, 12x12x32
    x = _depthwise_separable_block(x, STAGE_CHANNELS["A"], strides=1, name="block3")  # 12x12x32
    exit1_features = x

    # Stage B: blocks 4-6, exit2 @ block6 (60% depth)
    x = _depthwise_separable_block(x, STAGE_CHANNELS["B"], strides=2, name="block4")  # 12->6, 6x6x40
    x = _depthwise_separable_block(x, STAGE_CHANNELS["B"], strides=1, name="block5")  # 6x6x40
    x = _depthwise_separable_block(x, STAGE_CHANNELS["B"], strides=1, name="block6")  # 6x6x40
    exit2_features = x

    # Stage C: blocks 7-10, exit3 @ block10 (100% depth)
    x = _depthwise_separable_block(x, 64, strides=1, name="block7")                   # 6x6x64
    x = _depthwise_separable_block(x, STAGE_CHANNELS["C"], strides=2, name="block8")  # 6->3, 3x3x176
    x = _depthwise_separable_block(x, STAGE_CHANNELS["C"], strides=1, name="block9")  # 3x3x176
    x = _depthwise_separable_block(x, STAGE_CHANNELS["C"], strides=1, name="block10")  # 3x3x176
    exit3_features = x

    return exit1_features, exit2_features, exit3_features


def build_multi_exit_model(name: str = "gtsrb_multiexit") -> Model:
    """3 named outputs: exit1, exit2, exit3 (raw logits, sparse-CE-ready)."""
    inputs = layers.Input(shape=(INPUT_SIZE, INPUT_SIZE, 3), name="image")
    f1, f2, f3 = build_backbone(inputs)
    exit1 = _exit_head(f1, "exit1")
    exit2 = _exit_head(f2, "exit2")
    exit3 = _exit_head(f3, "exit3")
    return Model(inputs=inputs, outputs={"exit1": exit1, "exit2": exit2, "exit3": exit3}, name=name)


def build_baseline_model(name: str = "gtsrb_baseline_noexit") -> Model:
    """Same backbone, single final-exit output only -- control model to
    measure whether joint multi-exit training costs final-layer accuracy."""
    inputs = layers.Input(shape=(INPUT_SIZE, INPUT_SIZE, 3), name="image")
    _, _, f3 = build_backbone(inputs)
    logits = _exit_head(f3, "logits")
    return Model(inputs=inputs, outputs=logits, name=name)


def count_params_by_component(model: Model) -> dict[str, int]:
    """Rough param breakdown: backbone (shared trunk) vs each exit head, by
    layer-name prefix. Useful for the params report without needing to
    manually re-derive it from model.summary()."""
    counts: dict[str, int] = {"backbone": 0}
    for layer in model.layers:
        n = layer.count_params()
        if n == 0:
            continue
        if layer.name.startswith("exit1") :
            counts["exit1_head"] = counts.get("exit1_head", 0) + n
        elif layer.name.startswith("exit2"):
            counts["exit2_head"] = counts.get("exit2_head", 0) + n
        elif layer.name.startswith("exit3") or layer.name == "logits":
            counts["exit3_head_or_logits"] = counts.get("exit3_head_or_logits", 0) + n
        else:
            counts["backbone"] += n
    counts["total"] = sum(v for k, v in counts.items() if k != "total")
    return counts


if __name__ == "__main__":
    me_model = build_multi_exit_model()
    me_model.summary()
    print("\nParam breakdown (multi-exit):")
    for k, v in count_params_by_component(me_model).items():
        print(f"  {k}: {v:,}")

    baseline_model = build_baseline_model()
    print(f"\nBaseline total params: {baseline_model.count_params():,}")
