#!/usr/bin/env python3
"""Emit a paste-ready deftype stub for a jakx discovery type.

Lookup order:
  1. jak3/all-types.gc        — direct port (preferred; parity is common)
  2. jak2/all-types.gc        — if jak3 doesn't have it
  3. regen/new-all-types.gc   — fall-back (may be #|...|# commented)

Modes:
  --full   : emit the entire jak3 body verbatim (default)
  --min    : emit a MINIMAL stub (parent only, method-count-assert elided,
             no fields) — useful when Session 1 suspects jakx layout differs.

Output goes to stdout with a leading header comment identifying the source,
so Session 1 sees where the body came from.

Usage:
  python3 scripts/jakx_watch/emit_stub.py --name explosion
  python3 scripts/jakx_watch/emit_stub.py --name explosion --min
  python3 scripts/jakx_watch/emit_stub.py --top 10     # batch-emit top N from activation_queue.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAK3_TYPES = ROOT / "decompiler" / "config" / "jak3" / "all-types.gc"
JAK2_TYPES = ROOT / "decompiler" / "config" / "jak2" / "all-types.gc"
JAKX_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
REGEN = ROOT / ".jakx_watch" / "decomp_out" / "jakx" / "new-all-types.gc"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"

RE_ANY = re.compile(r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)\s*")


def _block_comment_mask(lines: list[str]) -> list[bool]:
    in_block = [False] * len(lines)
    block = False
    for idx, line in enumerate(lines):
        if "#|" in line and not block:
            block = True
            in_block[idx] = True
        elif block:
            in_block[idx] = True
            if "|#" in line:
                block = False
        if "#|" in line and "|#" in line.split("#|", 1)[1]:
            block = False
    return in_block


def extract_deftype(path: Path, name: str, prefer_active: bool = True) -> tuple[str, bool] | None:
    """Return (source_text, is_active) for (deftype NAME ...) from path, or None.

    is_active = True iff this occurrence is NOT commented (line or block).
    If the file has multiple occurrences, prefer an active one when prefer_active.
    """
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    mask = _block_comment_mask(lines)
    found: list[tuple[str, bool]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = RE_ANY.match(line)
        if not m or m.group(1) != name:
            i += 1
            continue
        start = i
        line_commented = ";;" in line[: line.find("(deftype")]
        block_commented = mask[i]
        active = not line_commented and not block_commented
        depth = 0
        while i < len(lines):
            raw = lines[i]
            s = re.sub(r"^\s*;;\s?", "", raw) if line_commented else raw
            s = re.sub(r";;.*", "", s)
            for ch in s:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            if depth <= 0 and i > start:
                found.append(("\n".join(lines[start : i + 1]), active))
                i += 1
                break
            i += 1
        else:
            found.append(("\n".join(lines[start:]), active))
    if not found:
        return None
    if prefer_active:
        for body, active in found:
            if active:
                return body, True
    return found[0]


def minimal_stub(body: str, name: str) -> str:
    """Reduce body to (deftype NAME (PARENT) () ). Strips fields + asserts."""
    m = re.search(r"\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(([^)]+)\)", body)
    if not m:
        return body
    parent = m.group(2).strip()
    return (
        f";; MINIMAL STUB — fields + method-count-assert elided.\n"
        f";; Fill in once decomp finds concrete field uses.\n"
        f"(deftype {name} ({parent})\n"
        f"  ()\n"
        f"  )"
    )


def emit_for_name(name: str, minimal: bool) -> str:
    jakx = extract_deftype(JAKX_TYPES, name)
    if jakx and jakx[1]:
        return f";; already active in jakx all-types.gc — no stub needed.\n{jakx[0]}\n"

    for src_label, src_path in [("jak3", JAK3_TYPES), ("jak2", JAK2_TYPES), ("regen", REGEN)]:
        res = extract_deftype(src_path, name)
        if not res:
            continue
        body, _active = res
        header = f";; source: {src_label}/all-types.gc"
        body = re.sub(r"^\s*#\|\s*", "", body)
        body = re.sub(r"\s*\|#\s*$", "", body)
        body = re.sub(r"(?m)^\s*;;\s?", "", body) if src_label != "jak3" and src_label != "jak2" else body
        if minimal:
            return f"{header}  (minimal stub)\n{minimal_stub(body, name)}\n"
        return f"{header}\n{body}\n"
    # Last resort: commented version from jakx itself (block-commented body).
    if jakx:
        body = re.sub(r"^\s*#\|\s*", "", jakx[0])
        body = re.sub(r"\s*\|#\s*$", "", body)
        return (f";; source: jakx all-types.gc (was block-commented — un-commented here)\n"
                f"{body}\n")
    return f";; NOT FOUND: '{name}' in jak3, jak2, or regen.\n"


def load_top(n: int) -> list[str]:
    if not LATEST.exists():
        return []
    snap = json.loads(LATEST.read_text())
    ranked = snap.get("types_drift", {}).get("ranked_discovery", [])
    return [r["name"] for r in ranked[:n]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="deftype name to emit")
    ap.add_argument("--min", action="store_true", help="emit minimal stub (parent-only, no fields)")
    ap.add_argument("--top", type=int, help="batch-emit top N from activation queue")
    args = ap.parse_args()

    if args.top:
        names = load_top(args.top)
        if not names:
            print("no ranked queue — run scripts/jakx_watch/rank_discovery.py first", file=sys.stderr)
            return 1
        out = [
            "# --- jakx activation batch ---",
            f"# scripts/jakx_watch/emit_stub.py --top {args.top}",
            "# paste into decompiler/config/jakx/all-types.gc near related types.",
            "# after pasting, bash scripts/jakx_watch/run.sh to verify no regression.",
            "",
        ]
        for n in names:
            out.append(f";; === {n} ===")
            out.append(emit_for_name(n, args.min))
            out.append("")
        print("\n".join(out))
        return 0

    if not args.name:
        ap.print_help()
        return 1
    print(emit_for_name(args.name, args.min))
    return 0


if __name__ == "__main__":
    sys.exit(main())
