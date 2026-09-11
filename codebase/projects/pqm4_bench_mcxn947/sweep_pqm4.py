#!/usr/bin/env python3
"""Sweep pqm4 m4f variants on MCXN947: build->flash->capture->parse.

Usage: python sweep_pqm4.py
Each config is (ALG, LEVEL, VARIANT, REPS). Build uses cmake preset debug.
"""
import subprocess, serial, time, re, os, sys

ENV = dict(os.environ)
ENV["ARMGCC_DIR"] = "C:/Users/zain_/.mcuxpressotools/arm-gnu-toolchain-14.2.rel1-mingw-w64-x86_64-arm-none-eabi"
ENV["PATH"] = "C:/Users/zain_/.mcuxpressotools/arm-gnu-toolchain-14.2.rel1-mingw-w64-x86_64-arm-none-eabi/bin;" + ENV.get("PATH", "")
SDK = "h:/z_thesis/codebase/sdk/mcuxsdk/mcuxsdk"
LS = "C:/nxp/LinkServer_26.6.137/LinkServer.exe"
PORT = "COM9"
PROBE = "0V5USKFHVAZTY"
PROJ = "H:/z_thesis/codebase/projects/pqm4_bench_mcxn947"
BIN = f"{PROJ}/debug/pqm4_bench_mcxn947_cm33_core0.bin"

CONFIGS = [
    ("MLKEM", "1024", "m4fspeed"),
    ("MLKEM", "1024", "m4fstack"),
    ("MLDSA", "44",   "m4f"),
    ("MLDSA", "65",   "m4f"),
    ("MLDSA", "87",   "m4f"),
]

def run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)

def build(alg, level, variant):
    cmds = [
        ["cmake", "--preset", "debug", "-DALG="+alg, "-DLEVEL="+level,
         "-DVARIANT="+variant, "-DREPS=1", "-DSdkRootDirPath="+SDK],
        ["cmake", "--build", "debug"],
    ]
    for c in cmds:
        rc, out = run(c)
        if rc != 0:
            errs = [l for l in out.splitlines() if "error" in l.lower()][:3]
            print(f"BUILD FAIL {alg}-{level}-{variant}: {errs}")
            return False
    return True

def flash():
    rc, out = run([LS, "flash", "-p", PROBE, "auto", "load", f"{BIN}:0x00000000"])
    return rc == 0

def capture(runs=4):
    """reset-board capture; return list of (kp_cycles, enc_cycles, sig_cycles, vfy_cycles)."""
    out_rows = []
    for r in range(runs):
        ser = serial.Serial(PORT, 115200, timeout=2)
        ser.reset_input_buffer()
        subprocess.run([LS, "probe", PROBE, "wiretimedreset", "100"], capture_output=True)
        buf = bytearray(); t0 = time.time()
        while time.time() - t0 < 25:
            ch = ser.read(8192)
            if ch: buf += ch
            if b"PQM4_END" in buf: break
        ser.close()
        text = buf.decode(errors="replace")
        kp = re.findall(r"kp,(\d+)", text)
        enc = re.findall(r"enc,(\d+)", text)
        sg = re.findall(r"sign,(\d+)", text)
        vf = re.findall(r"vrfy,(\d+)", text)
        if kp or sg:
            out_rows.append((int(kp[0]) if kp else None,
                             int(enc[0]) if enc else None,
                             int(sg[0]) if sg else None,
                             int(vf[0]) if vf else None))
        else:
            out_rows.append(None)
    return out_rows

def main():
    results = {}
    for alg, level, variant in CONFIGS:
        print(f"\n=== {alg}-{level} {variant} ===")
        if not build(alg, level, variant):
            results[f"{alg}-{level}"] = "BUILD FAIL"
            continue
        if not flash():
            print("  FLASH FAIL")
            results[f"{alg}-{level}"] = "FLASH FAIL"
            continue
        rows = capture(4)
        ok = [r for r in rows if r]
        if not ok:
            results[f"{alg}-{level}"] = "NO COMPLETE RUN (fault/hang)"
            print("  NO COMPLETE RUN")
            continue
        # average the first complete run
        kp = [r[0] for r in ok if r[0]]
        enc = [r[1] for r in ok if r[1]]
        sg = [r[2] for r in ok if r[2]]
        vf = [r[3] for r in ok if r[3]]
        line = f"  complete={len(ok)}/{len(rows)}"
        if kp: line += f" kp={sum(kp)/len(kp):,.0f} ({sum(kp)/len(kp)/1.5e6:.2f}ms)"
        if enc: line += f" enc={sum(enc)/len(enc):,.0f} ({sum(enc)/len(enc)/1.5e6:.2f}ms)"
        if sg: line += f" sign={sum(sg)/len(sg):,.0f} ({sum(sg)/len(sg)/1.5e6:.2f}ms)"
        if vf: line += f" vrfy={sum(vf)/len(vf):,.0f} ({sum(vf)/len(vf)/1.5e6:.2f}ms)"
        print(line)
        results[f"{alg}-{level}"] = {
            "kp_mean": sum(kp)/len(kp) if kp else None,
            "enc_mean": sum(enc)/len(enc) if enc else None,
            "sign_mean": sum(sg)/len(sg) if sg else None,
            "vrfy_mean": sum(vf)/len(vf) if vf else None,
            "complete_runs": len(ok),
        }
    import json
    open("results/pqm4_sweep_results.json", "w").write(json.dumps(results, indent=2))
    print("\nSaved results/pqm4_sweep_results.json")

if __name__ == "__main__":
    main()
