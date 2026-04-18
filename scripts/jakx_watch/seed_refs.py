#!/usr/bin/env python3
"""Auto-seed missing _REF.gc files for real-clean jakx decomps.

For each file in the real-clean bucket that lacks a _REF.gc (or all files
with --force):
  1. Find its sibling in goal_src/jakx/<subpath>/<name>.gc
  2. Get the current decompiler output via one of two paths (tried in order):
     a) Copy <name>_disasm.gc from the decomp output directory
        (.jakx_watch/decomp_out/jakx/ then decompiler_out/jakx/)
     b) Fallback: run offline-test --dump_current_output per file.
        This works when the batch decompiler is broken (e.g., size-assert
        mismatch for an unrelated type) but per-file offline-test still
        runs. For amber files (has REF that doesn't match), the dump fires;
        for files with no REF, a sentinel placeholder forces a mismatch so
        the dump fires too.
  3. Place result at test/decompiler/reference/jakx/<subpath>/<name>_REF.gc

Skips files that already have a _REF.gc. Use --force to overwrite all.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
OFFLINE_TEST = ROOT / "build" / "Release" / "bin" / "offline-test"
GOAL_SRC = ROOT / "goal_src" / "jakx"
REF_DIR = ROOT / "test" / "decompiler" / "reference" / "jakx"
ISO_DIR = ROOT / "iso_data"
DUMP_DIR = ROOT / ".jakx_watch" / "ref_dump"

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


def _seed_via_copy(name: str, decomp_out: Path, dest: Path) -> bool:
    """Copy <name>_disasm.gc from decomp_out to dest. Returns True on success."""
    src = decomp_out / f"{name}_disasm.gc"
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), dest)
    return True


def _seed_via_offline_test(name: str, dest: Path) -> bool:
    """Use offline-test --dump_current_output to get the current decompiler output.

    The dump only fires when the test FAILS (current output ≠ REF). We ensure
    failure by writing a single-byte sentinel to the REF if it doesn't exist,
    then restore/remove it after the dump.
    """
    if not OFFLINE_TEST.exists():
        return False
    DUMP_DIR.mkdir(parents=True, exist_ok=True)

    # Remove any stale dump.
    for old in DUMP_DIR.rglob(f"{name}_REF.gc"):
        old.unlink()

    # If no REF exists yet, write a sentinel so offline-test sees a failure.
    sentinel_written = False
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(";; sentinel\n")
        sentinel_written = True

    r = subprocess.run(
        [
            str(OFFLINE_TEST),
            "--iso_data_path", str(ISO_DIR / "jakx"),
            "--game", "jakx",
            "--file", name,
            "--dump_current_output",
        ],
        capture_output=True, text=True, check=False, timeout=180, cwd=str(DUMP_DIR),
    )

    dumped = next(DUMP_DIR.rglob(f"{name}_REF.gc"), None)
    if dumped is None:
        # No dump = test passed (current output matched REF) → REF is already good.
        if sentinel_written:
            dest.unlink(missing_ok=True)
        return False  # nothing to update
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(dumped), dest)
    return True


def seed_file(name: str, decomp_out: Path | None) -> bool:
    sub = source_subpath(name)
    if sub is None:
        print(f"  ✗ {name}: no goal_src/jakx/**/{name}.gc — can't place ref")
        return False
    dest = REF_DIR / sub / f"{name}_REF.gc"

    # Primary: copy from decomp_out directory.
    if decomp_out and _seed_via_copy(name, decomp_out, dest):
        print(f"  ✓ {name} → {dest.relative_to(ROOT)}  [copy]")
        return True

    # Fallback: per-file offline-test dump (works when batch decompiler is broken).
    if _seed_via_offline_test(name, dest):
        print(f"  ✓ {name} → {dest.relative_to(ROOT)}  [dump]")
        return True

    if decomp_out:
        print(f"  ✗ {name}: not in decomp_out and offline-test dump failed")
    else:
        print(f"  ✗ {name}: no decomp_out and offline-test dump failed")
    return False


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
        decomp_out: Path | None = Path(args.decomp_out).resolve()
    else:
        decomp_out = _find_decomp_out()

    if decomp_out:
        print(f"decomp source: {decomp_out.relative_to(ROOT)}")
    else:
        print("no decomp_out dir with _disasm.gc files found — will use offline-test fallback")

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
            sub_str = str(sub) if sub else "<no-source>"
            print(f"  - {n}  → test/decompiler/reference/jakx/{sub_str}/")
        return 0

    print("\nseeding:")
    ok = fail = 0
    for n in missing:
        if seed_file(n, decomp_out):
            ok += 1
        else:
            fail += 1

    # Clean up dump dir if empty.
    if DUMP_DIR.exists() and not any(DUMP_DIR.rglob("*")):
        shutil.rmtree(DUMP_DIR, ignore_errors=True)

    print(f"\nseeded: {ok}  ·  failed: {fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
