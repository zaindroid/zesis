"""
Trains either the multi-exit model or the no-exit baseline (models/architectures.py)
on the GTSRB train split, holding out a track-aware monitoring slice for
per-exit accuracy logging. Does NOT touch data/splits/calibration.csv or
data/splits/test.csv -- those are reserved for Brief 3.

Usage:
  python train/train.py --config train/configs/multiexit.yaml
  python train/train.py --config train/configs/baseline.yaml
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import tensorflow as tf  # noqa: E402

# ged25-ki is a shared multi-user GPU box (see README). By default TF grabs
# most/all GPU memory upfront on first use, which starves other users'
# concurrent jobs (and vice versa -- a previous run here was killed when
# another job grabbed ~19GB mid-training). This model is tiny (<100K params);
# it doesn't need much VRAM, so let it grow on demand instead of claiming
# everything. Must run before any other TF GPU call.
for _gpu in tf.config.list_physical_devices("GPU"):
    tf.config.experimental.set_memory_growth(_gpu, True)

from data.preprocessing import load_and_normalize, TARGET_SIZE  # noqa: E402
from models.architectures import (  # noqa: E402
    build_multi_exit_model, build_baseline_model, count_params_by_component,
)

SPLITS_DIR = ROOT / "data" / "splits"


def set_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def load_csv_records(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def track_id_from_path(path: str) -> int:
    """GTSRB training filenames are <trackID>_<frameID>.ppm -- same
    track-awareness rule as train/split_dataset.py, reapplied here so this
    monitoring val-slice doesn't leak near-duplicate frames either."""
    stem = Path(path).stem
    return int(stem.split("_")[0])


def track_aware_holdout(records: list[dict], seed: int, val_track_fraction: float
                         ) -> tuple[list[dict], list[dict]]:
    """Carve a monitoring val-slice out of TRAIN, by track, stratified per
    class -- mirrors train/split_dataset.py's train/calibration logic so
    this internal training-monitoring split has the same leakage guarantee.
    This is NOT the calibration split; it's purely for watching per-exit
    accuracy during training and is never referenced by conformal/."""
    by_class_track: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for r in records:
        key = (int(r["label"]), track_id_from_path(r["path"]))
        by_class_track[key].append(r)

    tracks_by_class: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for key in by_class_track:
        tracks_by_class[key[0]].append(key)

    rng = random.Random(seed)
    train_records, val_records = [], []
    for class_id, keys in sorted(tracks_by_class.items()):
        keys = sorted(keys)
        rng.shuffle(keys)
        n_val = max(1, round(len(keys) * val_track_fraction))
        n_val = min(n_val, len(keys) - 1)  # always leave >=1 track for training
        val_keys = set(keys[:n_val])
        for key in keys:
            target = val_records if key in val_keys else train_records
            target.extend(by_class_track[key])
    return train_records, val_records


def make_dataset(records: list[dict], batch_size: int, shuffle: bool, seed: int,
                  multi_exit: bool) -> tf.data.Dataset:
    paths = [r["path"] for r in records]
    labels = [int(r["label"]) for r in records]
    rois = [(int(r["roi_x1"]), int(r["roi_y1"]), int(r["roi_x2"]), int(r["roi_y2"]))
            for r in records]

    def gen():
        for path, label, roi in zip(paths, labels, rois):
            img = load_and_normalize(path, roi)
            yield img, label

    ds = tf.data.Dataset.from_generator(
        gen,
        output_signature=(
            tf.TensorSpec(shape=(TARGET_SIZE, TARGET_SIZE, 3), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.int32),
        ),
    )
    ds = ds.cache()
    if shuffle:
        ds = ds.shuffle(buffer_size=len(records), seed=seed, reshuffle_each_iteration=True)

    if multi_exit:
        ds = ds.map(lambda img, label: (img, {"exit1": label, "exit2": label, "exit3": label}),
                    num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return ds


class MaxOfMinCheckpoint(tf.keras.callbacks.Callback):
    """Saves weights at the epoch where min(val_exit1_acc, val_exit2_acc,
    val_exit3_acc) is maximized -- the joint selection criterion for the
    anytime-certification story: it picks the epoch where the WEAKEST exit is
    strongest, instead of only optimizing the final exit (val_exit3_acc, which
    is what the regular ModelCheckpoint below uses). Writes
    results/checkpoints/multiexit/best_joint.weights.h5.
    """

    def __init__(self, filepath: str) -> None:
        super().__init__()
        self.filepath = filepath
        self.best_min = -1.0

    def on_epoch_end(self, epoch: int, logs: dict | None = None) -> None:
        logs = logs or {}
        keys = ["val_exit1_acc", "val_exit2_acc", "val_exit3_acc"]
        if not all(k in logs for k in keys):
            return
        cur_min = min(float(logs[k]) for k in keys)
        if cur_min > self.best_min:
            self.best_min = cur_min
            self.model.save_weights(self.filepath)
            print(f"\nMaxOfMinCheckpoint: epoch {epoch + 1} min={cur_min:.4f} "
                  f"(saved {self.filepath})")


def build_and_compile(model_kind: str, exit_loss_weights: dict, learning_rate: float) -> tf.keras.Model:
    # jit_compile=False: RTX 5090 (Blackwell, compute capability 12.0a) hits a
    # hard XLA/Triton fused-GEMM compilation failure during the backward pass
    # on this TF 2.21 build ("Autotuner could not compile any configs for
    # HLO: ...gemm_fusion..."). Forward-only ops (e.g. env/gpu_check.py's
    # plain matmul) work fine; it's specifically the XLA auto-clustering
    # around fused train-step ops that breaks. Not a code bug -- a genuine
    # gap in this TF build's compiler support for a very new GPU
    # architecture. Non-XLA (graph-mode) training works correctly.
    if model_kind == "multiexit":
        model = build_multi_exit_model()
        loss = {k: tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
                for k in ("exit1", "exit2", "exit3")}
        metrics = {k: [tf.keras.metrics.SparseCategoricalAccuracy(name="acc")]
                   for k in ("exit1", "exit2", "exit3")}
        model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate),
                      loss=loss, loss_weights=exit_loss_weights, metrics=metrics,
                      jit_compile=False)
    elif model_kind == "baseline":
        model = build_baseline_model()
        model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate),
                      loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                      metrics=[tf.keras.metrics.SparseCategoricalAccuracy(name="acc")],
                      jit_compile=False)
    else:
        raise ValueError(f"unknown model_kind: {model_kind}")
    return model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    set_seeds(cfg["seed"])
    model_kind = cfg["model"]
    multi_exit = model_kind == "multiexit"

    print(f"config: {args.config}")
    print(json.dumps(cfg, indent=2))

    all_train_records = load_csv_records(SPLITS_DIR / "train.csv")
    train_records, val_records = track_aware_holdout(
        all_train_records, seed=cfg["seed"], val_track_fraction=cfg["val_track_fraction"])
    print(f"train-proper: {len(train_records)} images, monitoring val-slice: {len(val_records)} images")

    train_ds = make_dataset(train_records, cfg["batch_size"], shuffle=True,
                             seed=cfg["seed"], multi_exit=multi_exit)
    val_ds = make_dataset(val_records, cfg["batch_size"], shuffle=False,
                           seed=cfg["seed"], multi_exit=multi_exit)

    model = build_and_compile(model_kind, cfg.get("exit_loss_weights", {}), cfg["learning_rate"])
    model.summary()

    param_counts = count_params_by_component(model) if multi_exit else {"total": model.count_params()}
    print("param counts:", param_counts)

    ckpt_dir = ROOT / cfg["checkpoint_dir"]
    log_dir = ROOT / cfg["log_dir"]
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    monitor_metric = "val_exit3_acc" if multi_exit else "val_acc"
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(ckpt_dir / "best.weights.h5"),
            save_weights_only=True, save_best_only=True,
            monitor=monitor_metric, mode="max", verbose=1),
        tf.keras.callbacks.CSVLogger(str(log_dir / "history.csv")),
    ]
    if multi_exit:
        callbacks.append(MaxOfMinCheckpoint(str(ckpt_dir / "best_joint.weights.h5")))

    history = model.fit(train_ds, validation_data=val_ds, epochs=cfg["epochs"], callbacks=callbacks)

    model.save_weights(str(ckpt_dir / "final.weights.h5"))

    # Final per-exit accuracy table (val-slice-of-train, per the brief).
    eval_results = model.evaluate(val_ds, return_dict=True)
    print("\nFinal evaluation on monitoring val-slice:")
    print(json.dumps(eval_results, indent=2))

    summary = {
        "config": args.config,
        "model_kind": model_kind,
        "param_counts": param_counts,
        "n_train_proper": len(train_records),
        "n_val_slice": len(val_records),
        "final_eval": eval_results,
        "epochs_trained": len(history.history.get("loss", [])),
    }
    with open(log_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nwrote {log_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
