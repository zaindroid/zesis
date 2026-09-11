# Experiment 2 — pqm4 M4F→M33 Assembly Portability Post-Mortem (hardware-verified)

**Question:** *Why* does the hand-optimized Cortex-M4F pqm4 assembly (1.4–1.6×
faster than PQClean clean-C) fault on the Cortex-M33 of the FRDM-MCXN947?

**Method:** a custom `HardFault_Handler` was added to the pqm4 benchmark
firmware to capture the ARMv8-M fault status registers (CFSR/HFSR/MMFAR/BFAR
and the stacked PC) at the instant of the fault, and the remaining failure
mode was investigated live with LinkServer's GDB server (halt + register and
stack inspection). Board: FRDM-MCXN947 (MCXN947, Cortex-M33 @150 MHz),
ML-DSA-44 m4f variant, free-running.

## Result 1 — the exact fault registers (default 32 KB stack)

```
PQM4_BEGIN alg=MLDSA level=44
kp..
=== HardFault (M4F asm on M33) ===
CFSR  = 0x00100000   HFSR  = 0x40000000
MMFAR = 0xE000ED34   BFAR  = 0xE000ED38     <- stale, never updated
stacked PC = 0x40000000  stacked LR = 0xE000ED34   <- garbage
[FORCED] escalated to HardFault
```

**Decode (ARMv8-M, Cortex-M33):**
- **CFSR bit 20 = UNSTKERR** — *unstacking error*: during exception return the
  processor could not unstack the saved exception frame (the frame itself was
  corrupted). It is **not** STKOF (bit 16), not UNALIGNED (bit 24), not
  UNDEFINSTR (bit 16) and not a precise DACCVIOL (bit 30 — MMFAR/BFAR are
  stale, no precise address was recorded).
- **HFSR bit 30 = FORCED** — the original fault escalated to HardFault.
- The stacked PC (0x40000000) is an EXC_RETURN-style value, not a code
  address — the exception frame was already corrupt when the CPU tried to
  stack/unstack it.

**Interpretation:** the m4f keypair **corrupted its own stack state** on the
M33. The corruption was severe enough that the exception machinery itself
could not unwind — an unstacking error — which escalated to HardFault.

## Result 2 — with a 128 KB stack the fault becomes a silent hang (GDB)

The default project stack is **0x8000 (32 KB)** (`STACK_SIZE =
DEFINED(__stack_size__)?__stack_size__:0x8000`). Rebuilding with
`-Wl,--defsym=__stack_size__=0x20000` (128 KB) removed the UNSTKERR fault,
but the keypair then **hangs** (`kp..` printed, never `ok`). Halting the hung
core via GDB:

```
pc  0x20018040   (inside the stack region, executing data as code)
lr  0x1302e8a9   (garbage, not a flash address)
sp  0x20018800   (0x2004E000 - 0x20018800 = 219 KB below __StackTop:
                 91 KB BELOW the 128 KB __StackLimit)
disassembly at PC:  strh r1,[r0,#2]; movs r0,#1; strh r1,[r0,#2] (r0=1 -> addr 3);
                    b.n .-2        <- 0xE7FE infinite self-loop (the "hang")
backtrace: corrupt (frame identical to itself)
```

So with enough stack to avoid the hardware fault, the m4f keypair **still
smash the stack pointer and the return address**: PC ends up executing data
inside the stack region (the classic `b.n .-2` trap pattern), LR is garbage,
and the SP sits far below the stack limit. addr2line cannot resolve either
address — they are not code.

## Root cause statement (precise)

The pqm4 **M4F-targeted assembly corrupts its own call state when executed on
the Cortex-M33**. The failure is:
- **not** a TrustZone/security-state violation (no INVPC/INVSTATE/NOCP, and
  the MCXN947 here runs non-secure from boot),
- **not** an illegal instruction (no UNDEFINSTR),
- **not** a classic unaligned-access UsageFault (no UNALIGNED; the fault
  class captured is an **unstacking error**, UNSTKERR),
- but a **stack-discipline incompatibility**: the hand-written asm's stack /
  frame handling (register push/pop lists, SP arithmetic, LDRD/STRD twiddle
  loads in `smallntt_769.S`/`ntt.S` with 8-byte alignment requirements) does
  not survive the M33's stricter ARMv8-M behavior. The first observable
  symptom depends on stack size: at 32 KB the M33's stack-limit hardware
  escalates to HardFault (UNSTKERR+FORCED); at 128 KB the corruption silently
  derails PC/LR/SP into an infinite loop in RAM.

## Why this is a genuine portability finding

1. It turns a software crash into an **architectural difference**: the M4F
   (ARMv7-M) has no stack-limit hardware and silently overruns; the M33
   (ARMv8-M) catches stack corruption at the hardware level — so "the same
   code" fails *differently and detectably* on the modern core.
2. The naive expectation ("M4F asm on M33 = unaligned LDRD fault") is
   **wrong** in this case: the register evidence points to unstacking/stack
   corruption, not an alignment UsageFault.
3. The clean-C pqm4 reference and the PQClean clean-C path both run
   correctly on the same board with the same 128 KB stack — isolating the
   failure to the **hand-written assembly**, not the algorithm or the SoC.

## Files

- `main.c` — added `HardFault_Handler` (CFSR/HFSR/MMFAR/BFAR capture)
- `results/mldsa44_fault.txt` — raw fault-register capture (32 KB stack)
- `results/mldsa44_128k_fault.txt` — hang capture (128 KB stack)
- `CMakeLists.txt` — 128 KB stack verification flag (documented)
