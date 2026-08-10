"""
Build the seeded, stratified train/calibration split from the official
GTSRB training archive, and package the official GTSRB test archive as the
held-out test split.

TRACK-AWARE SPLITTING (why this matters, read before changing anything):
GTSRB training images are not independent samples. Each physical sign
instance was photographed as a short "track" of ~30 sequential video
frames, encoded in the filename as `<trackID>_<frameID>.ppm` within each
class folder (e.g. `00000/00007_00023.ppm` = class 0, track 7, frame 23).
Consecutive frames of the same track are near-duplicates. Splitting by
INDIVIDUAL IMAGE rather than by whole TRACK would leak near-duplicate
frames of the same physical sign across train/calibration, which silently
invalidates the calibration split even though no literal file path
appears in both CSVs -- the conformal calibration set must see signs the
model's effective training distribution hasn't already memorized specific
frames of. This script splits by TRACK, never by individual frame.

The test split is the official, separately-photographed GTSRB test set --
different sessions/tracks entirely by construction, so it's used as-is and
is never touched by this script's splitting logic (only copied into the
same path,label,roi CSV format for consistency).

Usage: python train/split_dataset.py --seed 20260728 --cal-track-fraction 0.15
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
GTSRB_DIR = DATA_DIR / "gtsrb"
SPLITS_DIR = DATA_DIR / "splits"

MIN_CAL_TOTAL = 1500
MIN_CAL_PER_CLASS = 10  # floor; script errors out (not silently skips) if unreachable for any class


def find_dir(pattern: str) -> Path:
    candidates = list(GTSRB_DIR.rglob(pattern))
    if not candidates:
        raise FileNotFoundError(f"could not find {pattern} under {GTSRB_DIR}")
    return candidates[0]


def load_training_records() -> list[dict]:
    """Return one record per training image: class_id, track_id, path, roi."""
    train_root = find_dir("Final_Training/Images")
    records = []
    for class_dir in sorted(train_root.iterdir()):
        if not class_dir.is_dir():
            continue
        class_id = int(class_dir.name)
        gt_csv = class_dir / f"GT-{class_dir.name}.csv"
        with open(gt_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                filename = row["Filename"]
                track_id = int(filename.split("_")[0])
                records.append({
                    "class_id": class_id,
                    "track_id": track_id,
                    "path": str((class_dir / filename).resolve()),
                    "roi_x1": int(row["Roi.X1"]),
                    "roi_y1": int(row["Roi.Y1"]),
                    "roi_x2": int(row["Roi.X2"]),
                    "roi_y2": int(row["Roi.Y2"]),
                })
    return records


def load_test_records() -> list[dict]:
    test_root = find_dir("Final_Test/Images")
    gt_csv = find_dir("GT-final_test.csv") if (GTSRB_DIR / "GT-final_test.csv").exists() else None
    gt_csv_candidates = list(GTSRB_DIR.rglob("GT-final_test.csv"))
    gt_csv = gt_csv_candidates[0]
    records = []
    with open(gt_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            filename = row["Filename"]
            records.append({
                "class_id": int(row["ClassId"]),
                "path": str((test_root / filename).resolve()),
                "roi_x1": int(row["Roi.X1"]),
                "roi_y1": int(row["Roi.Y1"]),
                "roi_x2": int(row["Roi.X2"]),
                "roi_y2": int(row["Roi.Y2"]),
            })
    return records


def split_train_calibration(records: list[dict], seed: int, cal_track_fraction: float
                             ) -> tuple[list[dict], list[dict]]:
    # Group by (class_id, track_id) -> list of frame records
    tracks: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for r in records:
        tracks[(r["class_id"], r["track_id"])].append(r)

    tracks_by_class: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for key in tracks:
        tracks_by_class[key[0]].append(key)

    rng = random.Random(seed)
    train_records: list[dict] = []
    cal_records: list[dict] = []

    for class_id, track_keys in sorted(tracks_by_class.items()):
        track_keys = sorted(track_keys)  # deterministic order before seeded shuffle
        rng.shuffle(track_keys)
        n_tracks = len(track_keys)
        n_cal_tracks = max(1, round(n_tracks * cal_track_fraction))
        if n_cal_tracks >= n_tracks:
            n_cal_tracks = n_tracks - 1  # always leave >=1 track for training
        cal_keys = set(track_keys[:n_cal_tracks])

        class_cal_count = sum(len(tracks[k]) for k in track_keys if k in cal_keys)
        if class_cal_count < MIN_CAL_PER_CLASS:
            raise AssertionError(
                f"class {class_id}: only {class_cal_count} calibration images from "
                f"{n_cal_tracks}/{n_tracks} tracks -- below MIN_CAL_PER_CLASS={MIN_CAL_PER_CLASS}. "
                f"Increase --cal-track-fraction."
            )

        for key in track_keys:
            target = cal_records if key in cal_keys else train_records
            target.extend(tracks[key])

    total_cal = len(cal_records)
    if total_cal < MIN_CAL_TOTAL:
        raise AssertionError(
            f"calibration split has {total_cal} images, below MIN_CAL_TOTAL={MIN_CAL_TOTAL}. "
            f"Increase --cal-track-fraction and rerun."
        )

    return train_records, cal_records


def write_split_csv(records: list[dict], path: Path) -> str:
    """Write (path,label,roi_x1,roi_y1,roi_x2,roi_y2) CSV, return its SHA-256 hex digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "label", "roi_x1", "roi_y1", "roi_x2", "roi_y2"])
        for r in sorted(records, key=lambda r: r["path"]):
            writer.writerow([r["path"], r["class_id"], r["roi_x1"], r["roi_y1"],
                              r["roi_x2"], r["roi_y2"]])
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_class_distribution(records: list[dict], path: Path, n_classes: int = 43) -> None:
    counts = defaultdict(int)
    for r in records:
        counts[r["class_id"]] += 1
    total = len(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["class_id", "count", "fraction_of_split"])
        for class_id in range(n_classes):
            c = counts.get(class_id, 0)
            writer.writerow([class_id, c, f"{c / total:.4f}" if total else "0.0000"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260728,
                     help="fixed seed for track shuffling (default: date-derived, documented in README)")
    ap.add_argument("--cal-track-fraction", type=float, default=0.15,
                     help="fraction of TRACKS (not images) per class allocated to calibration")
    args = ap.parse_args()

    print(f"seed={args.seed} cal_track_fraction={args.cal_track_fraction}")

    print("loading training annotations...")
    train_pool = load_training_records()
    print(f"  {len(train_pool)} training images across "
          f"{len(set(r['class_id'] for r in train_pool))} classes")

    print("loading test annotations...")
    test_records = load_test_records()
    print(f"  {len(test_records)} test images across "
          f"{len(set(r['class_id'] for r in test_records))} classes")

    print("splitting train/calibration by TRACK (seeded, stratified per class)...")
    train_records, cal_records = split_train_calibration(
        train_pool, seed=args.seed, cal_track_fraction=args.cal_track_fraction)
    print(f"  train: {len(train_records)} images")
    print(f"  calibration: {len(cal_records)} images")

    # sanity: no path appears in both train and calibration
    train_paths = set(r["path"] for r in train_records)
    cal_paths = set(r["path"] for r in cal_records)
    overlap = train_paths & cal_paths
    assert not overlap, f"BUG: {len(overlap)} paths appear in both train and calibration"

    hashes = {}
    hashes["train.csv"] = write_split_csv(train_records, SPLITS_DIR / "train.csv")
    hashes["calibration.csv"] = write_split_csv(cal_records, SPLITS_DIR / "calibration.csv")
    hashes["test.csv"] = write_split_csv(test_records, SPLITS_DIR / "test.csv")

    write_class_distribution(train_records, SPLITS_DIR / "class_distribution_train.csv")
    write_class_distribution(cal_records, SPLITS_DIR / "class_distribution_calibration.csv")
    write_class_distribution(test_records, SPLITS_DIR / "class_distribution_test.csv")

    with open(SPLITS_DIR / "checksums.sha256", "w", encoding="utf-8") as f:
        for name, digest in hashes.items():
            f.write(f"{digest}  {name}\n")

    summary_lines = [
        "# Split summary",
        "",
        f"Seed: `{args.seed}`  |  cal_track_fraction: `{args.cal_track_fraction}`",
        "",
        "| split | images | classes present |",
        "|---|---|---|",
        f"| train | {len(train_records)} | {len(set(r['class_id'] for r in train_records))} |",
        f"| calibration | {len(cal_records)} | {len(set(r['class_id'] for r in cal_records))} |",
        f"| test | {len(test_records)} | {len(set(r['class_id'] for r in test_records))} |",
        "",
        "SHA-256 checksums in `checksums.sha256`. Per-class distribution tables in "
        "`class_distribution_{train,calibration,test}.csv`.",
        "",
        "Train/calibration were split by GTSRB TRACK (physical sign instance, ~30 "
        "sequential frames), never by individual frame -- see the module docstring "
        "in `train/split_dataset.py` for why. Test is the official, separately-"
        "photographed GTSRB test set, used unmodified.",
    ]
    with open(SPLITS_DIR / "SPLIT_SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")

    print("\ndone. wrote:")
    for name in ["train.csv", "calibration.csv", "test.csv", "checksums.sha256",
                 "class_distribution_train.csv", "class_distribution_calibration.csv",
                 "class_distribution_test.csv", "SPLIT_SUMMARY.md"]:
        print(f"  data/splits/{name}")


if __name__ == "__main__":
    main()
