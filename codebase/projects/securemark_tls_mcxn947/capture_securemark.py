#!/usr/bin/env python3
"""Capture SecureMark-TLS serial output continuously until 'Score is' appears or timeout."""
import serial, time, subprocess, sys

PORT = 'COM9'
TIMEOUT_S = 1200  # 20 min
OUT = r'H:\z_thesis\codebase\projects\securemark_tls_mcxn947\results\securemark_selfhosted_raw.txt'

# open serial first (avoid the flash auto-restart race)
ser = serial.Serial(PORT, 115200, timeout=1)
ser.reset_input_buffer()
print(f'[{time.strftime("%H:%M:%S")}] serial open, resetting board...', flush=True)
subprocess.run(['C:/nxp/LinkServer_26.6.137/LinkServer.exe', 'probe', '0V5USKFHVAZTY', 'wiretimedreset', '100'],
               capture_output=True)

buf = bytearray()
t0 = time.time()
with open(OUT, 'wb') as f:
    while time.time() - t0 < TIMEOUT_S:
        try:
            ch = ser.read(8192)
        except Exception:
            break
        if ch:
            buf += ch
            f.write(ch)
            f.flush()
        if b'Score is' in buf:
            break
        # progress heartbeat every 60s
        if int(time.time() - t0) % 60 == 0:
            print(f'[{time.strftime("%H:%M:%S")}] {len(buf)} bytes, components: {buf.count(b"Component #")}', flush=True)
            time.sleep(1)  # avoid spamming
ser.close()

text = buf.decode(errors='replace')
lines = [l for l in text.splitlines() if l.strip()]
print(f'DONE: bytes={len(buf)} lines={len(lines)} score={"Score is" in text}', flush=True)
i = text.find('Component #')
if i >= 0:
    print(text[i:i+2600], flush=True)
else:
    print('no score section; tail:', repr(text[-250:]), flush=True)
