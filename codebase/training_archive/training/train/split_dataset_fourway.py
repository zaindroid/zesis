"""
FROZEN-PROTOCOL four-way split: train / calibration / margin_val / test.

Why this file exists (read before changing anything):
  Brief 1's original split_dataset.py made a TWO-way track-aware split
  (train + calibration) and treated the official GTSRB test archive as the
  held-out test split. The conformal-certification protocol was later
  upgraded to a FROZEN FOUR-WAY protocol (see data/splits/FROZEN_PROTOCOL.md):

    train        75%   -- training + internal monitoring-val (checkpoint selection ONLY here)
    calibration  15%   -- conformal tau_k calibration ONLY
    margin_val   10%   -- MARGIN derivation ONLY (calibration->margin_val shift)
    test         (official GTSRB test archive, QUARANTINED -- never written by this script)

  The critical invariant: test.csv is defined ONCE and then never touched
  until the final single coverage_validate.py run. This script therefore
  does NOT write test.csv at all -- it only records the frozen checksum of
  the already-existing test.csv in checksums.sha256. The previous
  contaminated practice (tuning MARGIN_FACTOR / checkpoint against test
  feedback) is what this split exists to make impossible.

  Track-aware splitting is preserved from Brief 1: GTSRB filenames encode
  <trackID>_<frameID>.ppm, ~30 near-duplicate frames of the same physical
  sign. Splitting by individual frame would leak near-duplicates across
  splits; this script splits by TRACK, never by frame, per class, seeded.

Usage:
  python train/split_dataset_fourway.py --seed 20260728 \
      --train-track-fraction 0.75 --cal-track-fraction 0.15 --margin-track-fraction 0.10
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

MIN_CAL_PER_CLASS = 10    # floor; errors out (not silently skips) if unreachable
MIN_MARGIN_PER_CLASS = 10
MIN_MARGIN_TOTAL = 500    # margin_val safety-critical budget; see FROZEN_PROTOCOL.md


def find_dir(pattern: str) -> Path:
    candidates = list(GTSRB_DIR.rglob(pattern))
    if not candidates:
        raise FileNotFoundError(f"could not find {pattern} under {GTSRB_DIR}")
    return candidates[0]


def load_training_records() -> list[dict]:
    """One record per training image: class_id, track_id, path, roi."""
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


def split_three_way(records: list[dict], seed: int,
                    train_frac: float, cal_frac: float, margin_frac: float
                    ) -> tuple[list[dict], list[dict], list[dict]]:
    """Per-class, per-track three-way split (seeded, stratified per class).

    Allocation per class (by TRACK, never by frame):
      n_cal    = max(1, round(n_tracks * cal_frac))
      n_margin = max(1, round(n_tracks * margin_frac))
      guard:   n_cal + n_margin < n_tracks  (always leave >= 1 track for train)
    Track order is seeded-shuffled once; cal takes the first n_cal, margin
    the next n_margin, train the rest. Same seed + fractions => identical
    output every run.
    """
    tracks: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for r in records:
        tracks[(r["class_id"], r["track_id"])].append(r)

    tracks_by_class: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for key in tracks:
        tracks_by_class[key[0]].append(key)

    rng = random.Random(seed)
    train_records: list[dict] = []
    cal_records: list[dict] = []
    margin_records: list[dict] = []

    for class_id, track_keys in sorted(tracks_by_class.items()):
        track_keys = sorted(track_keys)  # deterministic order before seeded shuffle
        rng.shuffle(track_keys)
        n_tracks = len(track_keys)

        n_cal = max(1, round(n_tracks * cal_frac))
        n_margin = max(1, round(n_tracks * margin_frac))
        if n_cal + n_margin >= n_tracks:
            n_margin = max(0, n_tracks - n_cal - 1)  # always leave >= 1 for train

        cal_keys = set(track_keys[:n_cal])
        margin_keys = set(track_keys[n_cal:n_cal + n_margin])

        class_cal_count = sum(len(tracks[k]) for k in cal_keys)
        class_margin_count = sum(len(tracks[k]) for k in margin_keys)
        if class_cal_count < MIN_CAL_PER_CLASS:
            raise AssertionError(
                f"class {class_id}: only {class_cal_count} calibration images -- "
                f"below MIN_CAL_PER_CLASS={MIN_CAL_PER_CLASS}. Increase --cal-track-fraction.")
        if class_margin_count < MIN_MARGIN_PER_CLASS:
            raise AssertionError(
                f"class {class_id}: only {class_margin_count} margin images -- "
                f"below MIN_MARGIN_PER_CLASS={MIN_MARGIN_PER_CLASS}. Increase --margin-track-fraction.")

        for key in track_keys:
            if key in cal_keys:
                cal_records.extend(tracks[key])
            elif key in margin_keys:
                margin_records.extend(tracks[key])
            else:
                train_records.extend(tracks[key])

    if len(margin_records) < MIN_MARGIN_TOTAL:
        raise AssertionError(
            f"margin_val split has {len(margin_records)} images, below MIN_MARGIN_TOTAL={MIN_MARGIN_TOTAL}.")
    return train_records, cal_records, margin_records


def write_split_csv(records: list[dict], path: Path) -> str:
    """Write (path,label,roi_x1,roi_y1,roi_x2,roi_y2) CSV, return SHA-256 hex digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path", "label", "roi_x1", "roi_y1", "roi_x2", "roi_y2"])
        for r in sorted(records, key=lambda r: r["path"]):
            writer.writerow([r["path"], r["class_id"], r["roi_x1"], r["roi_y1"],
                             r["roi_x2"], r["roi_y2"]])
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_of(path: Path) -> str:
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
    ap.add_argument("--seed", type=int, default=20260728)
    ap.add_argument("--train-track-fraction", type=float, default=0.75)
    ap.add_argument("--cal-track-fraction", type=float, default=0.15)
    ap.add_argument("--margin-track-fraction", type=float, default=0.10)
    args = ap.parse_args()

    print(f"seed={args.seed} fractions train/cal/margin = "
          f"{args.train_track_fraction}/{args.cal_track_fraction}/{args.margin_track_fraction}")

    train_pool = load_training_records()
    print(f"  {len(train_pool)} training images across "
          f"{len(set(r['class_id'] for r in train_pool))} classes")

    train_records, cal_records, margin_records = split_three_way(
        train_pool, seed=args.seed,
        train_frac=args.train_track_fraction,
        cal_frac=args.cal_track_fraction,
        margin_frac=args.margin_track_fraction)
    print(f"  train: {len(train_records)}  calibration: {len(cal_records)}  "
          f"margin_val: {len(margin_records)}")

    # Disjointness sanity (also enforced structurally by track allocation).
    all_paths = [set(r["path"] for r in split) for split in
                 (train_records, cal_records, margin_records)]
    assert not (all_paths[0] & all_paths[1]) and not (all_paths[0] & all_paths[2]) \
        and not (all_paths[1] & all_paths[2]), "BUG: overlap between splits"

    # TEST IS QUARANTINED: never rewrite it. Record the frozen checksum only.
    test_path = SPLITS_DIR / "test.csv"
    assert test_path.exists(), f"quarantined test.csv missing at {test_path}"
    test_checksum = sha256_of(test_path)

    hashes = {
        "train.csv": write_split_csv(train_records, SPLITS_DIR / "train.csv"),
        "calibration.csv": write_split_csv(cal_records, SPLITS_DIR / "calibration.csv"),
        "margin_val.csv": write_split_csv(margin_records, SPLITS_DIR / "margin_val.csv"),
        "test.csv": test_checksum,  # frozen, NOT rewritten
    }
    with open(SPLITS_DIR / "checksums.sha256", "w", encoding="utf-8") as f:
        for name, digest in hashes.items():
            f.write(f"{digest}  {name}\n")

    write_class_distribution(train_records, SPLITS_DIR / "class_distribution_train.csv")
    write_class_distribution(cal_records, SPLITS_DIR / "class_distribution_calibration.csv")
    write_class_distribution(margin_records, SPLITS_DIR / "class_distribution_margin_val.csv")

    summary = [
        "# Split summary (FROZEN FOUR-WAY protocol)",
        "",
        f"Seed: `{args.seed}`  |  track fractions train/cal/margin = "
        f"`{args.train_track_fraction}/{args.cal_track_fraction}/{args.margin_track_fraction}`",
        "",
        "| split | images | classes present | role |",
        "|---|---|---|---|",
        f"| train | {len(train_records)} | {len(set(r['class_id'] for r in train_records))} | checkpoint selection (train + internal val) |",
        f"| calibration | {len(cal_records)} | {len(set(r['class_id'] for r in cal_records))} | conformal tau_k only |",
        f"| margin_val | {len(margin_records)} | {len(set(r['class_id'] for r in margin_records))} | margin derivation only |",
        f"| test | (quarantined, unchanged) | 43 | final single touch only |",
        "",
        "test.csv was defined once and is QUARANTINED: this script never writes it; "
        "its SHA-256 in checksums.sha256 is frozen. The full protocol is documented in "
        "FROZEN_PROTOCOL.md -- do not re-run coverage_validate.py except as the final, "
        "single, frozen test touch.",
        "",
        "All splits are TRACK-aware (never frame-level) and stratified per class -- "
        "see the module docstring and data/splits/safety_critical.md.",
    ]
    with open(SPLITS_DIR / "SPLIT_SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")

    print("\ndone. wrote: train.csv, calibration.csv, margin_val.csv, checksums.sha256, "
          "class_distribution_{train,calibration,margin_val}.csv, SPLIT_SUMMARY.md")
    print(f"test.csv frozen checksum: {test_checksum}")


if __name__ == "__main__":
    main()
