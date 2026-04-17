#!/usr/bin/env python3
"""Run offline-test for jakx against files that reached real-clean.

Splits the real-clean bucket into:
  - green  : offline-test passed (decomps AND goalc-compiles to matching bytecode)
  - amber  : decomps, but bytecode-diff fails → not shippable yet
  - skipped: no reference file exists (expected for early phase)

Requires a minimal jakx offline-test config at
  test/offline/config/jakx/config.jsonc
...and reference files under
  test/decompiler/reference/jakx/**/*_REF.gc

For jakx's Phase-0 state (no corpus), this script no-ops cleanly.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_TEST = ROOT / "build" / "Release" / "bin" / "offline-test"
JAKX_CONFIG = ROOT / "test" / "offline" / "config" / "jakx" / "config.jsonc"
JAKX_REFS = ROOT / "test" / "decompiler" / "reference" / "jakx"
ISO_DIR = ROOT / "iso_data"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"


def main() -> int:
    if not OFFLINE_TEST.exists():
        print("offline-test binary missing — build it:")
        print("  cmake --build build/Release --target offline-test -j")
        return 0
    if not JAKX_CONFIG.exists():
        print(f"skipped: jakx offline-test config missing at {JAKX_CONFIG.relative_to(ROOT)}")
        print("         (Phase-0 work item — create config + reference corpus)")
        return 0
    if not JAKX_REFS.exists() or not any(JAKX_REFS.rglob("*_REF.gc")):
        print(f"skipped: no jakx reference files under {JAKX_REFS.relative_to(ROOT)}")
        print("         run offline-test with --dump_current_output once, then commit "
              "cleaned _REF.gc files")
        return 0

    snap = json.loads(LATEST.read_text()) if LATEST.exists() else None
    if not snap:
        print("no latest snapshot — run measure.py first")
        return 1

    # Only check files that made it to real-clean.
    candidates = sorted(
        name for name, v in snap["per_file"].items() if v["category"] == "real-clean"
    )
    print(f"real-clean candidates: {len(candidates)}")

    results = {"green": [], "amber": [], "error": []}
    for name in candidates:
        r = subprocess.run(
            [
                str(OFFLINE_TEST),
                "--iso_data_path", str(ISO_DIR / "jakx"),
                "--game", "jakx",
                "--file", name,
                "--fail-on-cmp",
            ],
            capture_output=True, text=True, check=False, timeout=120,
        )
        if r.returncode == 0:
            results["green"].append(name)
        elif "no reference" in (r.stdout + r.stderr).lower():
            # skip quietly
            pass
        else:
            results["amber"].append(name)

    print(f"green  (offline-test passing):  {len(results['green'])}")
    print(f"amber  (decomps, bytecode mismatch): {len(results['amber'])}")
    if results["green"]:
        print()
        print("GREEN files:")
        for n in results["green"]:
            print(f"  ✓ {n}")
    if results["amber"]:
        print()
        print("AMBER files (top 20):")
        for n in results["amber"][:20]:
            print(f"  ~ {n}")

    # Persist into the latest snapshot for downstream tooling.
    snap["offline_test"] = {
        "green": results["green"],
        "amber": results["amber"],
        "candidates": len(candidates),
    }
    LATEST.write_text(json.dumps(snap, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
