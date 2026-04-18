#!/usr/bin/env python3
"""Scan all-types.gc for define-extern clobbers.

A 'clobber' is a (define-extern FOO <type>) that appears after line 59000 where
(deftype FOO ...) was already defined and is active (not block/line commented).

GOAL processes all-types.gc top-to-bottom.  A late define-extern overwrites the
type entry, turning it into 'object' (or whatever type the extern uses), which
causes typecheck failures in REF files that depend on that type.

This scanner is static — it only reads all-types.gc, no decomp run needed.

Output:
  .jakx_watch/clobber_queue.md   — all active clobbers with file/line context
  stdout                         — summary counts
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
OUTPUT_MD = ROOT / ".jakx_watch" / "clobber_queue.md"

# line threshold: define-extern entries before this are considered normal forward-decls
CLOBBER_THRESHOLD = 59000

RE_DEFTYPE = re.compile(r"^\s*\(deftype\s+([\w<>!?:\-\+\*/=]+)\s*\((\S+)\)")
RE_DEFINE_EXTERN = re.compile(
    r"^\s*\(define-extern\s+([\w<>!?:\-\+\*/=]+)\s+(\S+)\s*\)"
)
RE_LINE_COMMENT = re.compile(r"^\s*;;")


def scan(text: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (active_deftypes, active_clobbers, already_fixed_clobbers).

    active_deftypes   — deftypes that are active (not commented), with line number
    active_clobbers   — define-extern at line>THRESHOLD that clobber an active deftype
    already_fixed     — commented-out define-extern that WOULD have been a clobber
    """
    lines = text.splitlines()

    # Build block-comment map
    in_block = [False] * len(lines)
    block = False
    for idx, raw in enumerate(lines):
        if "#|" in raw:
            # Check for same-line open+close
            after_open = raw.split("#|", 1)[1]
            if "|#" in after_open:
                # Inline block comment — mark only this line
                in_block[idx] = True
                continue
            block = True
        if block:
            in_block[idx] = True
            if "|#" in raw:
                block = False

    # First pass: collect all active deftypes (line number + parent)
    active_deftype: dict[str, dict] = {}   # name → {line, parent, active}
    all_deftype: dict[str, dict] = {}      # name → {line, parent, commented, block_commented}

    for idx, raw in enumerate(lines):
        lineno = idx + 1
        if in_block[idx]:
            m = RE_DEFTYPE.match(raw.lstrip())
            if m:
                name, parent = m.group(1), m.group(2)
                if name not in all_deftype:
                    all_deftype[name] = {
                        "line": lineno, "parent": parent,
                        "commented": False, "block_commented": True,
                    }
            continue
        if RE_LINE_COMMENT.match(raw):
            # Could be ";; (deftype ...)"
            m = RE_DEFTYPE.match(raw.lstrip().lstrip(";").lstrip())
            if m:
                name, parent = m.group(1), m.group(2)
                if name not in all_deftype:
                    all_deftype[name] = {
                        "line": lineno, "parent": parent,
                        "commented": True, "block_commented": False,
                    }
            continue
        m = RE_DEFTYPE.match(raw)
        if m:
            name, parent = m.group(1), m.group(2)
            rec = {"line": lineno, "parent": parent, "commented": False, "block_commented": False}
            # If already recorded as inactive, active version wins
            existing = all_deftype.get(name)
            if existing is None or (existing["commented"] or existing["block_commented"]):
                all_deftype[name] = rec
            active_deftype[name] = rec

    # Second pass: collect define-extern entries at line > CLOBBER_THRESHOLD
    active_clobbers: list[dict] = []
    already_fixed: list[dict] = []

    for idx, raw in enumerate(lines):
        lineno = idx + 1
        if lineno <= CLOBBER_THRESHOLD:
            continue

        # Check if this line (or the line commented variant) is a define-extern
        is_line_commented = RE_LINE_COMMENT.match(raw) is not None
        is_block_commented = in_block[idx]

        check_line = raw
        if is_line_commented:
            # Strip leading ;; to test the underlying form
            check_line = re.sub(r"^\s*;;\s*", "", raw)

        m = RE_DEFINE_EXTERN.match(check_line)
        if not m:
            continue

        name, extern_type = m.group(1), m.group(2)

        # Only care about clobbers of active deftypes
        deftype_rec = active_deftype.get(name)
        if deftype_rec is None:
            continue  # No active deftype — not a clobber

        # It IS a clobber (define-extern after active deftype)
        rec = {
            "name": name,
            "extern_type": extern_type,
            "deftype_line": deftype_rec["line"],
            "extern_line": lineno,
            "parent": deftype_rec["parent"],
            "line_commented": is_line_commented,
            "block_commented": is_block_commented,
        }
        if is_line_commented or is_block_commented:
            already_fixed.append(rec)
        else:
            active_clobbers.append(rec)

    active_deftypes = list(active_deftype.values())
    return active_deftypes, active_clobbers, already_fixed


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--types", default=str(ALL_TYPES))
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    types_path = Path(args.types)
    text = types_path.read_text(errors="replace")

    _active_dt, active_clobbers, already_fixed = scan(text)

    active_clobbers.sort(key=lambda r: r["extern_line"])

    print(f"define-extern clobbers (active, line>{CLOBBER_THRESHOLD}): {len(active_clobbers)}")
    print(f"already-fixed clobbers (commented-out):                   {len(already_fixed)}")

    if active_clobbers:
        print("\nActive clobbers (A1/A2: comment these out):")
        for r in active_clobbers:
            print(f"  L{r['extern_line']:>6}  (define-extern {r['name']} {r['extern_type']})  "
                  f"← deftype at L{r['deftype_line']}")

    if args.no_write:
        return 0

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    md_lines = [
        "# jakx all-types.gc — define-extern clobber queue",
        "",
        f"_source: `scripts/jakx_watch/clobber_scan.py`  ·  "
        f"threshold: line>{CLOBBER_THRESHOLD}_",
        "",
        "A **clobber** is a `(define-extern FOO object)` (or similar) that appears "
        "after line 59000, where `(deftype FOO ...)` is already active earlier in the "
        "file. GOAL processes top-to-bottom, so the late `define-extern` overwrites the "
        "type as `object`, causing typecheck failures in any REF file that depends on it.",
        "",
        "**Fix for A1/A2**: comment out each active-clobber line with `;;`.",
        "",
    ]

    if active_clobbers:
        md_lines += [
            f"## Active clobbers ({len(active_clobbers)}) — need to be commented out",
            "",
            "| extern_line | type name | extern_type | deftype_line | parent |",
            "|------------:|-----------|-------------|-------------:|--------|",
        ]
        for r in active_clobbers:
            md_lines.append(
                f"| L{r['extern_line']} | `{r['name']}` | `{r['extern_type']}` "
                f"| L{r['deftype_line']} | `{r['parent']}` |"
            )
        md_lines.append("")
    else:
        md_lines += ["## Active clobbers — none found ✓", ""]

    md_lines += [
        f"## Already-fixed clobbers ({len(already_fixed)}) — commented out",
        "",
        "These were previously active clobbers that have been fixed by commenting "
        "out the `define-extern` line.",
        "",
        "| extern_line | type name | extern_type | deftype_line |",
        "|------------:|-----------|-------------|-------------:|",
    ]
    for r in sorted(already_fixed, key=lambda r: r["extern_line"]):
        md_lines.append(
            f"| L{r['extern_line']} | `{r['name']}` | `{r['extern_type']}` "
            f"| L{r['deftype_line']} |"
        )
    md_lines.append("")

    md_lines += [
        "## How to use",
        "",
        "Run any time after all-types.gc is modified:",
        "```bash",
        "python3 scripts/jakx_watch/clobber_scan.py",
        "```",
        "",
        "The scanner is static — no decomp run required.  "
        "Add it to `run.sh` if you want it in every cycle.",
    ]

    OUTPUT_MD.write_text("\n".join(md_lines) + "\n")
    print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
