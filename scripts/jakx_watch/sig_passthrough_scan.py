#!/usr/bin/env python3
"""sig_passthrough_scan.py — Detect under-declared method signatures.

Pattern: ;; ERROR: Function may read a register that is not set: aN

Source: Sonnet's discovery in nav-engine method 13 / nav-mesh method 24
where the method signature in all-types.gc declared fewer params than
the caller passed through (e.g. method declared (_type_) but caller
also passes a2/a3 via passthrough). Opus mass-applied this for debug-h
in cycle 14.

This script:
  1. Greps IR2 outputs for "Function may read a register that is not set: aN"
  2. For each hit, identifies the enclosing function/method
  3. Looks up the current signature in all-types.gc
  4. Counts how many register reads are missing (a2 → param 1 missing,
     a3 → params 1+2 missing, etc.)
  5. Outputs candidates to a queue for an agent to apply

Output: .jakx_watch/research/sig_passthrough_candidates_<ts>.md

Usage:
  python3 scripts/jakx_watch/sig_passthrough_scan.py [--max-list N]
"""
from __future__ import annotations

import argparse
import re
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECOMP_OUT = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
RESEARCH = ROOT / ".jakx_watch" / "research"
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"

ERROR_RE = re.compile(
    r";;\s*ERROR:\s*Function may read a register that is not set:\s*(a\d)"
)
FUNC_HEADER_RE = re.compile(r"^;\s*\.function\s+(.+)$")
METHOD_HEADER_RE = re.compile(r"^;\s*\.function\s+\((method|new) (\d+) (\S+)\)")

# Param-register order for MIPS calling conv (a0=this, a1..a3=params, t0+ for more)
ARG_REGS = ["a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3"]


def find_failing_function(ir2_text: str, error_line_no: int) -> str | None:
    """Walk backward from error line to find the enclosing .function header."""
    lines = ir2_text.splitlines()
    for i in range(error_line_no, max(0, error_line_no - 200), -1):
        line = lines[i]
        m = FUNC_HEADER_RE.match(line)
        if m:
            return m.group(1).strip()
    return None


def scan_file(ir2_path: Path) -> list[dict]:
    """Return list of candidates found in this IR2 file."""
    text = ir2_path.read_text(errors="replace")
    candidates = []
    for i, line in enumerate(text.splitlines()):
        m = ERROR_RE.search(line)
        if not m:
            continue
        bad_reg = m.group(1)
        func = find_failing_function(text, i)
        if not func:
            continue
        # arg index from a-N
        try:
            arg_idx = ARG_REGS.index(bad_reg)
        except ValueError:
            continue
        candidates.append({
            "file": ir2_path.stem.replace("_ir2", ""),
            "function": func,
            "missing_reg": bad_reg,
            "min_params_needed": arg_idx,  # a2 → 2 params (a1+a2), a3 → 3, etc.
        })
    return candidates


def lookup_method_sig(func_name: str, all_types_text: str) -> str | None:
    """Find the method signature line in all-types.gc for a (method N type) form."""
    m = re.match(r"\((method|new)\s+(\d+)\s+(\S+)\)", func_name)
    if not m:
        return None
    method_num = m.group(2)
    type_name = m.group(3)
    # Find deftype block
    deftype_re = re.compile(r"\(deftype\s+" + re.escape(type_name) + r"\s+\(")
    dm = deftype_re.search(all_types_text)
    if not dm:
        return None
    # Find method line within next ~5000 chars
    block_end = all_types_text.find("(deftype ", dm.end())
    if block_end == -1:
        block_end = len(all_types_text)
    block = all_types_text[dm.start():block_end]
    sig_re = re.compile(
        r"\((\S+)\s+\((_type_[^)]*)\)[^)]*\)\s*;;\s*" + method_num + r"\b"
    )
    sm = sig_re.search(block)
    if sm:
        return sm.group(0)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-list", type=int, default=50,
                    help="Cap the candidate list output")
    ap.add_argument("--game", default="jakx",
                    choices=("jak1", "jak2", "jak3", "jakx"),
                    help="Target game (default: jakx, uses .jakx_watch/decomp_out)")
    args = ap.parse_args()

    # For non-jakx games, use decompiler_out/<game>/ + game-specific all-types.gc
    global DECOMP_OUT, ALL_TYPES
    if args.game != "jakx":
        DECOMP_OUT = ROOT / "decompiler_out" / args.game
        ALL_TYPES = ROOT / "decompiler" / "config" / args.game / "all-types.gc"

    print(f"[{args.game}] Scanning IR2 outputs for passthrough-arg signature gaps ...")
    files = sorted(DECOMP_OUT.glob("*_ir2.asm"))
    all_candidates = []
    per_file_count = defaultdict(int)
    for fp in files:
        cands = scan_file(fp)
        all_candidates.extend(cands)
        per_file_count[fp.stem.replace("_ir2", "")] += len(cands)

    print(f"  scanned {len(files)} files, {len(all_candidates)} candidates")

    # Dedupe by (function, missing_reg) — multiple errors in one function
    seen = {}
    for c in all_candidates:
        key = (c["function"], c["missing_reg"])
        if key not in seen or seen[key]["min_params_needed"] < c["min_params_needed"]:
            seen[key] = c
    candidates = list(seen.values())
    candidates.sort(key=lambda c: (-c["min_params_needed"], c["file"]))

    print(f"  {len(candidates)} unique (function, reg) pairs")

    # Try to look up current method signatures
    all_types_text = ALL_TYPES.read_text(errors="replace") if ALL_TYPES.exists() else ""
    for c in candidates[: args.max_list]:
        c["current_sig"] = lookup_method_sig(c["function"], all_types_text)

    RESEARCH.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    out = RESEARCH / f"sig_passthrough_candidates_{ts}.md"

    body = ["# Passthrough-arg signature candidates", "",
            f"Generated: {ts}", f"Total candidates: {len(candidates)}",
            "Pattern: `Function may read a register that is not set: aN`",
            "",
            "Recipe (per Sonnet's nav-engine fix + Opus's debug-h cycle 14):",
            "1. Find the method's deftype line in all-types.gc",
            "2. Add the missing param(s) to the method signature",
            "3. Type guess: check jak3's matching signature first; else use `object`",
            "4. Decomp + verify error gone + rc grew",
            "",
            "## Top candidates", "",
            "| file | function | missing_reg | min_params | current_sig |",
            "|---|---|---|---:|---|"]

    for c in candidates[: args.max_list]:
        sig = (c.get("current_sig") or "—").replace("|", "\\|")
        body.append(f"| {c['file']} | `{c['function']}` | {c['missing_reg']} | "
                    f"{c['min_params_needed']} | `{sig}` |")

    body.extend(["", "## Files most affected", ""])
    file_counts = sorted(per_file_count.items(), key=lambda x: -x[1])
    for f, n in file_counts[:20]:
        if n > 0:
            body.append(f"- {f}: {n} errors")

    out.write_text("\n".join(body))
    print(f"\nWrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
