#!/usr/bin/env python3
"""Evaluate a SecureMark-V2 + PQC harness capture (Task 4)."""
import csv
import os
import re
import sys

PQC_CRC = {
    "kem512_enc":    0xBB6188B7,
    "kem768_enc":    0x8A48D4A5,
    "kem1024_enc":   0xFDB3B688,
    "dsa44_sign":    0xBA561067,
    "dsa65_sign":    0x1EE8F069,
    "dsa87_sign":    0xAB6329B9,
    "hashdsa65_sign": 0x9C084B80,
}

raw = sys.argv[1]
text = open(raw, "rb").read().replace(b"\x00", b"").decode("utf-8", "replace")

# component lines look like: "  7 PQC_All           kem1024_kp    [pqc] crc32=... self-check=PASS"
# followed by the ips on the next line.
# Two line shapes in the capture:
#   PQC      : "<n> <suite> <comp>  [pqc] crc32=0x... self-check=PASS"  then "<ips>"
#   classical: "<n> <suite> <comp>  <ips>"                              (same line)
comp_re = re.compile(
    r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(?:\[pqc\] crc32=0x([0-9a-f]+) self-check=(\w+))?\s*$")
comp_val_re = re.compile(
    r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+([0-9]+\.[0-9]+)\s*$")
val_re = re.compile(r"^\s*([0-9]+\.[0-9]+)\s*$")

entries = []
classical = []
pending = None
crc_seen = {}
for line in text.splitlines():
    mv = comp_val_re.match(line)          # classical: ips on the same line
    if mv:
        suite = mv.group(2)
        if suite != "PQC_All":
            classical.append({"suite": suite, "name": mv.group(3),
                              "ips": float(mv.group(4))})
        pending = None
        continue
    m = comp_re.match(line)
    if m and m.group(2) == "PQC_All":
        pending = {"n": int(m.group(1)), "name": m.group(3),
                   "crc32": m.group(4), "check": m.group(5)}
        continue
    v = val_re.match(line)
    if v and pending is not None:
        pending["ips"] = float(v.group(1))
        entries.append(pending)
        if pending["crc32"]:
            crc_seen[pending["name"]] = int(pending["crc32"], 16)
        pending = None

if not entries:
    print("no PQC_All components found in", raw)
    raise SystemExit(1)

# ---- validation ----
print("PQC components found:", len(entries))
bad = [e for e in entries if e.get("check") not in (None, "PASS")]
print("self-check failures:", len(bad))
for name, exp in PQC_CRC.items():
    got = crc_seen.get(name)
    status = "MATCH" if got == exp else ("MISSING" if got is None else "MISMATCH")
    if got is not None:
        print(f"  CRC {name:16s} got 0x{got:08X} expected 0x{exp:08X}  {status}")

# ---- scores ----
def score(comps):
    tot = 0.0
    for c in comps:
        tot += c["w"] / c["ips"]
    return 1000.0 / tot if tot > 0 else 0.0

for e in entries:
    e["w"] = 1.0
s_equal = score(entries)

by = {e["name"]: e for e in entries}
proto_names = ["kem768_enc", "kem768_dec", "dsa65_sign", "dsa65_ver"]
if all(n in by for n in proto_names):
    proto = [{"w": 0.25, "ips": by[n]["ips"]} for n in proto_names]
    s_proto = score(proto)
else:
    s_proto = float("nan")

print()
print(f"PQC_All  (equal weight, {len(entries)} components) : {s_equal:12.3f}")
print(f"PQC_TLS1.3 (protocol weighted, 768/65)            : {s_proto:12.3f}")

# ---- CSV ----
out = os.path.join(os.path.dirname(raw), "..", "raw", "SECUREMARK_V2_PQC_SUMMARY.csv")
out = os.path.abspath(out)
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["component", "ips", "regression_crc32", "self_check"])
    for e in sorted(entries, key=lambda x: x["n"]):
        w.writerow([e["name"], f"{e['ips']:.3f}",
                    f"0x{e['crc32']}" if e["crc32"] else "", e.get("check", "")])
    w.writerow([])
    w.writerow(["PQC_All_score", f"{s_equal:.3f}"])
    w.writerow(["PQC_TLS13_score", f"{s_proto:.3f}"])
print("wrote", out)
