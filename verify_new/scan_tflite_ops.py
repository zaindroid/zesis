"""Minimal TFLite flatbuffer op scanner (no TF needed).
Rough heuristic: builtin op enum bytes appear in the opcodes table.
Good enough to confirm the segment models only use ops TFLite Micro supports.
"""
import os

OP_NAMES = {
    3: 'CONV_2D', 8: 'DEPTHWISE_CONV_2D', 0: 'ADD', 15: 'MUL', 6: 'RELU',
    21: 'RELU6', 9: 'FULLY_CONNECTED', 13: 'SOFTMAX', 5: 'RESHAPE',
    41: 'MEAN', 38: 'PAD', 17: 'MAX_POOL_2D', 18: 'AVERAGE_POOL_2D',
    60: 'QUANTIZE', 54: 'DEQUANTIZE', 22: 'TANH', 16: 'SUB', 46: 'STRIDED_SLICE',
    62: 'LOGISTIC', 43: 'SPLIT', 40: 'CONCATENATION', 20: 'MUL'}


def parse_tflite(path: str) -> None:
    data = open(path, 'rb').read()
    assert data[4:8] == b'TFL3', f"{path}: bad magic {data[4:8]!r}"
    found = []
    for op, name in OP_NAMES.items():
        c = data.count(bytes([op]))
        if c > 0:
            found.append((name, c))
    print(os.path.basename(path), f'size={len(data)}')
    print('  op byte-counts (rough heuristic):', found)


def main() -> None:
    for seg in ['segA', 'segB', 'segC']:
        p = f'H:/z_thesis/codebase/projects/gtsrb_policy_singlecore/tools/generated/{seg}_int8.tflite'
        if os.path.exists(p):
            parse_tflite(p)
        else:
            print(f'{p} missing')


if __name__ == '__main__':
    main()
