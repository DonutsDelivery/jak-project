#!/usr/bin/env python3
"""Auto-seed missing _REF.gc files for real-clean jakx decomps.

For each file in the real-clean bucket that lacks a _REF.gc:
  1. Find its sibling in goal_src/jakx/<subpath>/<name>.gc
  2. Copy <name>_disasm.gc from the decomp output directory
  3. Place it at test/decompiler/reference/jakx/<subpath>/<name>_REF.gc

Skips files that already have a _REF.gc (doesn't overwrite — that's regression
detection's job, we only add NEW coverage). Use --force to overwrite existing refs.

The source directory is searched in order:
  1. .jakx_watch/decomp_out/jakx/  (private watch output)
  2. decompiler_out/jakx/          (default decompiler output)

After seeding, re-run `bash scripts/jakx_watch/run.sh` so offline-test's
comparison uses the new refs.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
GOAL_SRC = ROOT / "goal_src" / "jakx"
REF_DIR = ROOT / "test" / "decompiler" / "reference" / "jakx"

# Decomp output search order.
_DECOMP_CANDIDATES = [
    ROOT / ".jakx_watch" / "decomp_out" / "jakx",
    ROOT / "decompiler_out" / "jakx",
]


def _find_decomp_out() -> Path | None:
    for p in _DECOMP_CANDIDATES:
        if p.exists() and any(p.glob("*_disasm.gc")):
            return p
    return None


def existing_refs() -> set[str]:
    return {p.stem[: -len("_REF")] for p in REF_DIR.rglob("*_REF.gc")}


def source_subpath(name: str) -> Path | None:
    """Return the relative subdir under goal_src/jakx where <name>.gc lives."""
    matches = list(GOAL_SRC.rglob(f"{name}.gc"))
    if not matches:
        return None
    rel = matches[0].relative_to(GOAL_SRC)
    return rel.parent


def seed_file(name: str, decomp_out: Path) -> bool:
    src = decomp_out / f"{name}_disasm.gc"
    if not src.exists():
        print(f"  ✗ {name}: {src.name} missing from {decomp_out.relative_to(ROOT)}")
        return False
    sub = source_subpath(name)
    if sub is None:
        print(f"  ✗ {name}: no goal_src/jakx/**/{name}.gc — can't place ref")
        return False
    dest = REF_DIR / sub / f"{name}_REF.gc"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), dest)
    print(f"  ✓ {name} → {dest.relative_to(ROOT)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be seeded, don't copy files")
    ap.add_argument("--force", action="store_true",
                    help="re-seed refs even if they already exist")
    ap.add_argument("--decomp-out", metavar="DIR",
                    help="override decomp output directory (default: auto-detect)")
    args = ap.parse_args()

    if not LATEST.exists():
        print("no latest snapshot — run measure.py first")
        return 1

    if args.decomp_out:
        decomp_out = Path(args.decomp_out).resolve()
    else:
        decomp_out = _find_decomp_out()
    if decomp_out is None or not decomp_out.exists():
        print("no decomp output directory found — run the decompiler first")
        return 1
    print(f"decomp source: {decomp_out.relative_to(ROOT)}")

    snap = json.loads(LATEST.read_text())
    real_clean = sorted(n for n, v in snap["per_file"].items() if v["category"] == "real-clean")
    have = existing_refs()
    missing = [n for n in real_clean if args.force or n not in have]

    print(f"real-clean: {len(real_clean)}  ·  have refs: {len(have)}  ·  to seed: {len(missing)}")
    if not missing:
        print("all real-clean files already have _REF.gc coverage. ✓")
        return 0

    if args.dry_run:
        print("\nwould seed:")
        for n in missing:
            sub = source_subpath(n)
            sub_str = f"engine/{sub}" if sub else "<no-source>"
            print(f"  - {n}  → test/decompiler/reference/jakx/{sub_str}/")
        return 0

    print("\nseeding:")
    ok = fail = 0
    for n in missing:
        if seed_file(n, decomp_out):
            ok += 1
        else:
            fail += 1

    print(f"\nseeded: {ok}  ·  failed: {fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
