"""
Extends the toy 3-block CNN to a 4-segment split by splitting block C into
two pieces at its internal Conv/GAP+FC boundary:
  A: 32x32x3 -> 16x16x8   (Conv+ReLU6+Pool)
  B: 16x16x8 -> 8x8x16    (Conv+ReLU6+Pool)
  C1: 8x8x16 -> 8x8x32    (Conv+ReLU6)
  C2: 8x8x32 -> 10        (GlobalAvgPool+FC)

Reuses the SAME conv_a/conv_b/conv_c/fc_c layer objects (with the same fixed
seed) as build_toy_model.py so weights are identical to the 1/2/3-segment
models already measured -- only the C2/C1 boundary is new.

Produces (in tools/generated/):
  seg_A.tflite   (already exists from build_toy_model.py, re-emitted here for
                  self-containedness -- byte-identical since same seed/layers)
  seg_B.tflite   (same)
  seg_C1.tflite  (new: Conv2D(32,3x3)+ReLU6 only, no GAP/FC)
  seg_C2.tflite  (new: GlobalAvgPool+FC only, input 8x8x32)
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

# ---- Same shared layer objects/order as build_toy_model.py, so weights match ----
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


def block_c1_fn(x):
    return relu_c(conv_c(x))


def block_c2_fn(x):
    return fc_c(gap_c(x))


# ---- Build the full graph once so shared layers get built with identical weights ----
full_input = tf.keras.Input(shape=INPUT_SHAPE, name="full_input")
a_out = block_a_fn(full_input)
b_out = block_b_fn(a_out)
c1_out = block_c1_fn(b_out)
c2_out = block_c2_fn(c1_out)

model_seg_A = tf.keras.Model(full_input, a_out, name="seg_A_4")
a_out_shape = model_seg_A.output_shape[1:]           # (16, 16, 8)

model_seg_AB = tf.keras.Model(full_input, b_out, name="seg_AB_4")
b_out_shape = model_seg_AB.output_shape[1:]          # (8, 8, 16)

model_seg_ABC1 = tf.keras.Model(full_input, c1_out, name="seg_ABC1_4")
c1_out_shape = model_seg_ABC1.output_shape[1:]       # (8, 8, 32)

b_input = tf.keras.Input(shape=a_out_shape, name="b_input_4")
model_seg_B = tf.keras.Model(b_input, block_b_fn(b_input), name="seg_B_4")

c1_input = tf.keras.Input(shape=b_out_shape, name="c1_input_4")
model_seg_C1 = tf.keras.Model(c1_input, block_c1_fn(c1_input), name="seg_C1_4")

c2_input = tf.keras.Input(shape=c1_out_shape, name="c2_input_4")
model_seg_C2 = tf.keras.Model(c2_input, block_c2_fn(c2_input), name="seg_C2_4")

print("Block A  output shape:", a_out_shape, "->", int(np.prod(a_out_shape)), "elements")
print("Block B  output shape:", b_out_shape, "->", int(np.prod(b_out_shape)), "elements")
print("Block C1 output shape:", c1_out_shape, "->", int(np.prod(c1_out_shape)), "elements")

# ---- Representative datasets ----
rng = np.random.default_rng(SEED)
calib_images = rng.uniform(0.0, 1.0, size=(N_CALIB,) + INPUT_SHAPE).astype(np.float32)

calib_a_out = model_seg_A.predict(calib_images, verbose=0)
calib_ab_out = model_seg_AB.predict(calib_images, verbose=0)
calib_abc1_out = model_seg_ABC1.predict(calib_images, verbose=0)


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


quantize_and_save(model_seg_A, calib_images, "seg_A4.tflite")
quantize_and_save(model_seg_B, calib_a_out, "seg_B4.tflite")
quantize_and_save(model_seg_C1, calib_ab_out, "seg_C14.tflite")
quantize_and_save(model_seg_C2, calib_abc1_out, "seg_C24.tflite")

print("\nDone. Intermediate activation footprint (INT8, 1 byte/element) for the 4-seg chain:")
print(f"  after A  (boundary 1): {int(np.prod(a_out_shape))} bytes")
print(f"  after B  (boundary 2): {int(np.prod(b_out_shape))} bytes")
print(f"  after C1 (boundary 3): {int(np.prod(c1_out_shape))} bytes")
