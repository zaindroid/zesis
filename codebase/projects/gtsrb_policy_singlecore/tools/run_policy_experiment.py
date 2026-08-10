"""
Drives the single-core crypto+perception interleaved policy experiment.
Streams the 1230-image on-device validation sample through the board (same
protocol style as hw_validate/run_hw_validate.py), one policy build at a
time. Board interleaves a crypto step every 10 frames (identical schedule
across all three policy builds) and replies with per-frame timing + exit +
confidence. This script just logs everything; cross-policy comparison
(total time, exit distribution, achieved miss-rate) happens in
analyze_policy_experiment.py.

Usage: python tools/run_policy_experiment.py <policy_name>
  where <policy_name> is one of: naive, static, adaptive
  (must match whichever POLICY the currently-flashed firmware was built
  with -- this script doesn't know or check that, it's on you to flash the
  right build first)
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import numpy as np
import serial
import tensorflow as tf
from PIL import Image

HERE = Path(__file__).parent
OUT_DIR = HERE.parent / "results" / "interleaved"
PORT = "COM9"
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
    if len(sys.argv) < 2 or sys.argv[1] not in ("naive", "static", "adaptive"):
        print("usage: python run_policy_experiment.py <naive|static|adaptive> [start] [end] [--no-quit]")
        sys.exit(1)
    policy_name = sys.argv[1]
    start_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    end_idx = int(sys.argv[3]) if len(sys.argv) > 3 else None
    send_quit = "--no-quit" not in sys.argv

    interp = tf.lite.Interpreter(model_path=str(HERE / "generated/segA_int8.tflite"))
    interp.allocate_tensors()
    in_scale, in_zp = interp.get_input_details()[0]["quantization"]
    print(f"segA input quantization: scale={in_scale}, zero_point={in_zp}")

    with open(HERE / "hw_validate/hw_validate_manifest.csv", newline="") as f:
        manifest = list(csv.DictReader(f))
    if end_idx is None:
        end_idx = len(manifest)
    manifest = manifest[start_idx:end_idx]
    print(f"manifest: rows [{start_idx}:{end_idx}) = {len(manifest)} images, policy={policy_name}")

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

    # Board prints several boot-time diagnostic lines (policy banner,
    # allowed-stop table, per-segment arena usage) before it reaches its
    # main loop and prints BATCH_READY. Draining those here, instead of
    # racing the first few frame sends against them, is what prevents the
    # early frames from being lost to a startup protocol desync.
    print("waiting for board BATCH_READY...")
    deadline = time.time() + 10
    while time.time() < deadline:
        line = ser.readline().decode(errors="replace").strip()
        if line:
            print(f"  board boot: {line}")
        if line == "BATCH_READY":
            break
    else:
        print("  WARNING: did not see BATCH_READY within 10s -- proceeding anyway")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"policy_results_{policy_name}.csv"
    fieldnames = ["idx", "filename", "label", "is_safety_critical",
                  "crypto_us", "frame_us", "exit_taken", "tier_used",
                  "pred1", "conf1", "pred2", "conf2", "pred3", "conf3"]
    n_ok = 0
    n_fail = 0
    t_start = time.time()
    file_mode = "a" if start_idx > 0 else "w"
    with open(out_path, file_mode, newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        if start_idx == 0:
            writer.writeheader()

        for row in manifest:
            path = str(HERE / "hw_validate/images" / row["filename"])
            roi = (int(row["roi_x1"]), int(row["roi_y1"]), int(row["roi_x2"]), int(row["roi_y2"]))
            label = int(row["label"])

            img = load_and_normalize(path, roi)
            q = quantize(img, in_scale, in_zp)

            ser.write(b"I" + q.tobytes())
            ser.flush()
            line = ser.readline().decode(errors="replace").strip()

            parts = line.split(",")
            if len(parts) != 11 or parts[0] != "R":
                print(f"  [{row['idx']}] BAD REPLY: {line!r} -- skipping (protocol desync?)")
                n_fail += 1
                continue

            (crypto_us, frame_us, exit_taken, tier_used,
             pred1, conf1, pred2, conf2, pred3, conf3) = (int(x) for x in parts[1:])
            writer.writerow({
                "idx": row["idx"], "filename": row["filename"], "label": label,
                "is_safety_critical": row["is_safety_critical"],
                "crypto_us": crypto_us, "frame_us": frame_us,
                "exit_taken": exit_taken, "tier_used": tier_used,
                "pred1": pred1, "conf1": conf1 / 1e6,
                "pred2": pred2, "conf2": conf2 / 1e6,
                "pred3": pred3, "conf3": conf3 / 1e6,
            })
            out_f.flush()
            n_ok += 1

            if n_ok % 100 == 0:
                elapsed = time.time() - t_start
                print(f"  {n_ok}/{len(manifest)} done ({elapsed:.0f}s elapsed)")

    if send_quit:
        ser.write(b"Q")
        ser.flush()
        time.sleep(0.2)
        tail = ser.read(200).decode(errors="replace")
        if tail:
            print(f"board: {tail.strip()}")
    ser.close()

    elapsed = time.time() - t_start
    print(f"\ndone: {n_ok} ok, {n_fail} failed/desynced, {elapsed:.0f}s wall-clock (incl. UART transfer)")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
