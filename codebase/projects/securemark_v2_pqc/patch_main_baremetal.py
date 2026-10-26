#!/usr/bin/env python3
"""Patch the SecureMark-V2 self-hosted main.c for bare-metal Cortex-M33.

Replaces the POSIX clock_gettime timestamp with the DWT cycle counter (64-bit
accumulator so the 32-bit CYCCNT wrap at ~28.6 s cannot corrupt a delta), and
adds a constructor that brings up the board and the cycle counter before main().
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.abspath(os.path.join(
    HERE, "..", "..", "securemark-v2", "examples", "selfhosted", "main.c"))

s = open(P, "rb").read().replace(b"\r\n", b"\n").decode("utf-8")

if "EE_BAREMETAL_DWT" in s:
    print("already patched")
    raise SystemExit(0)

# 1) includes + constructor
inc = '#include "ee_main.h"'
assert inc in s
s = s.replace(inc, inc + '\n#include "board.h"\n#include "dwt.h"', 1)

ctor = r'''
/* Bare-metal bring-up: board clocks/console and the DWT cycle counter must be
   live before the harness runs. A constructor runs before main(). */
__attribute__((constructor)) static void ee_baremetal_init(void)
{
    BOARD_InitHardware();
    dwt_init();
}
'''
s = s.replace(inc + '\n#include "board.h"\n#include "dwt.h"',
              inc + '\n#include "board.h"\n#include "dwt.h"\n' + ctor, 1)

# 2) DWT timestamp
old = '''#else
#error "Operating system not recognized"
#endif
    return elapsedMicroSeconds;
}'''
new = '''#else /* EE_BAREMETAL_DWT */
    /* Bare metal (Cortex-M33 @150 MHz): DWT->CYCCNT, 64-bit accumulator so the
       32-bit cycle counter wrapping every ~28.6 s cannot corrupt a delta. */
    static uint64_t s_us_total = 0;
    static uint32_t s_last_cyc = 0;
    static int      s_first    = 1;
    uint32_t        cyc        = DWT->CYCCNT;

    if (s_first)
    {
        s_last_cyc = cyc;
        s_first    = 0;
    }
    else
    {
        uint32_t delta = cyc - s_last_cyc;
        s_last_cyc     = cyc;
        s_us_total += ((uint64_t)delta * 1000000ull) / 150000000ull;
    }
    elapsedMicroSeconds = s_us_total;
#endif
    return elapsedMicroSeconds;
}'''
assert old in s, "th_timestamp tail not found"
s = s.replace(old, new, 1)

open(P, "w", encoding="utf-8", newline="\n").write(s)
print("main.c bare-metal patch applied")
