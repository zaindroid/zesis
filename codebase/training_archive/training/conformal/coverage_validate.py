"""
Final coverage validation: applies the calibrated tau_k thresholds
(conformal/calibrate.py's output, chosen on the CALIBRATION split) to the
held-out TEST split, and checks whether the achieved safety-critical
miss-rate among accepted test samples actually stays <= the target alpha.

This is the FIRST AND ONLY script in this lab that touches
data/splits/test.csv -- per Brief 1's rule ("test touched only at final
eval"). If this script needs to be rerun after any model/tau change, that's
a signal the change needs re-validating, not a routine step.

Reads:
  results/tflite/exit{1,2,3}_int8.tflite
  results/conformal_tau_table.csv
  data/splits/test.csv
Writes:
  results/coverage_validation_table.csv   -- the headline thesis artifact
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


def run_tflite_on_test(tflite_path: Path, records: list[dict]) -> list[dict]:
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
    test_records = load_csv_records(SPLITS_DIR / "test.csv")
    print(f"test split: {len(test_records)} images (first touch of test.csv in this lab)")

    with open(RESULTS_DIR / "conformal_tau_table.csv", newline="") as f:
        tau_table = list(csv.DictReader(f))

    out_rows = []
    predictions_cache: dict[str, list[dict]] = {}
    for exit_name in EXITS:
        print(f"\n=== {exit_name} ===")
        preds = run_tflite_on_test(TFLITE_DIR / f"{exit_name}_int8.tflite", test_records)
        predictions_cache[exit_name] = preds

        # Persisted for diagnosis/reuse -- mirrors calibration_predictions_*.csv
        # from train/quantize.py. This is the ONE place test.csv predictions
        # get saved; don't add other ad-hoc test-touching scripts elsewhere.
        pred_path = RESULTS_DIR / f"test_predictions_{exit_name}.csv"
        with open(pred_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(preds[0].keys()))
            writer.writeheader()
            writer.writerows(preds)
        print(f"  wrote {pred_path}")

        # Diagnostic: tau=0 (accept-everyone) safety-critical miss-rate,
        # calibration vs test -- isolates whether calibration->test gaps in
        # the table below are from tau selection or from a base-rate
        # distribution shift between the two splits (calibration is
        # track-held-out from the TRAINING archive; test is the officially
        # separate GTSRB test archive -- different photography sessions).
        sc_test = [p for p in preds if p["is_safety_critical"]]
        test_base_miss = sum(1 - p["correct"] for p in sc_test) / len(sc_test)
        with open(RESULTS_DIR / f"calibration_predictions_{exit_name}.csv", newline="") as f:
            cal_preds = [{"correct": int(r["correct"]), "is_safety_critical": int(r["is_safety_critical"])}
                         for r in csv.DictReader(f)]
        sc_cal = [p for p in cal_preds if p["is_safety_critical"]]
        cal_base_miss = sum(1 - p["correct"] for p in sc_cal) / len(sc_cal)
        print(f"  [diagnostic] tau=0 safety-critical miss-rate: "
              f"calibration={cal_base_miss:.4f} (n={len(sc_cal)})  "
              f"test={test_base_miss:.4f} (n={len(sc_test)})  "
              f"gap={test_base_miss - cal_base_miss:+.4f}")

    for row in tau_table:
        exit_name = row["exit"]
        alpha = float(row["alpha"])
        tau = float(row["tau"])
        certifiable = row["certifiable"] == "True"

        preds = predictions_cache[exit_name]
        sc = [p for p in preds if p["is_safety_critical"]]
        accepted = [p for p in sc if p["confidence"] >= tau]
        n = len(accepted)
        achieved_miss = (sum(1 - p["correct"] for p in accepted) / n) if n > 0 else float("nan")
        passes = certifiable and (n > 0) and (achieved_miss <= alpha)

        print(f"{exit_name} alpha={alpha} tau={tau:.3f}: n_accepted={n} "
              f"achieved_miss={achieved_miss:.4f} target<={alpha} "
              f"{'PASS' if passes else 'FAIL'}{'' if certifiable else ' (not certifiable at calibration time)'}")

        out_rows.append({
            "exit": exit_name, "target_alpha": alpha, "tau_k": tau,
            "certifiable_at_calibration": certifiable,
            "n_accepted_test": n, "achieved_miss_rate_test": f"{achieved_miss:.4f}" if n > 0 else "nan",
            "passes": passes,
        })

    out_path = RESULTS_DIR / "coverage_validation_table.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"\nwrote {out_path}")

    n_fail = sum(1 for r in out_rows if not r["passes"])
    if n_fail:
        print(f"\nWARNING: {n_fail}/{len(out_rows)} (exit, alpha) combinations FAILED "
              f"coverage validation on test -- the finite-sample calibration bound did "
              f"not generalize for these. Investigate before treating those tau_k as certified.")
    else:
        print(f"\nAll {len(out_rows)} (exit, alpha) combinations passed coverage validation.")


if __name__ == "__main__":
    main()
