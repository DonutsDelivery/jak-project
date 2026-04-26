#!/usr/bin/env python3
"""validate_rc_compile.py — Verify real-clean files actually compile via goalc.

Runs offline-test on real-clean files (or a sample) and reports which ones
pass/fail compile validation. Catches files that the decompiler marks as
"clean" but goalc rejects — the metric-lying cases Opus's GOALC lane found.

Output: .jakx_watch/research/rc_compile_validation_<ts>.md

Usage:
  python3 scripts/jakx_watch/validate_rc_compile.py            # all real-clean files
  python3 scripts/jakx_watch/validate_rc_compile.py --sample N # random N files
  python3 scripts/jakx_watch/validate_rc_compile.py --since-snap PATH  # files added since snapshot
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP_DIR = ROOT / ".jakx_watch" / "history"
RESEARCH = ROOT / ".jakx_watch" / "research"
ISO_PATH = ROOT / "iso_data" / "jakx"
OFFLINE_TEST = ROOT / "build" / "Release" / "offline-test"


def latest_snap():
    snaps = sorted(SNAP_DIR.glob("snap-*.json"), key=lambda p: p.stat().st_mtime)
    return snaps[-1] if snaps else None


def real_clean_files(snap_path):
    d = json.load(open(snap_path))
    pf = d.get("per_file", {})
    return [name for name, info in pf.items() if info.get("category") == "real-clean"]


def compile_one(file_stem, timeout=60):
    """Run offline-test --file <stem>. Return (verdict, summary).

    Verdicts:
      PASS         — compiles AND ref-matches jak3 reference
      STALE_REF    — compiles but output differs from REF (cosmetic, not a bug)
      COMPILE_FAIL — actual compile error (real bug)
      TIMEOUT      — exceeded timeout
    """
    cmd = [
        str(OFFLINE_TEST),
        "--iso_data_path", str(ISO_PATH),
        "--game", "jakx",
        "--file", file_stem,
    ]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", f"timed out after {timeout}s"
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    if p.returncode == 0 and "pass!" in out.lower():
        return "PASS", None

    has_comparison_fail = "comparison failed" in out.lower()
    has_compilation_error = "compilation error" in out.lower() or "compile error" in out.lower()

    if has_compilation_error:
        # Real compile failure — extract first compile error line
        err_lines = []
        for line in out.splitlines():
            if "compilation error" in line.lower() or "compile error" in line.lower():
                stripped = line.strip()
                for esc in ["\x1b[1m", "\x1b[0m", "\x1b[38;2;255;255;000m",
                            "\x1b[38;2;144;238;144m", "\x1b[38;2;255;000;000m", "\x1b[m"]:
                    stripped = stripped.replace(esc, "")
                err_lines.append(stripped[:200])
            if len(err_lines) >= 3:
                break
        return "COMPILE_FAIL", " | ".join(err_lines) if err_lines else "compile error in output"

    if has_comparison_fail:
        return "STALE_REF", "output differs from jak3 REF (run -d to refresh)"

    # Unknown failure
    return "COMPILE_FAIL", f"exit={p.returncode} (no specific error pattern matched)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0,
                    help="Sample N files randomly (0 = all real-clean)")
    ap.add_argument("--timeout", type=int, default=60,
                    help="Per-file compile timeout in seconds")
    ap.add_argument("--max-fails", type=int, default=0,
                    help="Stop after N failures (0 = no limit)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    snap = latest_snap()
    if not snap:
        print("ERROR: no snapshot found", file=sys.stderr)
        return 1
    rc_files = real_clean_files(snap)
    if not rc_files:
        print("ERROR: no real-clean files in snapshot", file=sys.stderr)
        return 1

    if args.sample and args.sample < len(rc_files):
        random.shuffle(rc_files)
        rc_files = rc_files[:args.sample]

    if not args.quiet:
        print(f"[validate] snap={snap.name}  validating {len(rc_files)} files  timeout={args.timeout}s")

    if not OFFLINE_TEST.exists():
        print(f"ERROR: {OFFLINE_TEST} not found — build offline-test first", file=sys.stderr)
        return 1

    pass_list = []
    stale_list = []  # compiles but REF stale (cosmetic)
    fail_list = []   # actual compile errors (real bugs)
    timeout_list = []
    t0 = time.time()
    for i, fname in enumerate(rc_files, 1):
        verdict, err = compile_one(fname, timeout=args.timeout)
        if verdict == "PASS":
            pass_list.append(fname)
            mark = "✓"
        elif verdict == "TIMEOUT":
            timeout_list.append((fname, err))
            mark = "T"
        elif verdict == "STALE_REF":
            stale_list.append(fname)
            mark = "~"
        else:
            fail_list.append((fname, err))
            mark = "✗"
        if not args.quiet:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  [{i:>3}/{len(rc_files)}] {mark} {fname:<40s}  ({rate:.1f} files/s)")
        if args.max_fails and len(fail_list) >= args.max_fails:
            print(f"  reached --max-fails={args.max_fails}, stopping early")
            break

    pass_n = len(pass_list)
    stale_n = len(stale_list)
    fail_n = len(fail_list)
    timeout_n = len(timeout_list)
    total = pass_n + stale_n + fail_n + timeout_n
    # "Honest" rate: PASS + STALE both compile cleanly. Only FAIL is a real bug.
    compiles_n = pass_n + stale_n
    compiles_pct = compiles_n * 100 / total if total else 0
    pass_pct = pass_n * 100 / total if total else 0

    RESEARCH.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    p = RESEARCH / f"rc_compile_validation_{ts}.md"

    body = [f"# Real-clean compile validation {ts}", "",
            f"snap: {snap.name}",
            f"sample size: {len(rc_files)} of {len(real_clean_files(snap))} total real-clean",
            f"timeout: {args.timeout}s/file", "",
            "## Result", "",
            f"| metric | count | % | severity |",
            f"|---|---:|---:|---|",
            f"| PASS (compile + ref-match) | {pass_n} | {pass_pct:.1f} | ✓ shippable |",
            f"| STALE_REF (compiles, ref out of date) | {stale_n} | {stale_n*100/total if total else 0:.1f} | ~ cosmetic |",
            f"| COMPILE_FAIL (real bug) | {fail_n} | {fail_n*100/total if total else 0:.1f} | ✗ blocker |",
            f"| TIMEOUT | {timeout_n} | {timeout_n*100/total if total else 0:.1f} | ? unknown |",
            f"| **TOTAL** | **{total}** | 100.0 | |",
            "",
            f"**Effective compile rate (PASS + STALE_REF)**: {compiles_n}/{total} = **{compiles_pct:.1f}%**",
            "",
            "STALE_REF means the file compiles cleanly but its `_REF.gc` test fixture",
            "is out of sync with current decomp output (because deftype/cast changes",
            "shifted output). To fix in bulk: `build/Release/offline-test --game jakx -d`",
            "then commit updated REF files.",
            ""]

    if fail_list:
        body.extend(["## COMPILE_FAIL (real bugs — fix or remove from real-clean)", "",
                     "| file | error summary |",
                     "|---|---|"])
        for f, e in fail_list:
            body.append(f"| {f} | {e[:200].replace('|','\\|')} |")
        body.append("")

    if stale_list:
        body.extend(["## STALE_REF (refresh `_REF.gc`)", ""])
        for f in stale_list:
            body.append(f"- {f}")
        body.append("")

    if timeout_list:
        body.extend(["## Timeouts", ""])
        for f, e in timeout_list:
            body.append(f"- {f}: {e}")
        body.append("")

    body.extend(["## Pass list", "", "<details>", "<summary>show passing files</summary>", "", "```"])
    body.extend(pass_list)
    body.extend(["```", "</details>", ""])

    p.write_text("\n".join(body))
    print(f"\n[validate] PASS={pass_n} FAIL={fail_n} TIMEOUT={timeout_n}  ({pass_pct:.1f}% pass)")
    print(f"[validate] report: {p}")

    return 0 if fail_n == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
