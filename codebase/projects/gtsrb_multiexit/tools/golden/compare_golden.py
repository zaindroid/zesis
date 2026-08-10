"""
Compares the board's UART-dumped GOLDEN lines against the PC-computed
reference (golden_reference.txt, from gen_golden.py).

Usage: python tools/golden/compare_golden.py <path_to_board_capture.txt>
"""
import re
import sys

HERE = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]


def _to_int32(v: int) -> int:
    # Board PRINTF("%d", (int)int8_value) prints negative int8 values as
    # their uint32 two's-complement bit pattern (fsl_debug_console's
    # lightweight printf does not sign-extend %d correctly here) -- decode
    # back to a signed value before comparing against the PC reference.
    if v >= 2**31:
        v -= 2**32
    return v


def parse_board_capture(path: str) -> dict:
    result = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            m = re.match(r"GOLDEN (\w+): \[(.*)\]", line)
            if m:
                key, values = m.groups()
                result[key] = [_to_int32(int(v)) for v in values.split(",") if v.strip()]
    return result


def parse_reference(path: str) -> dict:
    result = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith("["):
                result[key] = eval(value)
            else:
                result[key] = int(value)
    return result


def main():
    if len(sys.argv) != 2:
        print("usage: python compare_golden.py <board_capture.txt>")
        sys.exit(1)

    board = parse_board_capture(sys.argv[1])
    ref = parse_reference(HERE + "/golden_reference.txt")

    pairs = [
        ("exit1_logits_int8", "exit1_logits_int8"),
        ("block3_features_int8_first10", "block3_features_int8_first10"),
        ("exit2_logits_int8", "exit2_logits_int8"),
        ("block6_features_int8_first10", "block6_features_int8_first10"),
        ("exit3_logits_int8", "exit3_logits_int8"),
    ]

    TOLERANCE = 3  # LSBs; see Microcode version mismatch warning in boot log

    all_bitexact = True
    all_within_tol = True
    for board_key, ref_key in pairs:
        board_vals = board.get(board_key)
        ref_vals = ref.get(ref_key)
        if board_vals is None:
            print(f"MISSING on board: {board_key}")
            all_bitexact = False
            all_within_tol = False
            continue
        if board_vals == ref_vals:
            print(f"BIT-EXACT MATCH  {board_key}: {board_vals}")
            continue
        all_bitexact = False
        diffs = [b - r for b, r in zip(board_vals, ref_vals)]
        max_abs_diff = max(abs(d) for d in diffs)
        within_tol = max_abs_diff <= TOLERANCE
        all_within_tol = all_within_tol and within_tol
        tag = f"CLOSE (max |diff|={max_abs_diff} LSB)" if within_tol else f"MISMATCH (max |diff|={max_abs_diff} LSB)"
        print(f"{tag}  {board_key}:")
        print(f"  board: {board_vals}")
        print(f"  ref:   {ref_vals}")
        print(f"  diff:  {diffs}")

    # Decision-level check: does the predicted class (argmax) still match?
    print()
    argmax_ok = True
    for board_key, ref_key, ref_argmax_key in [
        ("exit1_logits_int8", "exit1_logits_int8", "exit1_argmax"),
        ("exit2_logits_int8", "exit2_logits_int8", "exit2_argmax"),
        ("exit3_logits_int8", "exit3_logits_int8", "exit3_argmax"),
    ]:
        board_vals = board.get(board_key)
        if board_vals is None:
            continue
        board_argmax = board_vals.index(max(board_vals))
        ref_argmax = ref.get(ref_argmax_key)
        ok = board_argmax == ref_argmax == ref.get("true_label")
        argmax_ok = argmax_ok and ok
        print(f"{'OK  ' if ok else 'FAIL'} {board_key}: board argmax={board_argmax}, "
              f"ref argmax={ref_argmax}, true_label={ref.get('true_label')}")

    print()
    if all_bitexact:
        print("GOLDEN-INPUT CHECK: PASS -- PC INT8 logits == board INT8 logits, bit-exact.")
    elif all_within_tol and argmax_ok:
        print(f"GOLDEN-INPUT CHECK: PASS WITH TOLERANCE -- not bit-exact (<= {TOLERANCE} LSB drift, "
              f"consistent with the on-board Neutron driver/converter microcode version mismatch "
              f"reported at boot), but every exit's predicted class matches the PC reference and "
              f"the true label.")
    else:
        print("GOLDEN-INPUT CHECK: FAIL -- mismatches exceed tolerance or predicted class diverged.")
    sys.exit(0 if (all_bitexact or (all_within_tol and argmax_ok)) else 1)


if __name__ == "__main__":
    main()
