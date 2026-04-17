#!/usr/bin/env python3
"""Triage helper: find every reference to a type name.

When decomp fatal-crashes with "Type X is unknown while parsing ...",
Agents 1/2 need to know the BLAST RADIUS of the name before deciding
whether to:
  * activate X (uncomment its deftype in jakx all-types.gc)
  * declare X forward (`(declare-type X structure)`)
  * remove the references that mention X

This script answers: "where is X used?"

Usage:
  python3 scripts/jakx_watch/type_ref_finder.py collide-list
  python3 scripts/jakx_watch/type_ref_finder.py --auto  # detect from status.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAKX_ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
JAK3_ALL_TYPES = ROOT / "decompiler" / "config" / "jak3" / "all-types.gc"
JAK2_ALL_TYPES = ROOT / "decompiler" / "config" / "jak2" / "all-types.gc"
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
STATUS_MD = ROOT / ".jakx_watch" / "status.md"

RE_FATAL_TYPE = re.compile(r"Type (\S+) is unknown")


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def auto_detect_name() -> str | None:
    """Read status.md banner to extract the failing type name."""
    if not STATUS_MD.exists():
        return None
    text = STATUS_MD.read_text(errors="replace")
    m = RE_FATAL_TYPE.search(text)
    if m:
        return m.group(1)
    return None


def find_in_file(path: Path, name: str, max_lines: int = 30) -> list[tuple[int, str, bool]]:
    """Return list of (line_number, line_text, is_live) where name appears as a word.

    is_live = True when the first occurrence of the name on the line precedes
    any `;;` on that line, meaning the parser will see it (not in a trailing
    comment).
    """
    if not path.exists():
        return []
    # Lisp identifier boundary: Lisp names can contain letters/digits/_-!?<>*+=/
    # so plain \b matches INSIDE identifiers like *collide-list-boxes*. Use a
    # lookaround that treats the superset of identifier chars as "inside".
    LISP_ID_CHARS = r"A-Za-z0-9_\-!?<>*+=/"
    pat = re.compile(
        rf"(?<![{LISP_ID_CHARS}]){re.escape(name)}(?![{LISP_ID_CHARS}])"
    )
    out = []
    for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        m = pat.search(line)
        if not m:
            continue
        # Find the first `;;` in the line (or -1 if none).
        comment_col = line.find(";;")
        is_live = (comment_col == -1) or (m.start() < comment_col)
        # Full-line comment? already handled since comment_col would be 0 and name_col > 0.
        # Inside a block-comment delimiter? cheap heuristic.
        if "#|" in line and line.find("#|") < m.start():
            is_live = False
        out.append((i, line.rstrip(), is_live))
        if len(out) >= max_lines:
            break
    return out


def find_in_decomp_out(decomp_dir: Path, name: str) -> dict[str, int]:
    """Return {file_stem: occurrence_count} for *_disasm.gc files mentioning name."""
    if not decomp_dir.exists():
        return {}
    LISP_ID_CHARS = r"A-Za-z0-9_\-!?<>*+=/"
    pat = re.compile(
        rf"(?<![{LISP_ID_CHARS}]){re.escape(name)}(?![{LISP_ID_CHARS}])"
    )
    out: dict[str, int] = {}
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        text = fp.read_text(errors="replace")
        matches = pat.findall(text)
        if matches:
            out[fp.name[: -len("_disasm.gc")]] = len(matches)
    return out


def find_deftype_body(path: Path, name: str) -> str | None:
    """Return the (deftype NAME ...) body text if present, else None."""
    if not path.exists():
        return None
    text = path.read_text(errors="replace")
    pat = re.compile(rf"^\(deftype\s+{re.escape(name)}\s+", re.MULTILINE)
    m = pat.search(text)
    if not m:
        return None
    start = m.start()
    depth = 1
    i = m.end()
    while i < len(text) and depth > 0:
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        i += 1
    return text[start:i]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?",
                    help="Type name to trace. If omitted, uses --auto to scrape status.md banner.")
    ap.add_argument("--auto", action="store_true",
                    help="Auto-detect type name from the latest FAILED status.md banner.")
    ap.add_argument("--max-refs", type=int, default=30,
                    help="Max references to print per file (default 30).")
    args = ap.parse_args()

    name = args.name
    if not name and args.auto:
        name = auto_detect_name()
        if not name:
            print("auto-detect: no 'Type X is unknown' banner in status.md", file=sys.stderr)
            return 1
        print(f"[auto-detected] fatal type: {name}")
        print()

    if not name:
        ap.error("must supply either positional name or --auto")

    print(f"== references to '{name}' in jakx config ==")
    refs = find_in_file(JAKX_ALL_TYPES, name, args.max_refs)
    live_count = sum(1 for _, _, live in refs if live)
    print(f"decompiler/config/jakx/all-types.gc: {len(refs)} line(s) mention it "
          f"({live_count} LIVE, {len(refs) - live_count} in comments)")
    for ln, text, is_live in refs:
        marker = "L " if is_live else "# "
        print(f"  {marker}{ln:>6}: {text[:180]}")

    print()
    decomp_dir = pick_decomp_dir()
    dec_hits = find_in_decomp_out(decomp_dir, name)
    print(f"== references in decomp output ({decomp_dir.relative_to(ROOT)}) ==")
    if dec_hits:
        for f, c in sorted(dec_hits.items(), key=lambda kv: -kv[1])[:15]:
            print(f"  {c:>3}  {f}")
        if len(dec_hits) > 15:
            print(f"  ... +{len(dec_hits) - 15} more files")
    else:
        print("  (no decomp output currently — decomp may be failing)")

    print()
    print("== prior-game references (for copy-port source) ==")
    for label, path in [("jak3", JAK3_ALL_TYPES), ("jak2", JAK2_ALL_TYPES)]:
        body = find_deftype_body(path, name)
        if body is None:
            print(f"  {label}: no deftype {name} found")
        else:
            first_line = body.splitlines()[0][:160]
            print(f"  {label}: deftype found — {len(body.splitlines())} lines")
            print(f"        first: {first_line}")

    print()
    print("next actions (agents 1/2):")
    live_refs = [(ln, text) for ln, text, live in refs if live]
    print(f"  · live (non-comment) refs in jakx all-types.gc: {len(live_refs)}")
    if live_refs:
        print("    → the live references need a declare-type or full deftype "
              "BEFORE the first reference. Move or forward-declare.")
        first_live = live_refs[0][0]
        print(f"    → earliest live reference is line {first_live}; "
              f"declare-type must precede it.")
    else:
        print("    → only commented refs. Activating the type isn't required unless "
              "you want the methods' docstring sigs parsed.")
    if find_deftype_body(JAK3_ALL_TYPES, name) is not None:
        print(f"  · jak3 has a deftype — port with: "
              f"python3 scripts/jakx_watch/emit_stub.py --name {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
