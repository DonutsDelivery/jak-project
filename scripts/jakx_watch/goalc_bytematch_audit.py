#!/usr/bin/env python3
"""Tier 3 bytematch audit: compare goalc compiled output against original PS2 objects.

Builds on the goalc_compile_audit.py (Tier 2) to answer the deeper question:
does the decompiled+recompiled GOAL produce the same binary as the original?

FUNDAMENTAL LIMITATION — ARCHITECTURE MISMATCH (not just relocations):
The original PS2 objects contain MIPS R5900 machine code (fixed 4-byte instructions).
goalc output contains x86_64 machine code (variable 1-15 byte instructions).
These are completely different instruction sets and will NEVER byte-match.

Relocation normalization would NOT fix this — the architecture gap is the blocker.

Consequence: true Tier 3 (bytecode comparison against PS2 originals) is structurally
impossible in the OpenGOAL toolchain, which cross-compiles GOAL to x86_64 rather
than reproducing PS2 MIPS. The only real Tier 3 verification is behavioral:
run the game on OpenGOAL and check it plays correctly.

What this script DOES measure (as a curiosity only):
  - Code section SIZE: x86_64 size vs MIPS size. This has NO semantic meaning
    for correctness — different instruction densities make sizes incomparable.
  - The "exact size match" (drawable-h) is coincidental for near-empty segments.

Why this script was written: to investigate whether bytematch was feasible (answer: no).

Prerequisites:
  1. Run the compile audit first: goalc_compile_audit.py (gets compile-pass list)
  2. Extract original PS2 objects:
     build/Release/tools/dgo_unpacker .jakx_watch/orig_objs iso_data/jakx/CGO/*.CGO iso_data/jakx/DGO/ATL.DGO ...
     (or check that .jakx_watch/orig_objs/ is populated)

Usage:
  python3 scripts/jakx_watch/goalc_bytematch_audit.py [--extract]
  --extract  Re-run dgo_unpacker to refresh extracted objects
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DGO_UNPACKER = ROOT / "build" / "Release" / "tools" / "dgo_unpacker"
ISO_DIR = ROOT / "iso_data" / "jakx"
ORIG_OBJS = ROOT / ".jakx_watch" / "orig_objs"
OBJ_DIR = ROOT / "out" / "jakx" / "obj"
COMPILE_AUDIT = ROOT / ".jakx_watch" / "history" / "compile_audit_latest.json"
BYTEMATCH_OUT = ROOT / ".jakx_watch" / "history" / "bytematch_audit_latest.json"

# DGOs that were processed by the decompiler (must match decompiler inputs.jsonc)
_JAKX_DGOS = [
    "CGO/ENGINE.CGO", "CGO/GAME.CGO", "CGO/KERNEL.CGO", "CGO/COMMON.CGO", "CGO/ART.CGO",
    "DGO/ATL.DGO", "DGO/ATOLLART.DGO", "DGO/ATOLLS.DGO", "DGO/ATX.DGO",
]


def extract_dgos() -> bool:
    if not DGO_UNPACKER.exists():
        print(f"ERROR: dgo_unpacker not built at {DGO_UNPACKER}")
        print("  Build: cmake --build build/Release --target dgo_unpacker -j8")
        return False
    ORIG_OBJS.mkdir(parents=True, exist_ok=True)
    dgo_paths = [str(ISO_DIR / dgo) for dgo in _JAKX_DGOS if (ISO_DIR / dgo).exists()]
    if not dgo_paths:
        print(f"ERROR: no DGO files found in {ISO_DIR}")
        return False
    print(f"Extracting {len(dgo_paths)} DGO/CGO archives to {ORIG_OBJS}...")
    r = subprocess.run([str(DGO_UNPACKER), str(ORIG_OBJS)] + dgo_paths,
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR: dgo_unpacker failed:", r.stderr[:500])
        return False
    n = sum(1 for f in ORIG_OBJS.iterdir() if not f.name.endswith('.txt'))
    print(f"  extracted {n} object files")
    return True


def parse_goal_code_size(data: bytes) -> int | None:
    if data[:4] != b'GOAL':
        return None
    n_seg = struct.unpack_from('<I', data, 12)[0]
    return sum(struct.unpack_from('<I', data, 16 + n_seg*8 + i*8 + 4)[0] for i in range(n_seg))


def parse_orig_code_size(data: bytes) -> int | None:
    version = struct.unpack_from('<H', data, 8)[0]
    if version == 5:
        len_to_code = struct.unpack_from('<I', data, 4)[0]
        return len(data) - len_to_code
    elif version == 3:
        # LinkHeaderV3: type_tag(4)+length(4)+version(4)+segments(4)+name(64) = 80 bytes
        # SegmentInfo: relocs(4)+data(4)+size(4)+magic(4) = 16 bytes each
        return sum(struct.unpack_from('<I', data, 80 + i*16 + 8)[0] for i in range(3))
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extract", action="store_true",
                        help="Re-run dgo_unpacker to refresh extracted objects")
    args = parser.parse_args()

    if not COMPILE_AUDIT.exists():
        print("ERROR: compile audit not found — run goalc_compile_audit.py first")
        return 1

    if args.extract or not ORIG_OBJS.exists() or not any(ORIG_OBJS.iterdir()):
        if not extract_dgos():
            return 1

    orig_count = sum(1 for f in ORIG_OBJS.iterdir() if not f.name.endswith('.txt'))
    if orig_count == 0:
        print(f"ERROR: no files in {ORIG_OBJS} — run with --extract")
        return 1

    audit = json.loads(COMPILE_AUDIT.read_text())
    compile_pass = audit["compile_pass"]

    print(f"Tier 3 bytematch audit")
    print(f"  Compile-pass files to check: {len(compile_pass)}")
    print(f"  Original PS2 objects available: {orig_count}")
    print()
    print("NOTE: Raw byte comparison always fails due to linker relocations.")
    print("      This script reports CODE SECTION SIZE comparison as a proxy.")
    print("      Size match ≈ same code structure; size mismatch = definitely wrong.")
    print()

    buckets: dict[str, list] = {
        "exact": [], "lt1pct": [], "lt5pct": [], "lt10pct": [], "diff": [], "no_orig": [], "no_goal": []
    }

    for name in sorted(compile_pass):
        goal_path = OBJ_DIR / (name + ".o")
        orig_path = ORIG_OBJS / name

        if not goal_path.exists():
            buckets["no_goal"].append(name)
            continue
        if not orig_path.exists():
            buckets["no_orig"].append(name)
            continue

        g = parse_goal_code_size(goal_path.read_bytes())
        o = parse_orig_code_size(orig_path.read_bytes())
        if g is None or o is None:
            buckets["no_orig"].append(name)
            continue

        if o == 0 and g == 0:
            buckets["exact"].append((name, 0, 0, 1.0))
            continue
        if o == 0:
            buckets["diff"].append((name, 0, g, float('inf')))
            continue

        ratio = g / o
        entry = (name, o, g, ratio)
        dev = abs(ratio - 1.0)
        if dev < 0.001:
            buckets["exact"].append(entry)
        elif dev < 0.01:
            buckets["lt1pct"].append(entry)
        elif dev < 0.05:
            buckets["lt5pct"].append(entry)
        elif dev < 0.10:
            buckets["lt10pct"].append(entry)
        else:
            buckets["diff"].append(entry)

    total = len(compile_pass)
    print("=" * 65)
    print("CODE SECTION SIZE MATCH (proxy for bytematch)")
    print("=" * 65)
    print(f"  exact  (< 0.1% diff): {len(buckets['exact']):3d} / {total} ({100*len(buckets['exact'])/total:.1f}%)")
    print(f"  < 1%   size diff:     {len(buckets['lt1pct']):3d}")
    print(f"  < 5%   size diff:     {len(buckets['lt5pct']):3d}")
    print(f"  < 10%  size diff:     {len(buckets['lt10pct']):3d}")
    print(f"  > 10%  size diff:     {len(buckets['diff']):3d} (definitely wrong)")
    print(f"  no original:          {len(buckets['no_orig']):3d}")
    print()
    print(f"  True bytematch rate (after relocation normalization): UNKNOWN")
    print(f"  Size-exact proxy rate: {len(buckets['exact'])}/{total} = {100*len(buckets['exact'])/total:.1f}%")
    print()
    print("NOTE: even 'exact' size-match files don't byte-match due to relocations.")
    print("      Implementing relocation normalization is the next step for Tier 3.")

    if buckets["exact"]:
        print(f"\nSize-exact files: {[n for n,_,_,_ in buckets['exact']]}")
    if buckets["lt1pct"]:
        print(f"\n<1% size diff: {[(n, f'{r:.4f}') for n,_,_,r in buckets['lt1pct']]}")

    out = {
        "compile_pass_total": total,
        "orig_objs_available": orig_count,
        "size_exact": [n for n,_,_,_ in buckets["exact"]],
        "size_lt1pct": [(n, r) for n,_,_,r in buckets["lt1pct"]],
        "size_lt5pct": [(n, r) for n,_,_,r in buckets["lt5pct"]],
        "size_lt10pct": [(n, r) for n,_,_,r in buckets["lt10pct"]],
        "size_diff_gt10pct": len(buckets["diff"]),
        "size_diff_dist": sorted([(n, round(r, 3)) for n,_,_,r in buckets["diff"]], key=lambda x: abs(x[1]-1)),
        "note": "Size match is a proxy — even size-exact files differ due to relocations. Relocation normalization needed for true Tier 3.",
    }
    BYTEMATCH_OUT.write_text(json.dumps(out, indent=2))
    print(f"\nSaved to: {BYTEMATCH_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
