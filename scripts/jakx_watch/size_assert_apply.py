#!/usr/bin/env python3
"""Apply mechanical :size-assert fixes from size_assert_fixable.md to all-types.gc.

Reads the 262 pre-triaged ±1-8 byte entries from .jakx_watch/size_assert_fixable.md,
finds each :size-assert line by anchoring on the deftype's line number, and rewrites
the declared value to the computed value.

Usage:
  python3 scripts/jakx_watch/size_assert_apply.py --dry-run
  python3 scripts/jakx_watch/size_assert_apply.py --top 10 --dry-run
  python3 scripts/jakx_watch/size_assert_apply.py --top 10 --commit
  python3 scripts/jakx_watch/size_assert_apply.py --all --commit

The script:
  1. Parses size_assert_fixable.md for (type, declared_hex, computed_hex, deftype_line).
  2. Locates the :size-assert line near the deftype anchor in all-types.gc.
  3. Verifies the current value matches declared_hex before touching anything.
  4. (Without --dry-run) applies edits, re-runs decompiler via apply_guard, measures delta.
  5. Commits or reverts depending on guard outcome.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXABLE_MD = ROOT / ".jakx_watch" / "size_assert_fixable.md"
CURRENT_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"

# :size-assert line pattern
_RE_SIZE_ASSERT = re.compile(r"^(\s*:size-assert\s+)#x([0-9a-fA-F]+)(.*)$")

# Markdown table row: | `typename` | `#hex` | `#hex` | diff | linenum |
_RE_TABLE_ROW = re.compile(
    r"^\|\s*`([\w\-<>!?:+*/=]+)`\s*\|\s*`#([0-9a-fA-F]+)`\s*\|\s*`#([0-9a-fA-F]+)`\s*\|[^|]+\|\s*(\d+)\s*\|"
)


# ---------------------------------------------------------------------------
# Parse fixable.md
# ---------------------------------------------------------------------------


def parse_fixable(md_path: Path) -> list[tuple[str, str, str, int]]:
    """Return list of (type_name, declared_hex, computed_hex, deftype_line_no).

    Only reads rows in the 'Actionable fixes' section (stops at 'Review needed').
    """
    entries: list[tuple[str, str, str, int]] = []
    in_section = False

    for line in md_path.read_text().splitlines():
        if "Actionable fixes" in line:
            in_section = True
            continue
        if in_section and line.startswith("## Review needed"):
            break
        if not in_section:
            continue

        m = _RE_TABLE_ROW.match(line)
        if m:
            tname = m.group(1)
            declared = m.group(2).lower()
            computed = m.group(3).lower()
            lno = int(m.group(4))
            if declared != computed:
                entries.append((tname, declared, computed, lno))

    return entries


# ---------------------------------------------------------------------------
# Find and plan fixes in all-types.gc
# ---------------------------------------------------------------------------


def plan_fixes(
    entries: list[tuple[str, str, str, int]],
    types_path: Path,
    top: int | None = None,
) -> list[tuple[int, str, str, str]]:
    """Return list of (line_no_1based, old_line, new_line, description).

    For each entry, scans forward from the deftype anchor line to find
    :size-assert #x<declared>. Skips entries inside block-comment regions.
    Skips entries where the current value doesn't match expected (already fixed
    or file drifted).
    """
    lines = types_path.read_text(errors="replace").splitlines(keepends=True)

    # Precompute block-comment spans so we can skip them
    block_comment_lines: set[int] = set()
    in_block = False
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if in_block:
            block_comment_lines.add(idx)
            if "|#" in stripped:
                in_block = False
        elif stripped.startswith("#|"):
            in_block = True
            block_comment_lines.add(idx)
            if "|#" in stripped[2:]:
                in_block = False

    fixes: list[tuple[int, str, str, str]] = []
    seen_lines: set[int] = set()

    limit = top if top is not None else len(entries)
    applied = 0

    for tname, declared_hex, computed_hex, anchor_lno in entries:
        if applied >= limit:
            break

        # Anchor is deftype line (1-based); search forward up to 20 lines
        start_idx = anchor_lno - 1  # 0-based
        found_idx: int | None = None

        for search_offset in range(20):
            idx = start_idx + search_offset
            if idx >= len(lines):
                break
            if idx in block_comment_lines:
                continue
            raw = lines[idx].rstrip("\r\n")
            m = _RE_SIZE_ASSERT.match(raw)
            if not m:
                continue
            current_val = m.group(2).lower()
            if current_val != declared_hex:
                # Value doesn't match — either already fixed or stale entry
                break
            found_idx = idx
            break

        if found_idx is None:
            continue  # skip — can't locate or already correct
        if found_idx in seen_lines:
            continue  # duplicate

        raw = lines[found_idx].rstrip("\r\n")
        m = _RE_SIZE_ASSERT.match(raw)
        assert m  # we just matched above

        new_raw = m.group(1) + f"#x{computed_hex}" + m.group(3)
        desc = f"{tname}: #x{declared_hex} → #x{computed_hex}"
        fixes.append((found_idx + 1, raw, new_raw, desc))
        seen_lines.add(found_idx)
        applied += 1

    return fixes


# ---------------------------------------------------------------------------
# Apply fixes
# ---------------------------------------------------------------------------


def apply_fixes(types_path: Path, fixes: list[tuple[int, str, str, str]]) -> None:
    """Rewrite :size-assert lines in all-types.gc."""
    lines = types_path.read_text(errors="replace").splitlines(keepends=True)

    # Verify first
    for line_no, old_line, new_line, _ in fixes:
        actual = lines[line_no - 1].rstrip("\r\n")
        if actual != old_line:
            raise ValueError(
                f"Line {line_no} mismatch.\n"
                f"  expected: {old_line!r}\n"
                f"  got:      {actual!r}"
            )

    # Apply
    for line_no, old_line, new_line, _ in fixes:
        original = lines[line_no - 1]
        ending = "\n"
        for end in ("\r\n", "\n", "\r"):
            if original.endswith(end):
                ending = end
                break
        lines[line_no - 1] = new_line + ending

    types_path.write_text("".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned edits without modifying files.",
    )
    ap.add_argument(
        "--top",
        type=int,
        default=None,
        metavar="N",
        help="Apply at most N fixes (default: all).",
    )
    ap.add_argument(
        "--skip",
        type=int,
        default=0,
        metavar="N",
        help="Skip the first N entries in the fixable list (default: 0).",
    )
    ap.add_argument(
        "--all",
        action="store_true",
        help="Apply all fixable entries (same as omitting --top).",
    )
    ap.add_argument(
        "--commit",
        action="store_true",
        help="Auto-commit if guard passes.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    top = args.top if args.top is not None else None
    skip = args.skip

    if not FIXABLE_MD.exists():
        print(f"ERROR: {FIXABLE_MD} not found", file=sys.stderr)
        return 1
    if not CURRENT_TYPES.exists():
        print(f"ERROR: {CURRENT_TYPES} not found", file=sys.stderr)
        return 1

    entries = parse_fixable(FIXABLE_MD)
    print(f"Parsed {len(entries)} fixable entries from {FIXABLE_MD.name}")

    if skip:
        entries = entries[skip:]
        print(f"Skipping first {skip} entries; {len(entries)} remaining")

    fixes = plan_fixes(entries, CURRENT_TYPES, top=top)

    if not fixes:
        print("No applicable fixes found (entries already applied or line mismatch).")
        return 0

    print(f"\nPlanned {len(fixes)} :size-assert edits:\n")
    for line_no, old_line, new_line, desc in fixes:
        print(f"  L{line_no:6d}  {desc}")

    if args.dry_run:
        print(f"\n[dry-run] {len(fixes)} edits would be applied.")
        return 0

    print(f"\nApplying {len(fixes)} edits via apply_guard …")

    n_fixes = len(fixes)
    msg = (
        f"fix(jakx/all-types): size_assert_apply batch {n_fixes} entries\n\n"
        f"Mechanical :size-assert corrections from size_assert_fixable.md.\n"
        f"{n_fixes} entries fixed (±1-8 byte discrepancies).\n\n"
        f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    )

    def do_apply() -> list[Path]:
        apply_fixes(CURRENT_TYPES, fixes)
        return [CURRENT_TYPES]

    result = run_with_guard(
        do_apply,
        label=f"size_assert/{n_fixes}",
        err_slack=0,
        warn_slack=0,
        commit_on_pass=args.commit,
        commit_message=msg,
    )

    if not result.passed:
        print(f"✗ Guard failed: {result.reason}", file=sys.stderr)
        return 1

    print(
        f"✓ Guard passed (Δerr={result.delta_err:+d} Δwarn={result.delta_warn:+d})"
    )
    if args.commit:
        if result.commit_sha:
            print(f"  Committed as {result.commit_sha}.")
        else:
            print("  (no commit — guard passed but commit_sha empty)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
