"""
Builds a toy multi-exit-style CNN (3 conv blocks: A, B, C) and exports it as:
  - monolithic.tflite   (A -> B -> C, single graph)
  - seg_AB.tflite       (A -> B, for the 2-segment split's first piece)
  - seg_A.tflite        (A alone, for the 3-segment split's first piece)
  - seg_B.tflite        (B alone, for the 3-segment split's second piece)
  - seg_C.tflite        (C alone, shared by both the 2-seg split's second piece
                          and the 3-seg split's third piece -- same input shape
                          in both cases since it always follows B's output)

All layers are INT8 per-channel quantized via TFLite's full-integer PTQ.
Weights are randomly initialized with a fixed seed -- this experiment measures
NPU dispatch/segmentation latency, not classification accuracy, so untrained
weights are fine as long as the op graph and tensor shapes are realistic.

Each exported graph is built directly from the SAME underlying tf.keras.layers
objects (reused across graphs, not nested Model-in-Model) so weights are
bit-identical across monolithic/segmented exports at every shared layer.

Input: 32x32x3 (matches the cifarnet example's image size for comparability).
Block A: Conv2D(8, 3x3, same) -> ReLU6 -> MaxPool(2x2)   : 32x32x3 -> 16x16x8
Block B: Conv2D(16, 3x3, same) -> ReLU6 -> MaxPool(2x2)  : 16x16x8 -> 8x8x16
Block C: Conv2D(32, 3x3, same) -> ReLU6 -> GlobalAvgPool -> FC(10) : 8x8x16 -> 10
"""
import os
import numpy as np
import tensorflow as tf

SEED = 1234
np.random.seed(SEED)
tf.random.set_seed(SEED)

OUT_DIR = "H:/z_thesis/codebase/projects/npu_segments/tools/generated"
os.makedirs(OUT_DIR, exist_ok=True)

INPUT_SHAPE = (32, 32, 3)
N_CALIB = 100

init = tf.keras.initializers.GlorotUniform(seed=SEED)

# ---- Shared layer objects (built once, reused across every exported graph) ----
conv_a = tf.keras.layers.Conv2D(8, 3, padding="same", kernel_initializer=init, name="a_conv")
relu_a = tf.keras.layers.ReLU(max_value=6.0, name="a_relu6")
pool_a = tf.keras.layers.MaxPool2D(2, name="a_pool")

conv_b = tf.keras.layers.Conv2D(16, 3, padding="same", kernel_initializer=init, name="b_conv")
relu_b = tf.keras.layers.ReLU(max_value=6.0, name="b_relu6")
pool_b = tf.keras.layers.MaxPool2D(2, name="b_pool")

conv_c = tf.keras.layers.Conv2D(32, 3, padding="same", kernel_initializer=init, name="c_conv")
relu_c = tf.keras.layers.ReLU(max_value=6.0, name="c_relu6")
gap_c = tf.keras.layers.GlobalAveragePooling2D(name="c_gap")
fc_c = tf.keras.layers.Dense(10, kernel_initializer=init, name="c_fc")


def block_a_fn(x):
    return pool_a(relu_a(conv_a(x)))


def block_b_fn(x):
    return pool_b(relu_b(conv_b(x)))


def block_c_fn(x):
    return fc_c(gap_c(relu_c(conv_c(x))))


# ---- Build every graph up front so all shared layers get built (weights created) ----
full_input = tf.keras.Input(shape=INPUT_SHAPE, name="full_input")
a_out = block_a_fn(full_input)
b_out = block_b_fn(a_out)
c_out = block_c_fn(b_out)

model_monolithic = tf.keras.Model(full_input, c_out, name="monolithic")
model_seg_AB = tf.keras.Model(full_input, b_out, name="seg_AB")
model_seg_A = tf.keras.Model(full_input, a_out, name="seg_A")

a_out_shape = model_seg_A.output_shape[1:]        # (16, 16, 8)
b_out_shape = model_seg_AB.output_shape[1:]       # (8, 8, 16)

b_input = tf.keras.Input(shape=a_out_shape, name="b_input")
model_seg_B = tf.keras.Model(b_input, block_b_fn(b_input), name="seg_B")

c_input = tf.keras.Input(shape=b_out_shape, name="c_input")
model_seg_C = tf.keras.Model(c_input, block_c_fn(c_input), name="seg_C")

print("Block A output shape:", a_out_shape, "->", int(np.prod(a_out_shape)), "elements")
print("Block B output shape:", b_out_shape, "->", int(np.prod(b_out_shape)), "elements")

# ---- Representative datasets ----
rng = np.random.default_rng(SEED)
calib_images = rng.uniform(0.0, 1.0, size=(N_CALIB,) + INPUT_SHAPE).astype(np.float32)

calib_a_out = model_seg_A.predict(calib_images, verbose=0)     # input to block B / seg B
calib_ab_out = model_seg_AB.predict(calib_images, verbose=0)   # input to block C / seg C


def rep_dataset(data):
    def gen():
        for i in range(data.shape[0]):
            yield [data[i:i + 1]]
    return gen


def quantize_and_save(keras_model, rep_data, out_name):
    converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = rep_dataset(rep_data)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    tflite_model = converter.convert()
    out_path = os.path.join(OUT_DIR, out_name)
    with open(out_path, "wb") as f:
        f.write(tflite_model)
    print(f"wrote {out_path} ({len(tflite_model)} bytes)")
    return out_path


quantize_and_save(model_monolithic, calib_images, "monolithic.tflite")
quantize_and_save(model_seg_AB, calib_images, "seg_AB.tflite")
quantize_and_save(model_seg_A, calib_images, "seg_A.tflite")
quantize_and_save(model_seg_B, calib_a_out, "seg_B.tflite")
quantize_and_save(model_seg_C, calib_ab_out, "seg_C.tflite")

print("\nDone. Intermediate activation footprint (INT8, 1 byte/element):")
print(f"  after A (3-seg boundary 1): {int(np.prod(a_out_shape))} bytes")
print(f"  after B (2-seg boundary / 3-seg boundary 2): {int(np.prod(b_out_shape))} bytes")
