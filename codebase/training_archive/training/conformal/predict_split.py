"""
Run the deployed INT8 per-exit .tflite models over an arbitrary split CSV
(used for the margin_val split in the frozen four-way protocol) and write
per-sample prediction CSVs in the SAME format as calibration_predictions_*.csv
(confidence, correct, is_safety_critical).

This mirrors conformal/coverage_validate.py's run_tflite_on_test() so that
margin_val predictions are produced by the exact same INT8 inference path
(preprocessing, quantization, dequantize->softmax confidence) as the final
test touch. It does NOT touch test.csv.

Usage:
  python conformal/predict_split.py --split margin_val
Writes:
  results/margin_val_predictions_exit{1,2,3}.csv
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))

import tensorflow as tf  # noqa: E402

for _gpu in tf.config.list_physical_devices("GPU"):
    tf.config.experimental.set_memory_growth(_gpu, True)

from data.preprocessing import load_and_normalize  # noqa: E402

SPLITS_DIR = ROOT / "data" / "splits"
RESULTS_DIR = ROOT / "results"
TFLITE_DIR = RESULTS_DIR / "tflite"
EXITS = ["exit1", "exit2", "exit3"]

SAFETY_CRITICAL_CLASS_IDS = {
    0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16,
    11, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
}


def load_csv_records(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_tflite_on_split(tflite_path: Path, records: list[dict]) -> list[dict]:
    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()
    in_detail = interpreter.get_input_details()[0]
    out_detail = interpreter.get_output_details()[0]
    in_scale, in_zp = in_detail["quantization"]
    out_scale, out_zp = out_detail["quantization"]

    rows = []
    for r in records:
        roi = (int(r["roi_x1"]), int(r["roi_y1"]), int(r["roi_x2"]), int(r["roi_y2"]))
        true_label = int(r["label"])
        img = load_and_normalize(r["path"], roi)
        q = np.round(img / in_scale + in_zp).clip(-128, 127).astype(np.int8)
        interpreter.set_tensor(in_detail["index"], np.expand_dims(q, axis=0))
        interpreter.invoke()
        out_q = interpreter.get_tensor(out_detail["index"])[0]
        logits = (out_q.astype(np.float32) - out_zp) * out_scale
        probs = tf.nn.softmax(logits).numpy()
        pred_label = int(np.argmax(probs))
        rows.append({
            "confidence": float(probs[pred_label]),
            "correct": int(pred_label == true_label),
            "is_safety_critical": int(true_label in SAFETY_CRITICAL_CLASS_IDS),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="margin_val",
                    help="split CSV name under data/splits (default: margin_val)")
    args = ap.parse_args()

    split_csv = SPLITS_DIR / f"{args.split}.csv"
    if not split_csv.exists():
        raise SystemExit(f"{split_csv} does not exist")
    records = load_csv_records(split_csv)
    print(f"{args.split} split: {len(records)} images")

    for exit_name in EXITS:
        preds = run_tflite_on_split(TFLITE_DIR / f"{exit_name}_int8.tflite", records)
        out = RESULTS_DIR / f"{args.split}_predictions_{exit_name}.csv"
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(preds[0].keys()))
            writer.writeheader()
            writer.writerows(preds)
        print(f"  wrote {out}")
    print("done")


if __name__ == "__main__":
    main()
