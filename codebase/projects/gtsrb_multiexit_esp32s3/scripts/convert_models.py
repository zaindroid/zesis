"""Convert the three INT8 TFLite segment models to C arrays for the
ESP32-S3 TFLite Micro project.

The *_int8.tflite files are the EXACT models the frozen four-way certification
was computed on (tau thresholds 0.858/0.723/0.402/0.912 derived from PC TFLite
inference). TFLite Micro on ESP32-S3 preserves the INT8 arithmetic, so the
certified menu transfers cleanly -- this is the whole point of the port.
"""
import sys
from pathlib import Path

SRC = Path("H:/z_thesis/codebase/projects/gtsrb_policy_singlecore/tools/generated")
DST = Path("H:/z_thesis/codebase/projects/gtsrb_multiexit_esp32s3/main/models")


def to_c_array(data: bytes, name: str) -> str:
    lines = [f"// Auto-generated from {name}.tflite", f"const unsigned char {name}_tflite[] = {{"]
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        lines.append("  " + ",".join(f"0x{b:02x}" for b in chunk) + ",")
    lines.append("};")
    lines.append(f"const unsigned int {name}_tflite_len = {len(data)};")
    return "\n".join(lines)


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    for seg in ["segA", "segB", "segC"]:
        src = SRC / f"{seg}_int8.tflite"
        if not src.exists():
            print(f"MISSING {src}")
            sys.exit(1)
        data = src.read_bytes()
        out = DST / f"{seg}_model_data.h"
        out.write_text(to_c_array(data, seg), encoding="utf-8")
        print(f"{seg}: {len(data)} bytes -> {out.name}")


if __name__ == "__main__":
    main()
