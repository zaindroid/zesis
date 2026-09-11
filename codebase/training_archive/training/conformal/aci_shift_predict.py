#!/usr/bin/env python3
"""Stage 1 (TTCA) — generate per-exit predictions over a 1000-frame navigation
sequence with an abrupt distribution shift at frame 300.

Frames 0-299:  clean GTSRB test images (frozen official test set, in order)
Frames 300-999: brightness x0.4 + Gaussian noise (sigma=25/255) — simulated
                tunnel/glare degradation.

Runs the deployed INT8 per-exit tflite models (same as predict_split.py) and
writes: aci_seq_1000.csv  [frame,label,is_sc,conf1,correct1,conf2,correct2,conf3,correct3]
"""
import csv
import numpy as np
import tensorflow as tf
from PIL import Image

ROOT = "/home/zulhaq/z_thesis/training"
TEST_CSV = f"{ROOT}/data/splits/test.csv"
TFLITE = f"{ROOT}/results/tflite"
OUT = f"{ROOT}/results/ttca"

TARGET_SIZE = 48
INPUT_MEAN = 127.5
INPUT_STD = 127.5
SAFETY_CRITICAL = {
    0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16,
    11, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
}
N_FRAMES = 1000
SHIFT_AT = 300
BRIGHTNESS = 0.4          # x0.4 = -60%
NOISE_SIGMA = 25.0        # /255 units


def load_normalize(path, roi, shifted):
    with Image.open(path) as img:
        img = img.convert("RGB")
        if roi is not None:
            img = img.crop(roi)
        img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.float32)
    if shifted:
        arr = arr * BRIGHTNESS
        arr = arr + np.random.normal(0.0, NOISE_SIGMA, arr.shape)
        arr = np.clip(arr, 0.0, 255.0)
    return (arr - INPUT_MEAN) / INPUT_STD


def dump_calib():
    """Run the calibration split (frozen protocol) through the per-exit
    models and save calib_softmax.npy + labels for the tau(alpha) curve."""
    import os
    os.makedirs(OUT, exist_ok=True)
    cal_csv = f"{ROOT}/data/splits/calibration.csv"
    with open(cal_csv, newline="") as f:
        rows = list(csv.DictReader(f))
    inters = {}
    for exit_name in ["exit1", "exit2", "exit3"]:
        it = tf.lite.Interpreter(model_path=f"{TFLITE}/{exit_name}_int8.tflite")
        it.allocate_tensors()
        inters[exit_name] = (it, it.get_input_details()[0], it.get_output_details()[0])
    soft = np.zeros((len(rows), 3, 43), dtype=np.float32)
    labs = np.zeros(len(rows), dtype=np.int64)
    for i, r in enumerate(rows):
        roi = (int(r["roi_x1"]), int(r["roi_y1"]), int(r["roi_x2"]), int(r["roi_y2"]))
        img = load_normalize(r["path"], roi, shifted=False)
        labs[i] = int(r["label"])
        for ei, exit_name in enumerate(["exit1", "exit2", "exit3"]):
            it, in_d, out_d = inters[exit_name]
            in_scale, in_zp = in_d["quantization"]
            out_scale, out_zp = out_d["quantization"]
            q = np.round(img / in_scale + in_zp).clip(-128, 127).astype(np.int8)
            it.set_tensor(in_d["index"], np.expand_dims(q, axis=0))
            it.invoke()
            out_q = it.get_tensor(out_d["index"])[0]
            logits = (out_q.astype(np.float32) - out_zp) * out_scale
            soft[i, ei] = tf.nn.softmax(logits).numpy()
        if (i + 1) % 500 == 0:
            print(f"  calib {i+1}/{len(rows)}")
    np.save(f"{OUT}/calib_softmax.npy", soft)
    np.save(f"{OUT}/calib_labels.npy", labs)
    print(f"calib softmax saved: {soft.shape}")


def main():
    import os, sys
    os.makedirs(OUT, exist_ok=True)
    if "--calib" in sys.argv:
        dump_calib(); return
    with open(TEST_CSV, newline="") as f:
        rows = list(csv.DictReader(f))
    rows = rows[:N_FRAMES]
    print(f"sequence: {len(rows)} frames, shift at frame {SHIFT_AT}")

    inters = {}
    for exit_name in ["exit1", "exit2", "exit3"]:
        it = tf.lite.Interpreter(model_path=f"{TFLITE}/{exit_name}_int8.tflite")
        it.allocate_tensors()
        inters[exit_name] = (it, it.get_input_details()[0], it.get_output_details()[0])

    rng = np.random.default_rng(20260811)
    out_rows = []
    soft_all = np.zeros((len(rows), 3, 43), dtype=np.float32)
    for i, r in enumerate(rows):
        roi = (int(r["roi_x1"]), int(r["roi_y1"]), int(r["roi_x2"]), int(r["roi_y2"]))
        shifted = i >= SHIFT_AT
        # per-frame noise draw (deterministic per frame)
        if shifted:
            np.random.seed(rng.integers(0, 2**31 - 1))
        img = load_normalize(r["path"], roi, shifted)
        true_label = int(r["label"])
        rec = {"frame": i, "label": true_label,
               "is_sc": int(true_label in SAFETY_CRITICAL)}
        soft = np.zeros((3, 43), dtype=np.float32)
        for ei, exit_name in enumerate(["exit1", "exit2", "exit3"]):
            it, in_d, out_d = inters[exit_name]
            in_scale, in_zp = in_d["quantization"]
            out_scale, out_zp = out_d["quantization"]
            q = np.round(img / in_scale + in_zp).clip(-128, 127).astype(np.int8)
            it.set_tensor(in_d["index"], np.expand_dims(q, axis=0))
            it.invoke()
            out_q = it.get_tensor(out_d["index"])[0]
            logits = (out_q.astype(np.float32) - out_zp) * out_scale
            soft[ei] = tf.nn.softmax(logits).numpy()
            rec[f"conf{exit_name[-1]}"] = float(soft[ei][int(np.argmax(soft[ei]))])
            rec[f"correct{exit_name[-1]}"] = int(int(np.argmax(soft[ei])) == true_label)
        soft_all[i] = soft
        out_rows.append(rec)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(rows)}")

    with open(f"{OUT}/aci_seq_1000.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    np.save(f"{OUT}/aci_softmax.npy", soft_all)
    print(f"wrote {OUT}/aci_seq_1000.csv + aci_softmax.npy ({len(out_rows)} rows)")
    # quick stats: coverage by segment
    clean = [r for r in out_rows if r["frame"] < SHIFT_AT]
    shift = [r for r in out_rows if r["frame"] >= SHIFT_AT]
    for name, seg in (("clean", clean), ("shifted", shift)):
        c3 = sum(r["correct3"] for r in seg) / len(seg)
        print(f"  {name}: exit3 top-1 accuracy {c3:.3f}")


if __name__ == "__main__":
    main()
