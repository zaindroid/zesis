"""
Build the on-board workload blob for the free-running interleaved energy
experiment.

Selection: 1,200 images drawn from the FULL frozen test set
(data/splits/test.csv, the official separate GTSRB test archive) at NATURAL
class frequency -- NOT the stratified hw_validate sample. Rationale: the
certified menu's achieved miss-rates (exit1@0.05=4.47%, exit3@0.05=4.50%,
etc.) were validated on the natural-frequency test set; the safety-bound
confirmation ("empirical SC miss-rate <= operating alpha over the workload")
is only interpretable if the workload resembles the certified population.
The old stratified sample (87.8% SC, classes capped at 40) forces ~15% SC
miss for every policy including naive -- an artifact, not a signal.

Preprocessing MUST match the firmware's host-side producer exactly:
  load_and_normalize(path, roi) -> uint8 48x48x3, then quantize with segA
  input scale=0.007843137718737125, zero_point=-1 -> int8[6912].

Outputs (written under results/interleaved_freerun/):
  workload.bin       -- 1200 * 6912 = 8,294,400 bytes, raw int8, frame-major
  workload_manifest.csv -- idx, filename, label, is_safety_critical, roi...
  workload_sha256.txt -- SHA-256 of workload.bin and of the manifest

The blob is meant to be burned to the board's external W25Q64 QSPI flash
(8 MB) at offset 0; the free-running firmware reads frame i at offset i*6912.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent  # .../training
SPLITS = ROOT / "data" / "splits"
OUT_DIR = ROOT / "results" / "interleaved_freerun"

TARGET = 1200
TARGET_SIZE = 48
INPUT_MEAN = 127.5
INPUT_STD = 127.5
SEGA_SCALE = 0.007843137718737125
SEGA_ZP = -1
IMAGE_BYTES = 48 * 48 * 3

SAFETY_CRITICAL = {
    0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 15, 16,
    11, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
}


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260728)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    with open(SPLITS / "test.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"test.csv: {len(rows)} rows (frozen official test archive)")

    # Stratified-by-class natural-frequency sample.
    by_class: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_class[int(r["label"])].append(r)
    # Per-class target proportional to natural frequency, floored at 1.
    per_class_target: dict[int, int] = {}
    remaining = TARGET
    for label, recs in sorted(by_class.items()):
        share = int(TARGET * len(recs) / len(rows))
        per_class_target[label] = max(1, share)
        remaining -= per_class_target[label]
    # Distribute leftover to the largest classes (smallest rounding error).
    for label, _ in sorted(by_class.items(), key=lambda kv: -len(kv[1])):
        if remaining <= 0:
            break
        per_class_target[label] += 1
        remaining -= 1
    assert remaining == 0, f"leftover={remaining}"

    selected: list[dict] = []
    for label in sorted(by_class):
        recs = sorted(by_class[label], key=lambda r: r["path"])
        rng.shuffle(recs)
        selected.extend(recs[:per_class_target[label]])

    counts = Counter(int(r["label"]) for r in selected)
    n_sc = sum(1 for r in selected if int(r["label"]) in SAFETY_CRITICAL)
    print(f"selected: {len(selected)} images, {len(counts)} classes, "
          f"safety-critical={n_sc} ({n_sc/len(selected)*100:.1f}%)")

    # Sanity: safety-critical share should be near the natural test ratio.
    test_sc = sum(1 for r in rows if int(r["label"]) in SAFETY_CRITICAL)
    print(f"natural test SC ratio: {test_sc/len(rows)*100:.1f}%  "
          f"(selected: {n_sc/len(selected)*100:.1f}%)")

    blob = bytearray()
    manifest = []
    for r in selected:
        roi = (int(r["roi_x1"]), int(r["roi_y1"]), int(r["roi_x2"]), int(r["roi_y2"]))
        img = load_and_normalize(r["path"], roi)
        q = quantize(img, SEGA_SCALE, SEGA_ZP)
        assert q.shape == (TARGET_SIZE, TARGET_SIZE, 3)
        blob += q.tobytes()
        manifest.append({
            "idx": len(manifest),
            "path": r["path"],
            "label": r["label"],
            "is_safety_critical": int(int(r["label"]) in SAFETY_CRITICAL),
            "roi_x1": r["roi_x1"], "roi_y1": r["roi_y1"],
            "roi_x2": r["roi_x2"], "roi_y2": r["roi_y2"],
        })

    assert len(blob) == TARGET * IMAGE_BYTES, f"blob size {len(blob)}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bin_path = OUT_DIR / "workload.bin"
    bin_path.write_bytes(bytes(blob))
    man_path = OUT_DIR / "workload_manifest.csv"
    with open(man_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
        w.writeheader()
        w.writerows(manifest)

    digest_bin = hashlib.sha256(bin_path.read_bytes()).hexdigest()
    digest_man = hashlib.sha256(man_path.read_bytes()).hexdigest()
    (OUT_DIR / "workload_sha256.txt").write_text(
        f"{digest_bin}  workload.bin\n{digest_man}  workload_manifest.csv\n")

    print(f"wrote {bin_path} ({len(blob)/1048576:.2f} MB)")
    print(f"wrote {man_path}")
    print(f"SHA-256(bin)   = {digest_bin}")
    print(f"SHA-256(manifest) = {digest_man}")


if __name__ == "__main__":
    main()
