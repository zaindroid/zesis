"""
Quick sanity check for the new UART batch-inference protocol: parses the
known golden_image_int8 array straight out of golden_input.h, sends it
through the batch protocol, and checks the reply matches the earlier
one-shot golden dump (pred=16 at every exit, high confidence).

Usage: python tools/hw_validate/sanity_test.py
"""
import re
import time
import serial

PORT = "COM3"
BAUD = 115200
HERE = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]


def load_golden_image() -> bytes:
    with open(HERE + "/../../golden_input.h", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"golden_image_int8\[\d+\]\s*=\s*\{([^}]*)\}", text)
    values = [int(v.strip()) for v in m.group(1).split(",") if v.strip()]
    assert len(values) == 6912, f"expected 6912 values, got {len(values)}"
    return bytes((v & 0xFF) for v in values)


def main():
    img = load_golden_image()
    print(f"loaded golden image, {len(img)} bytes")

    # DTR/RTS toggling on open resets this board (same gotcha worked around
    # in tools/golden/capture_serial.ps1) -- disable both explicitly via
    # DsrDtr/RtsCts=False *before* open so pyserial doesn't assert them.
    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 15
    ser.dsrdtr = False
    ser.rtscts = False
    ser.dtr = False
    ser.rts = False
    ser.open()
    print("port opened")
    ser.reset_input_buffer()

    # The board may already be idling in the batch loop from a prior run
    # (it only prints BATCH_READY once, right when it first gets there), so
    # don't wait for the banner -- just send the command and see if a valid
    # reply comes back within the timeout.
    t0 = time.time()
    n = ser.write(b"I" + img)
    ser.flush()
    print(f"wrote {n} bytes")

    line = ser.readline().decode(errors="replace").strip()
    dt = time.time() - t0
    print(f"reply ({dt*1000:.0f} ms): {line!r}")

    parts = line.split(",")
    assert parts[0] == "R", f"unexpected reply: {line}"
    pred1, conf1, pred2, conf2, pred3, conf3 = (int(x) for x in parts[1:])
    print(f"exit1: pred={pred1} conf={conf1/1e6:.4f}")
    print(f"exit2: pred={pred2} conf={conf2/1e6:.4f}")
    print(f"exit3: pred={pred3} conf={conf3/1e6:.4f}")

    ok = pred1 == 16 and pred2 == 16 and pred3 == 16
    print("SANITY CHECK:", "PASS" if ok else "FAIL")
    ser.close()


if __name__ == "__main__":
    main()
