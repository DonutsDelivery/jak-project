#!/usr/bin/env python3
"""fix_tag_helpers.py — shared helpers for tools that emit return-mismatch
style fix tags ("TYPE::method-N: DECL → ACTUAL ...").

Used by return_mismatch_apply.py and cross_game_return_mismatch_apply.py.
Keeps the parsing logic in one place so both tools agree on what to extract
for: scope (impact_set), blacklist filtering, and bisect-on-revert keys.

Tag format expected:
  "TYPE::METHOD: DECL → ACTUAL [optional trailing context]"
e.g.:
  "process::method-9: none → int (3 callers)"

API:
  parse_fix_tag(tag) -> (type, method, "decl:actual") | None
  extract_edited_types_from_fixes(fixes) -> set[str]
  filter_blacklisted(fixes, game) -> (kept, n_skipped)

The fix tuple is expected to be (line_no, old_line, new_line, tag) — the
shape produced by plan_fixes() in both apply scripts.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import blacklist as _bl  # noqa: E402


def parse_fix_tag(tag: str) -> tuple[str, str, str] | None:
    """Extract (type, method, 'decl:actual') from a fix tag.
    Returns None if the tag doesn't parse.
    """
    try:
        head, rest = tag.split(": ", 1)
        type_part, method = head.split("::", 1)
        decl_actual = rest.split(" → ", 1)
        decl = decl_actual[0].strip()
        actual = decl_actual[1].split(" ", 1)[0].strip()
        return (type_part, method, f"{decl}:{actual}")
    except (ValueError, IndexError):
        return None


def extract_edited_types_from_fixes(fixes: list) -> set[str]:
    """Pull type names out of fix tags. Used for impact_set scoping."""
    out: set[str] = set()
    for f in fixes:
        if len(f) < 4:
            continue
        parsed = parse_fix_tag(f[3])
        if parsed:
            out.add(parsed[0])
    return out


def filter_blacklisted(fixes: list, game: str) -> tuple[list, int]:
    """Drop fixes already on the blacklist. Returns (kept_fixes, n_skipped)."""
    if not fixes:
        return fixes, 0
    kept = []
    skipped = 0
    for f in fixes:
        if len(f) < 4:
            kept.append(f)
            continue
        parsed = parse_fix_tag(f[3])
        if parsed and _bl.is_blacklisted(game, parsed[0], parsed[1], parsed[2]):
            skipped += 1
            continue
        kept.append(f)
    return kept, skipped
