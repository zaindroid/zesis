"""
On-device conformal coverage validation: streams a stratified sample of
real GTSRB test images (tools/hw_validate/images/, manifest.csv, pulled
from the training lab's held-out TEST split -- never touched before now)
through the actual deployed NPU chain via the UART batch protocol added to
main.cpp, and logs per-exit prediction + confidence for each.

This replaces the PC TFLite-interpreter simulation used in
conformal/coverage_validate.py with genuine NPU hardware output, since
golden-input check (tools/golden/) showed the two are not bit-exact
(1-4 LSB drift). Output feeds compute_coverage.py.

Protocol: after boot, firmware idles at BATCH_READY waiting for
'I' + 6912 raw INT8 bytes; replies "R,pred1,conf1,pred2,conf2,pred3,conf3"
(confidences scaled by 1e6). If the board is mid-boot when this starts,
early writes may be lost -- rerun after a fresh reset/reflash if replies
don't line up.

Usage: python tools/hw_validate/run_hw_validate.py
"""
from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np
import serial
import tensorflow as tf
from PIL import Image

HERE = Path(__file__).parent
PORT = "COM3"
BAUD = 115200
TARGET_SIZE = 48
INPUT_MEAN = 127.5
INPUT_STD = 127.5


def load_and_normalize(path: str, roi) -> np.ndarray:
    with Image.open(path) as img:
        img = img.convert("RGB")
        if roi is not None:
            img = img.crop(roi)
        img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.uint8)
    return (arr.astype(np.float32) - INPUT_MEAN) / INPUT_STD


def quantize(arr: np.ndarray, scale: float, zero_point: int) -> np.ndarray:
    return np.round(arr / scale + zero_point).clip(-128, 127).astype(np.int8)


def main():
    interp = tf.lite.Interpreter(model_path=str(HERE / "../generated/segA_int8.tflite"))
    interp.allocate_tensors()
    in_scale, in_zp = interp.get_input_details()[0]["quantization"]
    print(f"segA input quantization: scale={in_scale}, zero_point={in_zp}")

    with open(HERE / "hw_validate_manifest.csv", newline="") as f:
        manifest = list(csv.DictReader(f))
    print(f"manifest: {len(manifest)} images")

    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 5
    ser.write_timeout = 5
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    ser.open()
    ser.reset_input_buffer()

    out_path = HERE / "hw_results.csv"
    fieldnames = ["idx", "filename", "label", "is_safety_critical",
                  "pred1", "conf1", "correct1",
                  "pred2", "conf2", "correct2",
                  "pred3", "conf3", "correct3"]
    n_ok = 0
    n_fail = 0
    t_start = time.time()
    with open(out_path, "w", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()

        for row in manifest:
            path = str(HERE / "images" / row["filename"])
            roi = (int(row["roi_x1"]), int(row["roi_y1"]), int(row["roi_x2"]), int(row["roi_y2"]))
            label = int(row["label"])

            img = load_and_normalize(path, roi)
            q = quantize(img, in_scale, in_zp)

            ser.write(b"I" + q.tobytes())
            ser.flush()
            line = ser.readline().decode(errors="replace").strip()

            parts = line.split(",")
            if len(parts) != 7 or parts[0] != "R":
                print(f"  [{row['idx']}] BAD REPLY: {line!r} -- skipping (protocol desync?)")
                n_fail += 1
                continue

            pred1, conf1, pred2, conf2, pred3, conf3 = (int(x) for x in parts[1:])
            writer.writerow({
                "idx": row["idx"], "filename": row["filename"], "label": label,
                "is_safety_critical": row["is_safety_critical"],
                "pred1": pred1, "conf1": conf1 / 1e6, "correct1": int(pred1 == label),
                "pred2": pred2, "conf2": conf2 / 1e6, "correct2": int(pred2 == label),
                "pred3": pred3, "conf3": conf3 / 1e6, "correct3": int(pred3 == label),
            })
            out_f.flush()
            n_ok += 1

            if n_ok % 100 == 0:
                elapsed = time.time() - t_start
                print(f"  {n_ok}/{len(manifest)} done ({elapsed:.0f}s elapsed, "
                      f"{elapsed/n_ok*1000:.0f} ms/image avg)")

    ser.close()
    elapsed = time.time() - t_start
    print(f"\ndone: {n_ok} ok, {n_fail} failed/desynced, {elapsed:.0f}s total")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
