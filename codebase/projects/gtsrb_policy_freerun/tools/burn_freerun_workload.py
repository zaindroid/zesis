"""
One-time burn of the free-running workload blob to the board's external
W25Q64 QSPI flash via the FREERUN_PROGRAM firmware.

Protocol (matches BurnWorkload() in gtsrb_policy_freerun/main.cpp):
  board prints BURN_READY
  host -> 'B'                     start
  board -> 'R'                    ready
  loop sectors 0..2024:
    host -> 4-byte LE sector idx + 4096 bytes
    board erases + page-programs + verifies; board -> 'K' or 'N'+stage
    (stage: 0=erase 1=program 2=verify -- the last stage attempted)
    host retries a failed sector up to 3 attempts
  host -> 'E'                     end
  board -> 'D' + 4-byte LE total + BURN_DONE

Run:  python burn_freerun_workload.py --port COM9 --blob workload.bin
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time

import serial


def read_until(ser: serial.Serial, token: bytes, timeout: float = 30.0) -> bytes:
    buf = b""
    t0 = time.time()
    while token not in buf:
        if time.time() - t0 > timeout:
            raise TimeoutError(f"timed out waiting for {token!r}; got {buf[-80:]!r}")
        chunk = ser.read(max(1, ser.in_waiting))
        if chunk:
            buf += chunk
    return buf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="board VCOM, e.g. COM9")
    ap.add_argument("--blob", required=True, help="path to workload.bin")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--sector-size", type=int, default=4096)
    ap.add_argument("--max-retries", type=int, default=3)
    args = ap.parse_args()

    blob = open(args.blob, "rb").read()
    n_sectors = len(blob) // args.sector_size
    assert len(blob) % args.sector_size == 0, "blob must be sector-aligned"
    print(f"blob: {len(blob)} bytes = {n_sectors} sectors of {args.sector_size}")
    print(f"SHA-256(blob) = {hashlib.sha256(blob).hexdigest()}")

    FAIL_STAGE = {0: "erase", 1: "program", 2: "verify"}

    ser = serial.Serial(args.port, args.baud, timeout=0.5)
    ser.reset_input_buffer()
    time.sleep(0.2)

    # Wait for BURN_READY (firmware already flashed and reset). Best-effort:
    # if it was already consumed by an earlier port open, proceed anyway --
    # the board is waiting for 'B' regardless.
    print("waiting for BURN_READY ...")
    try:
        read_until(ser, b"BURN_READY", timeout=5.0)
        print("BURN_READY received")
    except TimeoutError:
        print("BURN_READY not seen (may already have been consumed); sending 'B' anyway")

    ser.write(b"B")
    read_until(ser, b"R", timeout=10.0)
    # Drain any trailing bytes (e.g. the \r\n after 'R') so they don't get
    # misread as the first sector's ACK -- same class of bug as the
    # BATCH_READY desync fixed in run_policy_experiment.py.
    time.sleep(0.1)
    stray = ser.read(ser.in_waiting or 1) if ser.in_waiting else b""
    if stray:
        print(f"  drained stray bytes: {stray!r}")
    print("board ready")

    t_start = time.time()
    ok_sectors = 0
    for s in range(n_sectors):
        chunk = blob[s * args.sector_size:(s + 1) * args.sector_size]
        for attempt in range(args.max_retries):
            ser.write(s.to_bytes(4, "little") + chunk)
            ack = ser.read(1)
            if ack == b"K":
                ok_sectors += 1
                break
            if ack == b"N":
                code = ser.read(1)
                stage = FAIL_STAGE.get(code[0] if code else -1, f"unknown({code!r})")
                print(f"  sector {s} attempt {attempt+1}: NAK ({stage} failed), retrying")
            else:
                print(f"  sector {s} attempt {attempt+1}: unexpected reply {ack!r}, retrying")
        else:
            print(f"  sector {s}: FAILED after {args.max_retries} attempts")
            sys.exit(1)
        if s % 200 == 0:
            el = time.time() - t_start
            print(f"  {s}/{n_sectors} sectors, {el:.0f}s elapsed")

    ser.write(b"E")
    buf = read_until(ser, b"BURN_DONE", timeout=30.0)
    total = int.from_bytes(buf[buf.index(b"D") + 1: buf.index(b"D") + 5], "little")
    print(f"board reports total = {total} bytes (expected {len(blob)})")
    if total != len(blob):
        print("MISMATCH: board total != blob length")
        sys.exit(1)

    elapsed = time.time() - t_start
    print(f"burn complete: {ok_sectors}/{n_sectors} sectors OK in {elapsed:.0f}s "
          f"({len(blob)/elapsed/1024:.0f} KB/s)")
    print("BURN_DONE")


if __name__ == "__main__":
    main()
