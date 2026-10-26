#!/usr/bin/env python3
"""Capture a board's serial run to a file until BENCH_COMPLETE or timeout.

Usage: python capture_serial.py <port> <outfile> [timeout_s] [done_marker]
"""
import sys
import time
import serial

port = sys.argv[1]
outfile = sys.argv[2]
timeout_s = int(sys.argv[3]) if len(sys.argv) > 3 else 300
marker = sys.argv[4] if len(sys.argv) > 4 else "BENCH_COMPLETE"

ser = serial.Serial(port, 115200, timeout=0.5)
buf = bytearray()
t0 = time.time()
with open(outfile, "wb") as f:
    while time.time() - t0 < timeout_s:
        chunk = ser.read(8192)
        if chunk:
            f.write(chunk)
            f.flush()
            buf += chunk
            if marker.encode() in buf:
                break
ser.close()
print(f"captured {len(buf)} bytes in {time.time()-t0:.0f}s -> {outfile}")
print("complete:", marker.encode() in buf)
