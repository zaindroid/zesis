# SecureMark-V2 with PQC suites — MCXN947 results

EEMBC SecureMark-V2 harness extended with native post-quantum suites, running
bare metal on the FRDM-MCXN947.

**Methodology level: `-O2` for every primitive, PQC and classical alike.**
This is the single stated level for every number below. (An earlier run at a
mixed `-O0`/`-Os` is kept at the end as a sensitivity check.)

## What ran

- Harness: upstream `securemark-v2` self-hosted example. 102 components: 82
  classical (TLSv1.2, TLSv1.3 light/medium/heavy, Secure Boot) plus 20 new
  post-quantum components registered as the `PQC_All` suite.
- Backend: wolfSSL 5.9.2, native `wc_mlkem.c` / `wc_mldsa.c`, crypto-only
  (`WOLFCRYPT_ONLY`), `WOLFSSL_NO_ASM`, Cortex-M33 @ 150 MHz, `-O2`.
- Platform port: DWT cycle counter replacing `clock_gettime` (64-bit
  accumulator so the 32-bit CYCCNT wrap cannot corrupt a delta), `_write`
  retarget to LPUART, `th_malloc` and wolfSSL `XMALLOC` both routed to one
  160 KB static pool, 96 KB stack.
- Capture: `results/pqc_o2.txt` (COM9, 115200).

## Scores at -O2

| Score | Value | Definition |
|---|---|---|
| **PQC_All** | **2068.848** | 1000 / Σ(wᵢ/ipsᵢ), wᵢ = 1, 20 components |
| **PQC_TLS1.3** | **43705.876** | 1000 / Σ(0.25/ipsᵢ) over ML-KEM-768 enc/dec and ML-DSA-65 sign/verify |

## PQC components (per primitive, -O2)

| Component | ips | ms | regression CRC | check |
|---|---|---|---|---|
| kem512_kp | 229.375 | 4.36 | 0x62BBEB8F | PASS |
| kem512_enc | 266.075 | 3.76 | 0xBB6188B7 | PASS |
| kem512_dec | 196.734 | 5.08 | 0x9F5F9CEC | PASS |
| kem768_kp | 142.626 | 7.01 | 0x90501E72 | PASS |
| kem768_enc | 156.928 | 6.37 | 0x8A48D4A5 | PASS |
| kem768_dec | 121.330 | 8.24 | 0x9BCEA716 | PASS |
| kem1024_kp | 90.329 | 11.07 | 0xFCB38031 | PASS |
| kem1024_enc | 98.613 | 10.14 | 0xFDB3B688 | PASS |
| kem1024_dec | 79.620 | 12.56 | 0xC94D4A71 | PASS |
| dsa44_kp | 68.988 | 14.50 | 0xA3E2B62A | PASS |
| dsa44_sign | 34.275 | 29.18 | 0xBA561067 | PASS |
| dsa44_ver | 68.810 | 14.53 | 0xBA561067 | PASS |
| dsa65_kp | 39.818 | 25.11 | 0x24EB962B | PASS |
| dsa65_sign | 19.108 | 52.33 | 0x1EE8F069 | PASS |
| dsa65_ver | 40.696 | 24.57 | 0x1EE8F069 | PASS |
| dsa87_kp | 23.134 | 43.23 | 0x58BF68D4 | PASS |
| dsa87_sign | 10.828 | 92.35 | 0xAB6329B9 | PASS |
| dsa87_ver | 23.576 | 42.42 | 0xAB6329B9 | PASS |
| hashdsa65_sign | 19.196 | 52.09 | 0x9C084B80 | PASS |
| hashdsa65_ver | 40.902 | 24.45 | 0x9C084B80 | PASS |

All 20 components SELF-CHECK PASS. All seven comparable regression CRCs match
the standalone-bench values recorded on the same board, and they match the
`-Os` run as well — the regression checksum is optimiser-independent, which is
what makes it usable as a cross-build invariant.

## PQC vs classical, same library, same flags

Both sides are wolfSSL at `-O2`. Public-key phase = 1 ECDH + 1 sign + 2 verifies.

| Handshake public-key phase | Component times | Total |
|---|---|---|
| Classical (P-256) | 24.34 + 17.57 + 2×26.50 ms | **94.91 ms** |
| PQC (ML-KEM-768 + ML-DSA-65) | 6.37 + 8.24 + 52.33 + 24.57 ms | **91.51 ms** |

At `-O2` with a native PQC implementation the post-quantum public-key phase is
**3.6% cheaper** than classical P-256. The earlier mbedTLS-based classical
measurement put this phase at 166.1 ms, so the gap closes from "PQC is much
worse" to "PQC is level or slightly ahead" once both sides run the same
optimisation and a modern PQC engine. ML-DSA verification (24.57 ms) is
cheaper than ECDSA P-256 verification (26.50 ms); the cost sits in signing.

## Optimisation sensitivity

| | -Os (mixed run) | -O2 (this run) | factor |
|---|---|---|---|
| PQC_All | 414.746 | 2068.848 | 5.0x |
| PQC_TLS1.3 | 8525.134 | 43705.876 | 5.1x |
| ML-KEM-768 encap | 25.21 ms | 6.37 ms | 4.0x |

This is why the level had to be fixed before any comparison: the same code and
the same board differ five-fold. All comparison numbers in this report are `-O2`.

## Two standards of evidence

**Classical suites** are checked against EEMBC's precomputed golden CRCs.

**PQC suites have no EEMBC golden CRC** — EEMBC has published no PQC profile. So
they are reported under a dual scheme and never labelled "EEMBC CRC MATCH":

1. *Functional self-check* — KEM decapsulation recovers the encapsulated shared
   secret exactly; DSA verification returns valid. `SELF-CHECK: PASS`.
2. *Synthesized regression CRC* — CRC-32 over the deterministic output buffer,
   checked against the standalone bench value. Two independent builds agreeing
   bit-for-bit is evidence of identical cryptographic output.

## Honest limitations

- **One classical component still fails.** `rsa_verify_4096` in the Heavy
  suite reports `WC_KEY_SIZE_E` (-234); RSA-4096 support is not enabled in this
  build. RSA-2048 works (83.487 ips). The Heavy suite score is therefore not
  valid, and the harness's own score section does not print; the PQC scores
  above are computed from the captured component data by
  `scripts/evaluate_securemark_v2_pqc.py`.
- **`ecdh_p384r1` was fixed this run.** It failed `MISSING_RNG_E` because
  `wc_ecc_shared_secret` needs a live RNG on the key under
  `ECC_TIMING_RESISTANT`; the shim now calls `wc_ecc_set_rng`.
- **ML-DSA sign here is one sample per component.** Signing is rejection
  sampled; over 2000 runs at 256 B (Task 3B) the worst/median ratio is
  6.6x / 6.9x / 4.8x for levels 44 / 65 / 87. Use Task 3B for tails.
- **`WOLFSSL_NO_ASM`.** The `--enable-sp` / assembly build is a separate library
  variant and will move these numbers.
- Three upstream warnings (`format`, `maybe-uninitialized`,
  `incompatible-pointer-types` — the last a `word32`/`uint32_t` spelling
  difference with identical layout) are downgraded rather than fixed, so
  behaviour and not warning cleanliness is what the CRC checks validate.

## Three-tier implementation comparison (ML-KEM-768 encapsulation)

| Tier | Implementation | Time | Flags |
|---|---|---|---|
| Reference C | PQClean clean C | ~37.9 ms | `-O0` |
| Embedded engine | wolfSSL native | 6.37 ms | `-O2`, no asm |
| Hand-tuned assembly | pqm4 | ~6.6 ms | Cortex-M4F asm, M3 caveat |

The reference-C row is `-O0` and is not comparable at face value; it is listed
to show the tier ordering, not as a controlled measurement. Rebuilding the
PQClean bench at `-O2` is the open item that would make this row comparable.

---

## Update — harness-native scores, RSA-4096 fixed

The classical baseline is now complete and the harness prints its own score
section (no reconstruction from the capture). Two fixes made this possible:

- **RSA-4096**: `WC_KEY_SIZE_E` (-234). `RSA_MAX_SIZE` is
  `WC_BITS_FULL_BYTES(SP_INT_BITS)`, so `SP_INT_BITS 4096` was added.
  `rsa_verify_4096` now measures 22.179 ips.
- **Autotune hang**: the harness's `AUTOTUNE` loop doubles iterations until 1 s
  of work elapses. A component that fails instantly never reaches the target, so
  the loop spun forever and the score section never printed. The loop is now
  bounded (24 doublings ~ 16.7 M iterations, far past 1 s for any working
  primitive). This is a harness change, documented here.

### Native score sheet (MCXN947, wolfSSL, -O2)

| Suite | Score |
|---|---|
| **PQC_All** | **2068.402** |
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
| **PQC_TLS1.3 (768/65)** | **43696.105** |

Zero CRC errors across the run; all 20 PQC components SELF-CHECK PASS.
Capture: `results/pqc_scores.txt`.

## ML-DSA-65 sign: reconciling the two numbers

Two ML-DSA-65 signing figures existed and looked inconsistent:

| Source | Implementation | Flags | Statistic | Value |
|---|---|---|---|---|
| Task 3B | PQClean clean C, 256 B, n=2000 | `-Os` | median | 73.72 ms |
| Task 3B | same run | `-Os` | **mean** | **90.93 ms** |
| Harness | wolfSSL native | `-O2` | mean over 3 iterations | 52.33 ms |

The apparent 1.41x gap was an artefact of comparing the harness **mean** against
a **median**. Because rejection sampling gives a right-skewed distribution, the
mean sits well above the median (90.93 vs 73.72 ms, a 1.23x mean/median ratio on
that sample). The like-for-like comparison is mean to mean: **90.93 / 52.33 =
1.74x**.

That 1.74x is not resolved into its causes yet. Three effects are entangled:

1. **Library.** PQClean clean C vs wolfSSL's native ML-DSA. For ML-KEM the two
   differ by far more than an optimisation flag would explain, so this is
   expected to be the dominant term.
2. **Optimisation level.** `-Os` (PQClean build) vs `-O2` (harness). On the
   wolfSSL ML-KEM components the `-Os` to `-O2` step alone was ~4x, so this term
   is not small.
3. **Sample size.** The harness figure is a mean over 3 iterations, not a
   distribution. With a p99/median ratio of ~4x, a 3-sample mean is noisy; the
   Task 3B figure is a 2000-sample mean.

The experiment that would settle it: rebuild the PQClean ML-DSA bench at `-O2`
and re-run 2000 samples, giving (a) a matched-optimisation PQClean-vs-wolfSSL
number and (b) a proper distribution for wolfSSL. Until that exists, the honest
statement is "wolfSSL at -O2 signs ML-DSA-65 about 1.7x faster on the mean than
PQClean at -Os, with the split between library and optimisation not yet
isolated."

Separately: raising the PQC iteration count in `pqc_component` from 3 to
something like 30 is now safe (the autotune guard removes the hang risk) and
would make the harness mean far less noisy.

---

## Update — Task 2 complete: the library matrix is now controlled

The PQClean reference bench was rebuilt at `-O2` (was `-O0`), verified from
`compile_commands.json` (`['-Os','-O2']` -> `-O2`), and re-run on hardware
(`results/pqclean_o2.txt`, captured on COM9).

### ML-KEM-768, both implementations at -O2

| Implementation | keypair | encapsulate | decapsulate |
|---|---|---|---|
| PQClean clean C | 13.86 ms | **15.33 ms** | 17.39 ms |
| wolfSSL native | 7.01 ms | **6.37 ms** | 8.24 ms |
| ratio | 1.98x | **2.41x** | 2.11x |

At matched optimisation wolfSSL's native ML-KEM is **2.41x faster** than PQClean
clean C on encapsulation. That is a library-level result, not an optimisation
artefact — which is what the earlier mixed-flag table could not show.

### Optimisation sensitivity of the reference implementation

| PQClean ML-KEM-768 encap | Flags | Time |
|---|---|---|
| before | -O0 | 37.9 ms |
| after | -O2 | 15.33 ms |
| factor | | **2.47x** |

### Three-tier matrix (ML-KEM-768 encapsulation)

| Tier | Implementation | Time | Flags |
|---|---|---|---|
| Reference C | PQClean clean C | 15.33 ms | -O2, measured |
| Embedded engine | wolfSSL native | 6.37 ms | -O2, measured |
| Hand-tuned assembly | pqm4 | ~6.6 ms | Cortex-M4F asm, M3 caveat |

The first two rows are now a controlled comparison at one optimisation level.
The pqm4 row remains a different codebase (M4F assembly) that does not run
cleanly on the M33, so it stays indicative.

---

## Task 3A — 128 KB firmware signature verification (secure boot)

Firmware: `task3a/` (bare metal, DWT, -O2, wolfSSL). Payload: 131,072 B.
All four schemes verify PASS. Capture: `task3a/results/task3a_raw.txt`.

| Scheme | pre-hash | sign | **verify** | sig bytes | end-to-end | payload RAM |
|---|---|---|---|---|---|---|
| ECDSA P-256 | 44.23 | 16.93 | **26.73 ms** | 71 | 70.96 ms | streamed |
| ML-DSA-44 pure | n/a | 190.0 | **133.10 ms** | 2420 | 133.10 ms | **131,072 B** |
| ML-DSA-65 pure | n/a | 202.4 | **143.13 ms** | 3309 | 143.13 ms | **131,072 B** |
| HashML-DSA-65 | 85.34 | 57.49 | **24.45 ms** | 3309 | 109.79 ms | streamed |

(ms; pre-hash = streaming SHA-256 / SHA-512 over the 128 KB in 4 KB chunks)

### What this shows

1. **Hashing dominates pure ML-DSA verification.** The ML-DSA-65 verify (143 ms)
   absorbs a SHAKE256 pass over 128 KB inside the primitive. Pre-hashing lifts
   that out: HashML-DSA-65 verifies a 64-byte digest in **24.45 ms**, 5.9x
   faster, and end-to-end (85.34 + 24.45 = 109.79 ms) is still 23% cheaper than
   the pure path (143.13 ms).
2. **HashML-DSA verification beats ECDSA P-256 verification.**
   24.45 ms vs 26.73 ms. The classical advantage moves to signing and to the
   pre-hash, not to verification.
3. **The streaming/buffering split is real and asymmetric.** Pure ML-DSA hands
   the whole payload to the API, so a device receiving firmware over a link must
   hold all **131,072 B** in RAM at once. ECDSA and HashML-DSA verify a digest,
   so the payload streams through in 4 KB chunks: **112 B (SHA-256) or 224 B
   (SHA-512) of context + 4 KB chunk + digest**.
4. **Signature overhead.** 71 B (DER ECDSA) vs 2,420 B (ML-DSA-44) vs 3,309 B
   (ML-DSA-65 / HashML-DSA-65) — a 34-47x larger header to carry.

### Caveats

- SHA-256 and SHA-512 are software implementations (`WOLFSSL_NO_ASM`), so the
  pre-hash rows are pessimistic for the classical side. An AES/SHA hardware
  engine would cut the 44 ms and 85 ms substantially and shift the end-to-end
  ranking. This is the same flag caveat as everywhere else in this report.
- The streaming path models a link read by copying into a 4 KB chunk buffer;
  the payload itself sits in RAM for the pure-ML-DSA case, which is what the
  "payload RAM" column reports.
- Single run per scheme, not a distribution. ML-DSA signing is rejection
  sampled, so the sign column is one draw; the verify column is not, since
  verification has no rejection loop.
- `wc_ecc_verify_hash` takes (sig, siglen, hash, hashlen, res, key) — the first
  run had the arguments reversed and reported a spurious FAIL with 0 ms.
  Corrected; worth noting because the failure mode was silent-ish.
