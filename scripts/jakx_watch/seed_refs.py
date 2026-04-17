#!/usr/bin/env python3
"""Auto-seed missing _REF.gc files for real-clean jakx decomps.

For each file in the real-clean bucket that lacks a _REF.gc:
  1. Find its sibling in goal_src/jakx/<subpath>/<name>.gc
  2. Run offline-test --dump_current_output for that one file
  3. Move the dumped output to test/decompiler/reference/jakx/<subpath>/<name>_REF.gc

Skips files that already have a _REF.gc (doesn't overwrite — that's regression
detection's job, we only add NEW coverage).

After seeding, re-run `bash scripts/jakx_watch/run.sh` so offline-test's
comparison uses the new refs.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
OFFLINE_TEST = ROOT / "build" / "Release" / "bin" / "offline-test"
GOAL_SRC = ROOT / "goal_src" / "jakx"
REF_DIR = ROOT / "test" / "decompiler" / "reference" / "jakx"
ISO_DIR = ROOT / "iso_data"
DUMP_DIR = ROOT / ".jakx_watch" / "ref_dump"


def existing_refs() -> set[str]:
    return {p.stem[: -len("_REF")] for p in REF_DIR.rglob("*_REF.gc")}


def source_subpath(name: str) -> Path | None:
    """Return the relative subdir under goal_src/jakx where <name>.gc lives."""
    matches = list(GOAL_SRC.rglob(f"{name}.gc"))
    if not matches:
        return None
    rel = matches[0].relative_to(GOAL_SRC)
    return rel.parent


def dump_one(name: str) -> Path | None:
    """Run offline-test --dump_current_output for NAME; return dumped file path."""
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    # offline-test writes dumps into its own "dump/" relative folder under CWD.
    cwd = DUMP_DIR
    # Clean previous dump for this name.
    for old in cwd.rglob(f"{name}_REF.gc"):
        old.unlink()
    r = subprocess.run(
        [
            str(OFFLINE_TEST),
            "--iso_data_path", str(ISO_DIR / "jakx"),
            "--game", "jakx",
            "--file", name,
            "--dump_current_output",
        ],
        capture_output=True, text=True, check=False, timeout=180, cwd=str(cwd),
    )
    dumped = next(cwd.rglob(f"{name}_REF.gc"), None)
    if dumped is None:
        print(f"  ✗ {name}: dump failed (rc={r.returncode})")
        tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
        for line in tail:
            print(f"      {line}")
        return None
    return dumped


def seed_file(name: str) -> bool:
    sub = source_subpath(name)
    if sub is None:
        print(f"  ✗ {name}: no goal_src/jakx/**/{name}.gc — can't place ref")
        return False
    dumped = dump_one(name)
    if dumped is None:
        return False
    dest = REF_DIR / sub / f"{name}_REF.gc"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(dumped), dest)
    print(f"  ✓ {name} → {dest.relative_to(ROOT)}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be seeded, don't run offline-test")
    ap.add_argument("--force", action="store_true",
                    help="re-dump refs even if they already exist")
    args = ap.parse_args()

    if not OFFLINE_TEST.exists():
        print(f"offline-test binary missing: {OFFLINE_TEST.relative_to(ROOT)}")
        return 1
    if not LATEST.exists():
        print("no latest snapshot — run measure.py first")
        return 1

    snap = json.loads(LATEST.read_text())
    real_clean = sorted(n for n, v in snap["per_file"].items() if v["category"] == "real-clean")
    have = existing_refs()
    missing = [n for n in real_clean if args.force or n not in have]

    print(f"real-clean: {len(real_clean)}  ·  have refs: {len(have)}  ·  missing: {len(missing)}")
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
        if seed_file(n):
            ok += 1
        else:
            fail += 1

    # Cleanup the dump dir if it's empty.
    if DUMP_DIR.exists() and not any(DUMP_DIR.rglob("*")):
        shutil.rmtree(DUMP_DIR, ignore_errors=True)

    print(f"\nseeded: {ok}  ·  failed: {fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
