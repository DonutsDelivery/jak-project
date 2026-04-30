#!/usr/bin/env python3
"""Measure goalc compile-pass rate for all emitted jakx files.

Runs offline-test per file (without --fail-on-cmp) to distinguish:
  - compile-pass: goalc accepted the decompiled GOAL output
  - compile-fail: goalc rejected it (Compilation Error)
  - skip-compile: in offline-test skip_compile_files list (known non-compilers)
  - no-dgo: file's DGO not in offline-test config (shouldn't happen after config update)

This gives the TRUE ceiling on decompilation correctness: a file can only be
correct if goalc can compile it. The current pass metric (offline_test green)
measures compile+REF-match, but REF files are AI-seeded for jakx — so compile-pass
is the honest lower bound.

Usage:
  python3 scripts/jakx_watch/goalc_compile_audit.py [--threads N] [--cat CATEGORY]

  --threads N    parallel offline-test processes (default: 6)
  --cat CATEGORY only test files from this snapshot category (default: all except real-partial)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_TEST = ROOT / "build" / "Release" / "offline-test"
ISO_DIR = ROOT / "iso_data" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
AUDIT_OUT = ROOT / ".jakx_watch" / "history" / "compile_audit_latest.json"

# Files that the offline-test config explicitly skips compiling.
# We mark these as skip-compile rather than compile-fail.
_SKIP_COMPILE_FILES: frozenset[str] = frozenset({
    "types-h", "hfrag-h", "joint", "subdivide", "shadow-cpu-h", "foreground",
    "tie-methods", "scene-actor", "game-task-h",
})


def run_one(name: str, timeout: int = 90) -> dict:
    r = subprocess.run(
        [
            str(OFFLINE_TEST),
            "--iso_data_path", str(ISO_DIR),
            "--game", "jakx",
            "--file", name,
            # No --fail-on-cmp: we only care about compile, not REF match
        ],
        capture_output=True, text=True, check=False, timeout=timeout,
    )
    out = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)

    if "not one of these is in our list" in out:
        return {"name": name, "result": "no-dgo", "detail": ""}

    if name in _SKIP_COMPILE_FILES:
        # Even if it passed, record as skip-compile for honest accounting
        return {"name": name, "result": "skip-compile", "detail": ""}

    if r.returncode == 0:
        return {"name": name, "result": "compile-pass", "detail": ""}

    # Compile failure
    m = re.search(r"-- Compilation Error! --\s*\n(.+?)\n", out)
    detail = m.group(1).strip()[:200] if m else out.strip()[-200:]
    return {"name": name, "result": "compile-fail", "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--cat", default=None,
                        help="only test files from this snapshot category")
    parser.add_argument("--skip-partial", action="store_true", default=True,
                        help="skip real-partial files (they always fail) for speed")
    parser.add_argument("--include-partial", action="store_true",
                        help="include real-partial files (slow, expected 0 pass)")
    args = parser.parse_args()

    if not OFFLINE_TEST.exists():
        print("ERROR: offline-test binary missing — build it first")
        return 1
    if not ISO_DIR.exists():
        print(f"ERROR: iso_data/jakx missing at {ISO_DIR}")
        return 1
    if not LATEST.exists():
        print("ERROR: latest.json missing — run measure.py first")
        return 1

    snap = json.loads(LATEST.read_text())
    per_file = snap["per_file"]

    skip_cats = set()
    if not args.include_partial:
        skip_cats.add("real-partial")

    if args.cat:
        files = [n for n, v in per_file.items() if v["category"] == args.cat]
    else:
        files = [n for n, v in per_file.items() if v["category"] not in skip_cats]

    total = len(per_file)
    testing = len(files)
    skipped_partial = sum(1 for v in per_file.values() if v["category"] == "real-partial")

    print(f"Jakx goalc compile-pass audit")
    print(f"  Total emitted files: {total}")
    print(f"  Files to test: {testing} (skipping {skipped_partial} real-partial — expected 0 pass)")
    print(f"  Threads: {args.threads}")
    print()

    results: list[dict] = []
    done = 0

    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futs = {pool.submit(run_one, name): name for name in sorted(files)}
        for fut in as_completed(futs):
            res = fut.result()
            results.append(res)
            done += 1
            status = res["result"]
            sym = {"compile-pass": "✓", "compile-fail": "✗", "skip-compile": "~", "no-dgo": "?"}.get(status, "?")
            cat = per_file[res["name"]]["category"]
            print(f"  [{done:3d}/{testing}] {sym} {res['name']} ({cat})", flush=True)

    # Summarize by category
    by_cat: dict[str, dict[str, int]] = {}
    for r in results:
        cat = per_file[r["name"]]["category"]
        res = r["result"]
        if cat not in by_cat:
            by_cat[cat] = {}
        by_cat[cat][res] = by_cat[cat].get(res, 0) + 1

    compile_pass = [r for r in results if r["result"] == "compile-pass"]
    compile_fail = [r for r in results if r["result"] == "compile-fail"]
    skip_compile = [r for r in results if r["result"] == "skip-compile"]
    no_dgo = [r for r in results if r["result"] == "no-dgo"]

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"  compile-pass  : {len(compile_pass):3d}  (goalc accepted the decompiled GOAL)")
    print(f"  compile-fail  : {len(compile_fail):3d}  (goalc rejected — needs fix)")
    print(f"  skip-compile  : {len(skip_compile):3d}  (known non-compilers, intentionally skipped)")
    print(f"  no-dgo        : {len(no_dgo):3d}  (DGO not in offline-test config — fix config)")
    print()
    print("By category:")
    for cat, counts in sorted(by_cat.items()):
        total_cat = sum(counts.values())
        pass_ct = counts.get("compile-pass", 0)
        fail_ct = counts.get("compile-fail", 0)
        skip_ct = counts.get("skip-compile", 0)
        print(f"  {cat:20s}: {pass_ct} pass / {fail_ct} fail / {skip_ct} skip  (of {total_cat})")

    if args.include_partial:
        grand_total = total
    else:
        grand_total = testing + skipped_partial
    compile_total = len(compile_pass)
    print()
    print(f"Compile-pass rate: {compile_total}/{grand_total} = {100*compile_total/grand_total:.1f}%")
    print(f"  (ceiling on what current decompilation can possibly be correct about)")

    if compile_fail:
        print()
        print(f"Top compile-fail reasons:")
        fail_reasons: dict[str, int] = {}
        for r in compile_fail:
            detail = r["detail"][:80]
            fail_reasons[detail] = fail_reasons.get(detail, 0) + 1
        for reason, count in sorted(fail_reasons.items(), key=lambda x: -x[1])[:15]:
            print(f"  {count:3d}x  {reason}")

    # Save results
    audit_data = {
        "ts": snap.get("ts"),
        "git_sha": snap.get("git_sha"),
        "total_emitted": total,
        "tested": testing,
        "skipped_partial": skipped_partial,
        "compile_pass": [r["name"] for r in compile_pass],
        "compile_fail": [r["name"] for r in compile_fail],
        "skip_compile": [r["name"] for r in skip_compile],
        "no_dgo": [r["name"] for r in no_dgo],
        "compile_fail_detail": {r["name"]: r["detail"] for r in compile_fail},
        "by_category": by_cat,
        "compile_pass_rate": f"{compile_total}/{grand_total}",
    }
    AUDIT_OUT.write_text(json.dumps(audit_data, indent=2))
    print()
    print(f"Saved to: {AUDIT_OUT.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
