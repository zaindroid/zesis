"""
Host driver for the ESP32-S3 multi-exit benchmark.

Streams the frozen 1200-image natural-frequency workload (the same
workload.bin used for the NXP free-running design) to the board over the
USB-serial console, collects the per-frame result rows, and writes a CSV
identical in schema to the NXP policy_results_*.csv so the same analysis
scripts can compare platforms directly.

Protocol (see main.cpp RunBatch):
  host -> 'I' + 6912 raw INT8 bytes   (frame)
  board -> "R,crypto_us,frame_us,exit_taken,tier_used,pred1,conf1,"
           "pred2,conf2,pred3,conf3\r\n"
  host -> 'Q' ends the batch.

Usage:
  python run_esp32_experiment.py --port COM11 --policy naive \
      --out results/policy_results_esp32_naive.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import time

import serial

IMAGE_BYTES = 6912


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--policy", required=True, choices=["naive", "static", "adaptive"])
    ap.add_argument("--workload", default="H:/z_thesis/codebase/projects/gtsrb_policy_freerun/tools/hw_freerun/workload.bin")
    ap.add_argument("--manifest", default="H:/z_thesis/codebase/projects/gtsrb_policy_freerun/tools/hw_freerun/workload_manifest.csv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--n-frames", type=int, default=1200)
    args = ap.parse_args()

    blob = open(args.workload, "rb").read()
    blob = blob[:args.n_frames * IMAGE_BYTES]

    with open(args.manifest, newline="") as f:
        manifest = list(csv.DictReader(f))
    manifest = manifest[:args.n_frames]

    ser = serial.Serial(args.port, args.baud, timeout=60)
    time.sleep(1.0)
    ser.reset_input_buffer()
    # consume banner
    ser.read(400)

    print(f"policy={args.policy} n={args.n_frames} frames")
    t_start = time.time()
    rows = []
    for i in range(args.n_frames):
        img = blob[i * IMAGE_BYTES:(i + 1) * IMAGE_BYTES]
        ser.write(b"I" + img)
        line = ser.readline()
        if not line.startswith(b"R,"):
            print(f"frame {i}: unexpected: {line[:80]!r}")
            continue
        parts = line.decode(errors="replace").strip().split(",")
        crypto_us, frame_us, exit_taken, tier_used, p1, c1, p2, c2, p3, c3 = parts[1:]
        m = manifest[i]
        rows.append({
            "idx": i,
            "filename": m["path"].split("/")[-1],
            "label": m["label"],
            "is_safety_critical": m["is_safety_critical"],
            "crypto_us": crypto_us,
            "frame_us": frame_us,
            "img_read_us": 0,
            "exit_taken": exit_taken,
            "tier_used": tier_used,
            "pred1": p1, "conf1": c1,
            "pred2": p2, "conf2": c2,
            "pred3": p3, "conf3": c3,
        })
        if (i + 1) % 100 == 0:
            el = time.time() - t_start
            print(f"  {i+1}/{args.n_frames} frames, {el:.0f}s elapsed")

    ser.write(b"Q")
    time.sleep(0.3)
    ser.close()

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    elapsed = time.time() - t_start
    print(f"wrote {args.out}: {len(rows)} rows in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
