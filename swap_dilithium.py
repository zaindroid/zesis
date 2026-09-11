"""
Swap the dilithium_bench project's pqclean/ directory to a given ML-DSA
security level, mirroring swap.ps1's pattern for ML-KEM.

Usage: python swap_dilithium.py 44   (or 65, or 87)

Unlike ML-KEM's swap, this also patches sign.c to expose the internal
rejection-sampling attempt count (the `nonce` variable, incremented once
per pass through the `rej:` label -- its final value equals the number of
attempts; retries = attempts - 1) via a global variable + getter, since
PQClean's public API doesn't otherwise expose it. See
BENCHMARK_METHODOLOGY.md in dilithium_bench/ for why this number matters
(retry-count-vs-signing-time correlation is one of the deliverables).

The patch is applied to the freshly-copied sign.c on every swap (not to
the master PQClean checkout), so it's always in sync with whichever
level was just copied in, and never touches the pristine upstream source.
"""
import re
import shutil
import sys
from pathlib import Path

LEVELS = {"44", "65", "87"}

PROJ = Path("H:/z_thesis/codebase/projects/dilithium_bench")
PQ = PROJ / "pqclean"
KEEP = {"fips202.c", "fips202.h", "randombytes.c", "randombytes.h",
        "compat.h", "crypto_declassify.h"}


def patch_sign_c(sign_c_path: Path, level: str) -> None:
    """Expose the rejection-sampling attempt count via a global + getter."""
    text = sign_c_path.read_text(encoding="utf-8")
    prefix = f"PQCLEAN_MLDSA{level}_CLEAN"

    # 1. Add the global counter + getter near the top of the file, right
    #    after the last #include.
    includes_end = text.rfind("#include")
    includes_end = text.index("\n", includes_end) + 1
    instrumentation_decl = (
        f"\n/* --- benchmark instrumentation (added by swap_dilithium.py, not\n"
        f" * upstream PQClean) ---\n"
        f" * Exposes the rejection-sampling attempt count from the last\n"
        f" * {prefix}_crypto_sign_signature_ctx() call: the `nonce`\n"
        f" * variable increments once per pass through the `rej:` retry loop,\n"
        f" * so its final value IS the attempt count (1 = no rejection,\n"
        f" * N = (N-1) rejections before success). */\n"
        f"uint32_t {prefix}_last_sign_attempts = 0;\n"
    )
    text = text[:includes_end] + instrumentation_decl + text[includes_end:]

    # 2. Right before the `return 0;` that ends crypto_sign_signature_ctx
    #    (immediately follows the pack_sig/*siglen= lines after the `rej:`
    #    block), stash nonce's final value. Match specifically inside that
    #    function by anchoring on the preceding pack_sig call, so this
    #    can't accidentally match a `return 0;` in a different function.
    pattern = re.compile(
        r"(" + re.escape(f"{prefix}_pack_sig(sig, sig, &z, &h);") +
        r"\s*\n\s*\*siglen = " + re.escape(f"{prefix}_CRYPTO_BYTES") + r";\s*\n)"
        r"(\s*return 0;)"
    )
    new_text, n = pattern.subn(
        lambda m: m.group(1) + f"    {prefix}_last_sign_attempts = nonce;\n" + m.group(2),
        text,
    )
    if n != 1:
        print(f"ERROR: expected exactly 1 match for the sign-return patch site, got {n}")
        print("sign.c's structure may have changed -- inspect manually before trusting "
              "the retry-count instrumentation.")
        sys.exit(1)

    sign_c_path.write_text(new_text, encoding="utf-8")
    print(f"  patched sign.c: added {prefix}_last_sign_attempts (1 match)")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in LEVELS:
        print(f"Usage: python swap_dilithium.py <{'|'.join(sorted(LEVELS))}>")
        sys.exit(1)
    level = sys.argv[1]
    src = Path(f"H:/z_thesis/codebase/PQClean/crypto_sign/ml-dsa-{level}/clean")
    if not src.exists():
        print(f"ERROR: source dir not found: {src}")
        sys.exit(1)

    # Remove everything in pqclean/ except the KEEP list.
    for f in list(PQ.glob("*.c")) + list(PQ.glob("*.h")):
        if f.name not in KEEP:
            f.unlink()

    for f in list(src.glob("*.c")) + list(src.glob("*.h")):
        shutil.copy2(f, PQ / f.name)

    print(f"Copied ml-dsa-{level}/clean -> {PQ} ({len(list(src.glob('*.[ch]')))} files)")

    patch_sign_c(PQ / "sign.c", level)

    # Rename ALGNAME reference in main.c the same way swap.ps1 does for
    # hello_world.c, if main.c already exists.
    main_c = PROJ / "main.c"
    if main_c.exists():
        text = main_c.read_text(encoding="utf-8")
        new_text = re.sub(r"MLDSA\d\d", f"MLDSA{level}", text)
        if new_text != text:
            main_c.write_text(new_text, encoding="utf-8")
            print(f"  updated main.c: MLDSA references -> MLDSA{level}")

    print(f"Swapped to ML-DSA-{level}")


if __name__ == "__main__":
    main()
