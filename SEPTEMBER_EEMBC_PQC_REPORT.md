# September work — EEMBC-style PQC benchmarking

**Period:** 11–18 September 2026
**Board:** FRDM-MCXN947 (MCXN947, Cortex-M33 @ 150 MHz), bare metal, no RTOS,
DWT cycle counter.
**Methodology level: `-O2` for every primitive, PQC and classical alike.**
**Backend:** wolfSSL 5.9.2, native `wc_mlkem.c` / `wc_mldsa.c`, crypto-only
(`WOLFCRYPT_ONLY`), `WOLFSSL_NO_ASM`.

This consolidates the four September reports and the result files behind them:

| Source report | Date |
|---|---|
| `securemark_v2_pqc/bench/results/STANDALONE_PQC_BENCH.md` | 16 Sep |
| `pqm4_bench_mcxn947/results/PQM4_M4F_M33_POSTMORTEM.md` | 16 Sep |
| `securemark_v2_pqc/v2harness/results/SECUREMARK_V2_PQC_REPORT.md` | 17 Sep |
| `securemark_v2_pqc/v2harness/results/SECUREMARK_V2_FINAL_REPORT.md` | 18 Sep |

---

## 1. What was built

| Component | What it is |
|---|---|
| `wolfssl-m33/` | crypto-only wolfSSL 5.9.2 cross-built for Cortex-M33 with ML-KEM + ML-DSA enabled, static pool allocator (no heap), deterministic block RNG, `-O2` |
| `bench/` | standalone PQC driver — 21 points (7 algorithms x keypair/sign-or-encaps/verify) |
| `v2harness/` | upstream EEMBC **securemark-v2** self-hosted harness, extended with 20 native PQC components registered as the `PQC_All` suite; 102 components total |
| `task3a/` | 128 KB firmware signature verification (secure-boot case) |
| `pqm4_bench_mcxn947/` | pqm4 (Cortex-M4F assembly) on the M33, with a HardFault handler capturing ARMv8-M fault registers |

The harness integration also required three fixes without which no run completes:
the classical P-384 ECDH RNG (`MISSING_RNG_E`), RSA-4096 sizing (`SP_INT_BITS`),
and a bounded autotune loop (a failing component otherwise spins forever and the
score section never prints).

---

## 2. Standalone PQC bench

wolfSSL native, single samples. This exists to establish that the primitives run
correctly and reproducibly on the target before any harness work.

| Algorithm | keypair | encaps / sign | decaps / verify | Self-check | Regression CRC |
|---|---|---|---|---|---|
| ML-KEM-512 | 17.43 ms | 14.97 ms | 20.24 ms | PASS | 0xBB6188B7 |
| ML-KEM-768 | 28.02 ms | 25.24 ms | 32.74 ms | PASS | 0x8A48D4A5 |
| ML-KEM-1024 | 44.10 ms | 40.06 ms | 49.84 ms | PASS | 0xFDB3B688 |
| ML-DSA-44 | 66.36 ms | 165.55 ms | 69.70 ms | PASS | 0xBA561067 |
| ML-DSA-65 | 113.20 ms | 198.77 ms | 115.62 ms | PASS | 0x1EE8F069 |
| ML-DSA-87 | 192.68 ms | 254.21 ms | 195.14 ms | PASS | 0xAB6329B9 |
| HashML-DSA-65 | 113.20 ms | 235.17 ms | 115.11 ms | PASS | 0x9C084B80 |

(These are the `-Os` first-pass numbers; the `-O2` values are in §5.)

**On the CRCs.** They are synthesized regression checksums over the deterministic
output buffers (ciphertext‖shared-secret for KEM, signature for DSA). No EEMBC
golden value exists for a PQC profile, so "EEMBC CRC MATCH" is never claimed for
them. `SELF-CHECK: PASS` means the round trip held — KEM decapsulation recovered
the encapsulated secret exactly; DSA verification returned valid. The checksums
reproduce across independent resets **and across optimisation levels** (`-Os` and
`-O2` give identical values), which is what makes them usable as a cross-build
invariant.

---

## 3. SecureMark-V2 score sheet (native)

Emitted by the harness itself, not reconstructed. Capture:
`v2harness/results/pqc_denoised.txt` (30-iteration PQC means).

| Suite | Score |
|---|---|
| **PQC_All** | **2042.526** |
| **PQC_TLS1.3 (768/65)** | **40177.367** |
| TLSv1.2 | 10418.526 |
| TLSv1.3_Light | 251.907 |
| Boot_Light | 70.419 |
| TLSv1.3_Med_CCM | 100.576 |
| TLSv1.3_Med_GCM | 100.162 |
| Boot_Med_RSA | 38.160 |
| Boot_Med_ECC | 24.572 |
| TLSv1.3_Heavy_CCM | 4.127 |
| TLSv1.3_Heavy_GCM | 4.124 |
| Boot_Heavy_RSA | 10.408 |
| Boot_Heavy_ECC | 1.178 |

`1000 / Σ(wᵢ/ipsᵢ)`. `PQC_All`: wᵢ = 1 over 20 per-primitive components.
`PQC_TLS1.3`: w = 0.25 over ML-KEM-768 encaps/decaps and ML-DSA-65 sign/verify.
Zero CRC errors; all 20 PQC components SELF-CHECK PASS.

**PQC components at `-O2` (30-iteration means):**

| Algorithm | keypair | encaps / sign | decaps / verify |
|---|---|---|---|
| ML-KEM-512 | 4.36 ms | 3.76 ms | 5.08 ms |
| ML-KEM-768 | 7.01 ms | 6.37 ms | 8.24 ms |
| ML-KEM-1024 | 11.07 ms | 10.14 ms | 12.56 ms |
| ML-DSA-44 | 14.50 ms | 29.18 ms | 14.53 ms |
| ML-DSA-65 | 25.13 ms | 60.36 ms | 24.57 ms |
| ML-DSA-87 | 43.24 ms | 80.22 ms | 42.42 ms |
| HashML-DSA-65 | (same as ML-DSA-65) | 55.68 ms | 24.45 ms |

---

## 4. Handshake: PQC vs classical, same library, same flags

Both sides wolfSSL at `-O2`. Public-key phase = 1 ECDH + 1 sign + 2 verifies.

| Public-key phase | Composition | Total |
|---|---|---|
| Classical P-256 | 24.34 (ECDH) + 17.57 (sign) + 2 x 26.50 (verify) | **94.91 ms** |
| PQC (ML-KEM-768 + ML-DSA-65) | 6.37 + 8.24 + 60.36 + 24.57 | **99.54 ms** |

**PQC is 4.9% more expensive than classical P-256.** The penalty is a few
percent, not the +83% an mbedTLS-based comparison at `-O2` once implied. Cost is
concentrated in signing; PQC key establishment is far cheaper than its classical
counterpart.

> Correction on the record: an earlier version of this figure read "−3.6%
> cheaper". That came from a 3-iteration ML-DSA-65 sign mean. With 30 iterations
> the sign cost rose from 52.33 to 60.36 ms and the sign flipped. The
> de-noising was worth more than the decimal places suggest.

---

## 5. Library matrix

Full data: `securemark_v2_pqc/results/PQC_LIBRARY_CONFIG_MATRIX.csv` (42 rows,
generated by `scripts/emit_library_matrix.py`).

### ML-KEM-768 encapsulation, all tiers

| Tier | Implementation | Flags | Time | Cycles |
|---|---|---|---|---|
| Reference C | PQClean clean C | -O2 | 15.33 ms | 2,299,500 |
| Embedded engine | **wolfSSL native** | **-O2** | **6.37 ms** | **955,000** |
| Hand-tuned assembly | pqm4 (Cortex-M4F asm) | -O3 | 23.99 ms | 3,598,500 |

**The expected tier ordering does not hold.** The hand-tuned assembly is the
slowest of the three: 1.6x slower than PQClean clean C at matched `-O2` and 3.8x
slower than wolfSSL's portable C. Its decapsulation and all of ML-DSA fault on
the M33, so it is not fully measurable either.

What the data supports: *a modern portable PQC implementation beat the
M4F-specific assembly, which itself is not fully portable to ARMv8-M.* Less tidy
than the expected result, but it is the measured one.

### ML-DSA-65 signing

| Implementation | Statistic | n | Time |
|---|---|---|---|
| PQClean clean C | mean | 2000 | 91.61 ms |
| PQClean clean C | median | 2000 | 74.77 ms |
| wolfSSL native | mean | 30 | 60.36 ms |

**Library effect at matched `-O2`: 1.52x (mean vs mean).** The optimisation term
is essentially nil for PQClean ML-DSA (-Os 73.72 → -O2 74.77 ms median, 1.014x),
so the gap is entirely the library.

### The assembly/SP variant does not exist for this target

`WOLFSSL_NO_ASM` reads like a choice. It is not one. wolfSSL gates its Cortex-M
SP assembly on `WOLFSSL_ARM_ARCH_7M`, auto-detected from `__ARM_ARCH_7M__`:

```c
#if defined(WOLFSSL_SP_ARM_CORTEX_M_ASM) && defined(WOLFSSL_ARM_ARCH_7M)
```

The M33 is ARMv8-M, so the gate is closed and there is no ARMv8-M path.
**Verified empirically:** removing `WOLFSSL_NO_ASM` and rebuilding produces a
byte-identical library (575,922 B). The flag was never the limiter. So the
"embedded engine" tier is portable C by necessity.

---

## 6. Optimisation sensitivity

| Quantity | `-Os` | `-O2` | factor |
|---|---|---|---|
| PQC_All | 414.746 | 2042.526 | 4.9x |
| PQC_TLS1.3 | 8525.134 | 40177.367 | 4.7x |
| wolfSSL ML-KEM-768 encap | 25.21 ms | 6.37 ms | 4.0x |
| PQClean ML-KEM-768 encap | 37.9 ms (-O0) | 15.33 ms | 2.47x |
| PQClean ML-DSA-65 sign (median) | 73.72 ms | 74.77 ms | **1.01x** |

Same code, same board, five-fold difference. The level must be stated for every
number, which is why it is stated once at the top of this report and carried on
every matrix row. Note the last row: **sensitivity is library-specific.**
wolfSSL's ML-DSA responds strongly to optimisation; PQClean's clean-C ML-DSA
barely responds, because its cost sits in rejection sampling and NTT work rather
than code the compiler can restructure.

---

## 7. Task 3A — 128 KB firmware verification (secure boot)

Payload 131,072 B, n = 20 per scheme. Capture:
`task3a/results/task3a_dist.txt`.

| Scheme | sign mean/min/max | verify mean/min/max | sig bytes | payload RAM |
|---|---|---|---|---|
| ECDSA P-256 | 16.93 / 16.93 / 16.93 | 26.70 / 26.70 / 26.70 | 72 | streamed |
| ML-DSA-44 pure | 155.72 / 137.42 / 217.14 | 133.10 / 133.10 / 133.10 | 2420 | **131,072 B** |
| ML-DSA-65 pure | 179.47 / 148.75 / 318.18 | 143.13 / 143.13 / 143.13 | 3309 | **131,072 B** |
| HashML-DSA-65 | 55.30 / 30.08 / 107.91 | 24.45 / 24.45 / 24.45 | 3309 | streamed |

(ms. Pre-hash = streaming SHA-256 / SHA-512 over the 128 KB in 4 KB chunks:
44.23 ms and 85.34 ms respectively.)

1. **Hashing dominates pure ML-DSA verification.** ML-DSA-65 verify (143 ms)
   absorbs a SHAKE256 pass over 128 KB inside the primitive. Pre-hashing lifts it
   out: HashML-DSA-65 verifies a 64-byte digest in **24.45 ms**, 5.9x faster.
2. **HashML-DSA-65 verification beats ECDSA P-256 verification:** 24.45 vs
   26.70 ms. The classical advantage sits in the pre-hash and the small
   signature, not in verification.
3. **The buffering split is asymmetric.** Pure ML-DSA needs the whole payload
   addressable at once — 131,072 B of RAM for a device receiving firmware over a
   link. ECDSA and HashML-DSA verify a digest and stream in 4 KB chunks, needing
   112 B (SHA-256) or 224 B (SHA-512) of context plus the chunk.
4. **Signature overhead:** 72 B (DER ECDSA) vs 2420 / 3309 B — a 34-46x larger
   header to carry.
5. **Verification is deterministic** (min-max within 0.1%); **signing carries the
   tail** (HashML-DSA-65 spread 30.08-107.91 ms in 20 draws). ECDSA sign is
   constant because deterministic k removes the randomness.

The repeat loop found two bugs a single-draw run hides: `wc_ecc_verify_hash`
takes `(sig, siglen, hash, hashlen)` and the arguments were reversed (spurious
FAIL at 0 ms), and `siglen` is an in/out parameter so the second DER signature
overflowed its buffer (`BUFFER_E`, -132) unless reset each iteration.

---

## 8. Task 3B — telemetry signing fat tail

ML-DSA signing over 256 B telemetry frames, n = 2000 per level, PQClean:

| Level | median | p99 | max | worst/median |
|---|---|---|---|---|
| ML-DSA-44 | 43.94 ms | 181.91 ms | 289.05 ms | 6.6x |
| ML-DSA-65 (-Os) | 73.72 ms | 293.99 ms | 505.68 ms | 6.9x |
| ML-DSA-65 (-O2) | 74.77 ms | 291.54 ms | 500.57 ms | 6.7x |
| ML-DSA-87 | 99.41 ms | 336.24 ms | 477.86 ms | 4.8x |

At a 10 Hz telemetry budget (100 ms/frame) the median fits and the worst case
does not, at every level. This is the deadline-aware-scheduling argument in one
table: ML-DSA has a fat right tail, so a stateless "is the median under budget"
check is not sufficient.

---

## 9. pqm4 M4F→M33 portability post-mortem

**Question:** why does hand-optimised Cortex-M4F assembly that is 1.4-1.6x faster
than clean C fault on the M33?

**Method:** a custom `HardFault_Handler` capturing CFSR/HFSR/MMFAR/BFAR and the
stacked PC, plus LinkServer GDB halt-and-inspect.

```text
CFSR  = 0x00100000   HFSR = 0x40000000
MMFAR = 0xE000ED34   BFAR = 0xE000ED38     <- stale, never updated
stacked PC = 0x40000000   stacked LR = 0xE000ED34   <- garbage
[FORCED] escalated to HardFault
```

**Decode (ARMv8-M):** CFSR bit 20 = **STKOF** (stack overflow) — on ARMv8-M the
UsageFault STKOF is at UFSR bit 4, i.e. CFSR bit 20. HFSR bit 30 = FORCED, the
original UsageFault escalated.

**With a 128 KB stack** the STKOF disappears but the keypair hangs. GDB shows
`pc 0x20018040` — inside the stack region, executing data as code — with the
familiar `b.n .-2` self-loop, LR garbage, and SP sitting ~91 KB below the limit.

**Root cause:** the pqm4 M4F assembly corrupts its own call state on the M33.
Not a TrustZone violation (no INVPC/INVSTATE), not an illegal instruction (no
UNDEFINSTR), not an alignment fault (no UNALIGNED). The clean-C paths run
correctly on the same board with the same stack, isolating it to the assembly.

**Why it is a real finding:** it converts a software crash into an architectural
difference — the M4F (ARMv7-M) has no stack-limit hardware and silently
overruns, while the M33 (ARMv8-M) catches the corruption at the hardware level.
The same code fails *differently and detectably* on the modern core. And the
naive expectation ("M4F asm on M33 = unaligned LDRD fault") is wrong here: the
register evidence says stack overflow.

> An earlier revision of this note read CFSR bit 20 against the ARMv7-M layout
> and called it UNSTKERR. That was wrong for this core; corrected to STKOF.

---

## 10. Findings that overturned expectations

Collected here because each one is a result in its own right, and each was found
by measuring rather than assuming:

1. **PQC handshake is +4.9%, not −3.6%.** The "cheaper" figure was a 3-sample
   artefact.
2. **Assembly is the slowest tier, not the fastest.** wolfSSL portable C beat
   pqm4's M4F assembly by 3.8x on ML-KEM-768 encapsulation.
3. **The assembly build cannot even be enabled** for this target (ARMv8-M gate),
   so "no asm" is a constraint, not a preference.
4. **PQClean ML-DSA is insensitive to optimisation** (1.01x from `-Os` to
   `-O2`), against a 4.9x effect on PQC_All overall.
5. **Pure ML-DSA verification is 5.9x slower than HashML-DSA** with a 128 KB
   payload, and needs 128 KB of RAM to do it — the reverse of the usual
   assumption that pre-hashing is a niche optimisation.
6. **HashML-DSA-65 verify beats ECDSA P-256 verify** (24.45 vs 26.70 ms).

---

## 11. Caveats — all of them

**Evidence standard.** EEMBC has published no PQC profile, so there is **no
EEMBC golden CRC** for ML-KEM or ML-DSA. Those suites use a dual scheme: a
functional round-trip self-check plus a synthesized regression CRC. "EEMBC CRC
MATCH" is never claimed for them. Only the classical suites are checked against
EEMBC goldens.

**Task 3A specifically.** SHA-256 and SHA-512 are software implementations
(`WOLFSSL_NO_ASM`), so the 44.23 ms and 85.34 ms pre-hash figures are pessimistic
for the classical side; a hardware hash engine would cut them substantially and
shift the end-to-end ranking, though not the verify-only comparison.

**Measurement.** ML-DSA signing is rejection sampled; use the n=2000
distributions for tails and treat single draws as indicative only. Harness `ips`
is iterations over elapsed time, so PQC components are means (30 iterations);
the earlier 3-iteration mean was optimistic by ~13% on ML-DSA-65 sign.
Verification has no rejection loop and is effectively deterministic.

**Build.** `WOLFSSL_NO_ASM` throughout, for the architectural reason in §5.
Historical matrix rows carry `-O0`/`-Os` and are labelled; only `-O2` rows are
comparison-grade. Three upstream warnings are downgraded rather than fixed
(`format`, `maybe-uninitialized`, `incompatible-pointer-types` — the last a
`word32`/`uint32_t` spelling difference with identical layout). The four files
written for this work are warning-clean under `-Wall -Wextra`; the only
diagnostic they raise is wolfSSL's own advisory `#warning` about harden options.

**Harness changes.** Three, all documented at the point of change: the classical
P-384 ECDH RNG fix, `SP_INT_BITS 4096` for RSA-4096, and the bounded `AUTOTUNE`
loop.

**Scope.** `PQC_All` weights keypair, encapsulation and validation equally; the
protocol-weighted score exists precisely because equal weighting is not how a
handshake costs out.

---

## 12. Artifacts

| Path | Contents |
|---|---|
| `securemark_v2_pqc/v2harness/results/pqc_denoised.txt` | native score sheet capture (30-iter) |
| `securemark_v2_pqc/v2harness/results/SECUREMARK_V2_FINAL_REPORT.md` | full SecureMark-V2 report |
| `securemark_v2_pqc/v2harness/results/SECUREMARK_V2_PQC_REPORT.md` | running trail, including the fixes |
| `securemark_v2_pqc/v2harness/raw/SECUREMARK_V2_PQC_SUMMARY.csv` | per-component ips + CRCs |
| `securemark_v2_pqc/results/PQC_LIBRARY_CONFIG_MATRIX.csv` | library matrix, 42 rows |
| `securemark_v2_pqc/bench/results/STANDALONE_PQC_BENCH.md` | standalone bench |
| `securemark_v2_pqc/task3a/results/task3a_dist.txt` | 128 KB firmware verification, n=20 |
| `mldsa_bench_nxp/results/task3b/*_dist.csv` | ML-DSA sign distributions, n=2000 |
| `mlkem_bench/results/pqclean_o2.txt` | PQClean ML-KEM-768 at -O2 |
| `pqm4_bench_mcxn947/results/PQM4_M4F_M33_POSTMORTEM.md` | portability post-mortem |
| `pqm4_bench_mcxn947/results/mldsa44_fault.txt` | raw fault-register capture |

Regenerate: `scripts/emit_library_matrix.py` (matrix),
`scripts/evaluate_securemark_v2_pqc.py <capture>` (scores + CRC validation).

---

## 13. One-paragraph summary

In September the PQC benchmarking moved from a flat standalone bench to the
official EEMBC SecureMark-V2 harness carrying 20 native PQC components alongside
82 classical ones, all at `-O2`, on real hardware. The harness now emits its own
score sheet (`PQC_All` 2042.526, protocol-weighted 40177.367) with every PQC
component passing its functional self-check and its regression checksum. With
that baseline in place, the handshake comparison shows PQC at **+4.9%** against
classical P-256, the library matrix shows a **2.41x** spread between a reference
clean-C implementation and a native engine, and the secure-boot case shows
HashML-DSA verification **faster than ECDSA** while needing no payload buffering.
Three expected results came back inverted — the PQC penalty, the assembly tier's
ranking, and the availability of assembly at all.
