"""
Post-training INT8-per-channel (PCQ) quantization of the trained multi-exit
model, exported as three STANDALONE per-exit .tflite models (input -> exit_k),
sliced from the single trained multi-exit graph so all three share the exact
same trained weights.

representative_dataset = calibration split (data/splits/calibration.csv),
per the brief. Never touches data/splits/test.csv -- that's reserved for
conformal/coverage_validate.py's final evaluation.

Outputs:
  results/tflite/exit{1,2,3}_int8.tflite
  results/quantize_accuracy_report.csv     (FP32 vs INT8 per-exit accuracy)
  results/calibration_predictions_exit{1,2,3}.csv
      (per-sample INT8 predictions on calibration.csv -- confidence,
      correctness, safety-critical flag -- consumed by conformal/calibrate.py)

Usage: python train/quantize.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import tensorflow as tf  # noqa: E402

for _gpu in tf.config.list_physical_devices("GPU"):
    tf.config.experimental.set_memory_growth(_gpu, True)

from data.preprocessing import load_and_normalize, TARGET_SIZE  # noqa: E402
from models.architectures import build_multi_exit_model  # noqa: E402

SPLITS_DIR = ROOT / "data" / "splits"
RESULTS_DIR = ROOT / "results"
TFLITE_DIR = RESULTS_DIR / "tflite"
CKPT = ROOT / "results" / "checkpoints" / "multiexit" / "best.weights.h5"

EXIT_NAMES = ["exit1", "exit2", "exit3"]
N_REPRESENTATIVE = 500  # subsample of calibration.csv for PTQ scale/zero-point
                         # calibration -- generous for a model this size; the
                         # FULL calibration split is still used for the
                         # accuracy comparison and (downstream) conformal tau
                         # calibration, which are a different concern from PTQ
                         # representative-dataset sizing.

SAFETY_CRITICAL_CLASS_IDS = {
    0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16,
    11, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
}


def load_csv_records(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def image_and_roi(r: dict) -> tuple[str, tuple[int, int, int, int]]:
    return r["path"], (int(r["roi_x1"]), int(r["roi_y1"]), int(r["roi_x2"]), int(r["roi_y2"]))


def build_exit_submodels() -> dict[str, tf.keras.Model]:
    """Slice the trained multi-exit graph into 3 standalone single-output
    models. These share the exact same Layer objects (and therefore weights)
    as the original multi-exit model -- no weight copying, just new Model()
    wrappers around different output tensors of the same graph."""
    multi = build_multi_exit_model()
    multi.load_weights(str(CKPT))
    return {
        name: tf.keras.Model(inputs=multi.input, outputs=multi.get_layer(name).output,
                              name=f"{name}_standalone")
        for name in EXIT_NAMES
    }


def stratified_subset(records: list[dict], n_total: int, seed: int = 20260728) -> list[dict]:
    """calibration.csv is sorted by path (=> grouped by class subdirectory).
    A naive records[:n_total] prefix would bias PTQ scale/zero-point
    calibration toward whichever low-numbered classes happen to sort first
    and never see the rest of the class range at all. Stratify evenly across
    classes instead, seeded for reproducibility."""
    by_class: dict[int, list[dict]] = {}
    for r in records:
        by_class.setdefault(int(r["label"]), []).append(r)
    n_classes = len(by_class)
    per_class = max(1, n_total // n_classes)
    rng = np.random.default_rng(seed)
    subset = []
    for class_id, class_records in sorted(by_class.items()):
        idx = rng.choice(len(class_records), size=min(per_class, len(class_records)), replace=False)
        subset.extend(class_records[i] for i in idx)
    return subset


def make_representative_dataset(records: list[dict]):
    subset = stratified_subset(records, N_REPRESENTATIVE)
    print(f"  representative dataset: {len(subset)} images stratified across "
          f"{len(set(int(r['label']) for r in subset))} classes")

    def gen():
        for r in subset:
            path, roi = image_and_roi(r)
            img = load_and_normalize(path, roi)
            yield [np.expand_dims(img, axis=0)]
    return gen


def quantize_to_int8(model: tf.keras.Model, records: list[dict]) -> bytes:
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = make_representative_dataset(records)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    return converter.convert()


def run_tflite_interpreter(tflite_model: bytes, records: list[dict]) -> list[dict]:
    """Runs the INT8 interpreter over every record, returns per-sample
    prediction rows: true_label, pred_label, confidence (dequantized
    softmax-equivalent -- see note below), correct, is_safety_critical."""
    interpreter = tf.lite.Interpreter(model_content=tflite_model)
    interpreter.allocate_tensors()
    in_detail = interpreter.get_input_details()[0]
    out_detail = interpreter.get_output_details()[0]
    in_scale, in_zp = in_detail["quantization"]
    out_scale, out_zp = out_detail["quantization"]

    rows = []
    for r in records:
        path, roi = image_and_roi(r)
        true_label = int(r["label"])
        img = load_and_normalize(path, roi)  # float32, matches training input domain
        q = np.round(img / in_scale + in_zp).clip(-128, 127).astype(np.int8)
        interpreter.set_tensor(in_detail["index"], np.expand_dims(q, axis=0))
        interpreter.invoke()
        out_q = interpreter.get_tensor(out_detail["index"])[0]
        # Dequantize logits, then softmax for a genuine confidence score
        # (raw logits are not on a [0,1] scale and are not comparable across
        # exits without this step -- the tau threshold in conformal/ operates
        # on softmax confidence, matching how softmax is applied CPU-side
        # after NPU dispatch on the real board).
        logits = (out_q.astype(np.float32) - out_zp) * out_scale
        probs = tf.nn.softmax(logits).numpy()
        pred_label = int(np.argmax(probs))
        confidence = float(probs[pred_label])
        rows.append({
            "path": path,
            "true_label": true_label,
            "pred_label": pred_label,
            "confidence": confidence,
            "correct": int(pred_label == true_label),
            "is_safety_critical": int(true_label in SAFETY_CRITICAL_CLASS_IDS),
        })
    return rows


def run_fp32_model(model: tf.keras.Model, records: list[dict]) -> float:
    """FP32 accuracy for the same records, for the accuracy-drop comparison."""
    correct = 0
    for r in records:
        path, roi = image_and_roi(r)
        true_label = int(r["label"])
        img = load_and_normalize(path, roi)
        logits = model(np.expand_dims(img, axis=0), training=False).numpy()[0]
        pred_label = int(np.argmax(logits))
        correct += int(pred_label == true_label)
    return correct / len(records)


def main() -> None:
    TFLITE_DIR.mkdir(parents=True, exist_ok=True)
    calibration_records = load_csv_records(SPLITS_DIR / "calibration.csv")
    print(f"calibration split: {len(calibration_records)} images")

    submodels = build_exit_submodels()

    accuracy_rows = []
    for name in EXIT_NAMES:
        print(f"\n=== {name} ===")
        model = submodels[name]

        print("  quantizing (INT8 per-channel, PTQ)...")
        tflite_model = quantize_to_int8(model, calibration_records)
        out_path = TFLITE_DIR / f"{name}_int8.tflite"
        out_path.write_bytes(tflite_model)
        print(f"  wrote {out_path} ({len(tflite_model)} bytes)")

        print("  running FP32 on calibration split...")
        fp32_acc = run_fp32_model(model, calibration_records)

        print("  running INT8 on calibration split...")
        int8_rows = run_tflite_interpreter(tflite_model, calibration_records)
        int8_acc = sum(r["correct"] for r in int8_rows) / len(int8_rows)

        drop = fp32_acc - int8_acc
        print(f"  FP32 acc: {fp32_acc:.4f}  INT8 acc: {int8_acc:.4f}  drop: {drop:+.4f}")
        accuracy_rows.append({
            "exit": name, "fp32_acc": f"{fp32_acc:.4f}", "int8_acc": f"{int8_acc:.4f}",
            "drop_pp": f"{100 * drop:+.2f}",
        })

        pred_path = RESULTS_DIR / f"calibration_predictions_{name}.csv"
        with open(pred_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(int8_rows[0].keys()))
            writer.writeheader()
            writer.writerows(int8_rows)
        print(f"  wrote {pred_path}")

    report_path = RESULTS_DIR / "quantize_accuracy_report.csv"
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(accuracy_rows[0].keys()))
        writer.writeheader()
        writer.writerows(accuracy_rows)
    print(f"\nwrote {report_path}")

    if any(float(r["drop_pp"]) < -2.0 for r in accuracy_rows):
        print("\nWARNING: at least one exit's INT8 accuracy drop exceeds 2pp -- "
              "consider QAT (quantization-aware training) as a fallback, per the brief.")


if __name__ == "__main__":
    main()
