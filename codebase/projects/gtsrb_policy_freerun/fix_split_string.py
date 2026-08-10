#!/usr/bin/env python3
"""Fix the broken PRINTF string in split_inference.cpp.
The string literal contains a REAL CRLF (0x0D 0x0A) where the escape
sequence \\r\\n should be (0x5C 0x72 0x5C 0x6E). Fix by replacing those
two bytes with the four escape bytes.
"""
p = r"H:\z_thesis\codebase\projects\gtsrb_policy_freerun\split_inference.cpp"
with open(p, "rb") as f:
    s = f.read()

# Find the dbg PRINTF and the exact broken region
i = s.find(b"dbg frame")
assert i >= 0, "dbg frame not found"
seg = s[i:i + 120]
print("before:", seg.hex(" "))

# The broken string: ...dec=%u<0D 0A>", i, ok, ...
# Replace the real CRLF inside the quotes with the literal escape chars
target = b'dec=%u\r\n", i, ok'
repl = b'dec=%u\\r\\n", i, ok'   # literal backslash-r backslash-n (5C 72 5C 6E)
assert target in s, "target CRLF pattern not found"
s = s.replace(target, repl, 1)
with open(p, "wb") as f:
    f.write(s)

i = s.find(b"dbg frame")
print("after :", s[i:i + 120].hex(" "))
print("OK")
