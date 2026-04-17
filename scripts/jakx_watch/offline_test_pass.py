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

    # Pre-flight: run once against the first candidate to detect compile-setup
    # blockers (e.g., language-enum mismatch between all-types.gc and kernel-defs.gc).
    # If found, surface it and stop — no point running N files that all hit the
    # same setup failure.
    preflight = subprocess.run(
        [
            str(OFFLINE_TEST),
            "--iso_data_path", str(ISO_DIR / "jakx"),
            "--game", "jakx",
            "--file", candidates[0] if candidates else "NONE",
        ],
        capture_output=True, text=True, check=False, timeout=180,
    )
    pre_out = preflight.stdout + preflight.stderr
    setup_blocker = None
    import re as _re
    if "Inconsistent type definition" in pre_out:
        m = _re.search(r"Type ([\w<>!?:\-\+\*/=]+) was originally", pre_out)
        tname = m.group(1) if m else "<unknown>"
        setup_blocker = (
            f"all-types.gc vs kernel-defs.gc type mismatch on '{tname}'. "
            f"Fix: reconcile the defenum/deftype in decompiler/config/jakx/all-types.gc "
            f"with goal_src/jakx/kernel-defs.gc (use the 25-entry version jak3 has)."
        )
    elif "-- Type Error! --" in pre_out or "Type Error: Type" in pre_out:
        # Usually "Type X is unknown when parsing decompiler type file:Y:Z"
        # — a dependency type missing from all-types.gc
        clean = _re.sub(r"\x1b\[[0-9;]*m", "", pre_out)
        m = _re.search(
            r"Type Error: Type ([\w<>!?:\-\+\*/=]+) is unknown[^\n]*\n[^\n]*"
            r"decompiler type file:([^\s:]+?):(\d+)[^\n]*\n\s*\(([^\n]*)",
            clean,
        )
        if m:
            unk, fpath, line, form = m.group(1), m.group(2), m.group(3), m.group(4).strip()[:80]
            setup_blocker = (
                f"unknown type '{unk}' at {fpath}:{line} (in form: ({form}). "
                f"Add a deftype / declare-type / define-extern for '{unk}' in all-types.gc."
            )
        else:
            # Fall back: extract just the "Type X is unknown" line.
            m2 = _re.search(r"(Type Error: Type [\w<>!?:\-\+\*/=]+ is unknown[^\n]*)", clean)
            setup_blocker = (m2.group(1) if m2
                             else "Type Error parsing all-types.gc (couldn't parse detail).")
    elif preflight.returncode != 0 and "Compiler Exception" in pre_out:
        setup_blocker = (
            "offline-test compiler setup threw. Last 20 lines of output:\n  "
            + "\n  ".join(pre_out.strip().splitlines()[-20:])
        )

    if setup_blocker:
        print(f"BLOCKER: offline-test setup fails on ALL files.")
        print(f"  {setup_blocker}")
        snap["offline_test"] = {
            "green": [],
            "amber": [],
            "blocked": True,
            "blocker": setup_blocker,
            "candidates": len(candidates),
        }
        LATEST.write_text(json.dumps(snap, indent=2))
        return 0

    results = {"green": [], "amber": [], "amber_reasons": {}}
    import re as _re
    # Capture the one-line reason after "-- Compilation Error! --"
    reason_re = _re.compile(
        r"-- Compilation Error! --\s*\n\x1b?\[[0-9;]*m?\x1b?\[[0-9;]*m?(.+?)\n", _re.DOTALL
    )
    form_re = _re.compile(r"Form:\s*\n\x1b?\[[0-9;]*m?\x1b?\[[0-9;]*m?(.+?)\n", _re.DOTALL)

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
        out = r.stdout + r.stderr
        if r.returncode == 0:
            results["green"].append(name)
        elif "no reference" in out.lower():
            pass
        else:
            results["amber"].append(name)
            # Strip ANSI escape sequences, then extract the error reason and offending form.
            clean = _re.sub(r"\x1b\[[0-9;]*m", "", out)
            reason = "unknown"
            form = ""
            m = _re.search(r"-- Compilation Error! --\s*\n(.+?)\n", clean)
            if m:
                reason = m.group(1).strip()
            m = _re.search(r"Form:\s*\n(.+?)\n", clean)
            if m:
                form = m.group(1).strip()
            elif "diff" in clean.lower() and "---" in clean:
                # REF mismatch (not compile error): extract the first diff chunk.
                reason = "REF mismatch (decomp output differs from checked-in _REF.gc)"
                form = ""
            results["amber_reasons"][name] = {"reason": reason[:180], "form": form[:120]}

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
        "amber_reasons": results.get("amber_reasons", {}),
        "candidates": len(candidates),
    }
    LATEST.write_text(json.dumps(snap, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
