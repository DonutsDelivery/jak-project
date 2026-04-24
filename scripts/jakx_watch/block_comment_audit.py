#!/usr/bin/env python3
"""Detect deftypes accidentally disabled by unmatched `#| ... |#` block comments.

When a developer removes the opening `#|` to activate a deftype but forgets to
remove the closing `|#`, the deftype stays silently commented out. This causes
"unknown type" errors hours later after other changes build on the false sense
that the type is active.

This script parses all-types.gc, tracks block-comment nesting depth, and flags
every deftype that looks "real" (not marked as dead/duplicate, has a real
:size-assert) but is stranded inside an active `#| ... |#` block.

Output:
  * .jakx_watch/block_comment_audit.md — detailed table of at-risk cases
  * stdout summary
  * exit code 1 if at-risk cases found, 0 if clean
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
AUDIT_MD = ROOT / ".jakx_watch" / "block_comment_audit.md"

RE_DEFTYPE = re.compile(r"^\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(")
RE_SIZE_ASSERT = re.compile(r":size-assert\s+#x([0-9a-fA-F]+)")


def should_skip_deftype(deftype_name: str) -> bool:
    """Check if deftype name has markers that indicate it's intentionally dead."""
    skip_markers = ["-FULL-PENDING", "-OLD-REGEN", "-DEAD", "-DUP"]
    return any(marker in deftype_name for marker in skip_markers)


def scan_deftype_block(lines: list[str], start_line_no: int) -> tuple[bool, str | None]:
    """
    Scan a deftype block starting at start_line_no.

    Returns:
      (is_real_looking, size_assert_value)

    A "real-looking" deftype has:
      - A non-zero :size-assert value
      - No `;; DEAD:` or `;; SCAFFOLD` marker on the preceding comment line
    """
    # Look at the previous line for death markers
    if start_line_no > 0:
        prev_line = lines[start_line_no - 1]
        if ";; DEAD:" in prev_line or ";; SCAFFOLD" in prev_line:
            return (False, None)

    # Scan forward for :size-assert within the deftype block
    # Assume block ends at the first closing paren after opening (simplification)
    paren_depth = 1
    for i in range(start_line_no, min(start_line_no + 100, len(lines))):
        line = lines[i]

        # Count parentheses to track when deftype block ends
        paren_depth += line.count("(") - line.count(")")
        if paren_depth <= 0:
            break

        # Look for :size-assert
        m = RE_SIZE_ASSERT.search(line)
        if m:
            size_hex = m.group(1)
            # Skip if it's zero
            if size_hex == "0":
                return (False, None)
            return (True, f"#x{size_hex}")

    # No :size-assert found — not a real deftype
    return (False, None)


def find_block_comment_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """
    Find all block comment ranges (start_line, end_line) as line numbers (1-indexed).

    Handles nested `#| ... |#` comments. Returns list of (open_line, close_line).
    Opens may not be closed — caller should handle unclosed blocks.
    """
    ranges = []
    stack = []  # Stack of opening line numbers for nested comments

    for i, line in enumerate(lines):
        lineno = i + 1  # 1-indexed

        # Count #| and |# on this line, handling both
        # Simple approach: count them, track nesting
        open_count = line.count("#|")
        close_count = line.count("|#")

        for _ in range(open_count):
            stack.append(lineno)

        for _ in range(close_count):
            if stack:
                open_lineno = stack.pop()
                ranges.append((open_lineno, lineno))

    # Unclosed blocks: if stack is non-empty, those are still open at EOF
    # Mark them as (open_line, len(lines))
    for open_lineno in stack:
        ranges.append((open_lineno, len(lines)))

    return ranges


def line_in_block(lineno: int, ranges: list[tuple[int, int]]) -> bool:
    """Check if a line is inside any of the given block comment ranges."""
    for open_line, close_line in ranges:
        if open_line < lineno <= close_line:
            return True
    return False


def main() -> int:
    if not CURRENT_TYPES.exists():
        print(f"ERROR: {CURRENT_TYPES} not found", file=sys.stderr)
        return 1

    lines = CURRENT_TYPES.read_text(errors="replace").splitlines()

    # Find all block comment ranges
    block_ranges = find_block_comment_ranges(lines)

    # Scan for deftypes inside block comments
    at_risk: list[dict] = []

    for i, line in enumerate(lines):
        lineno = i + 1  # 1-indexed
        stripped = line.strip()

        # Skip line comments
        if stripped.startswith(";;") or stripped.startswith(";"):
            continue

        # Detect deftype
        m = RE_DEFTYPE.match(stripped)
        if not m:
            continue

        deftype_name = m.group(1)

        # Check if inside a block comment
        if not line_in_block(lineno, block_ranges):
            continue

        # Skip intentionally-dead deftypes
        if should_skip_deftype(deftype_name):
            continue

        # Check if it looks "real"
        is_real, size_assert = scan_deftype_block(lines, i)
        if not is_real:
            continue

        # Find which block comment encloses it
        parent_block_open = None
        parent_block_close = None
        for open_line, close_line in block_ranges:
            if open_line < lineno <= close_line:
                parent_block_open = open_line
                parent_block_close = close_line
                break

        at_risk.append({
            "deftype_name": deftype_name,
            "deftype_line": lineno,
            "size_assert": size_assert,
            "block_open": parent_block_open,
            "block_close": parent_block_close,
            "block_range": f"{parent_block_open}-{parent_block_close}" if parent_block_open else "unknown",
        })

    # Generate markdown
    md_lines = [
        "# Block-comment swallow audit",
        "",
        f"_source: scripts/jakx_watch/block_comment_audit.py · generated: {datetime.now().isoformat()}_",
        "",
        f"Found {len(at_risk)} at-risk deftypes inside `#| ... |#` block comments in all-types.gc.",
        "These look like active deftypes that are being silently disabled.",
        "",
    ]

    if at_risk:
        md_lines += [
            "| deftype | line | opening `#|` line | size-assert | parent block |",
            "|---------|-----:|------------------:|-------------|--------------|",
        ]
        for entry in sorted(at_risk, key=lambda x: x["deftype_line"]):
            md_lines.append(
                f"| `{entry['deftype_name']}` | {entry['deftype_line']} | {entry['block_open']} | "
                f"`{entry['size_assert']}` | {entry['block_open']}-{entry['block_close']} |"
            )
        md_lines.append("")

    # Group by parent block and count
    block_counts = {}
    for entry in at_risk:
        block_key = entry["block_range"]
        block_counts[block_key] = block_counts.get(block_key, 0) + 1

    top_blocks = sorted(block_counts.items(), key=lambda x: -x[1])

    if top_blocks:
        md_lines += [
            "## Top parent blocks (by at-risk deftype count)",
            "",
            "| parent block | at-risk count |",
            "|--------------|---------------:|",
        ]
        for block_range, count in top_blocks[:20]:
            md_lines.append(f"| lines {block_range} | {count} |")
        md_lines.append("")

    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(md_lines) + "\n")

    # Console output
    print(f"Block-comment audit: {len(at_risk)} at-risk deftypes found")
    if at_risk:
        print()
        print("Top offenders (parent blocks with ≥3 at-risk deftypes):")
        for block_range, count in top_blocks:
            if count >= 3:
                print(f"  - lines {block_range}: {count} deftypes")
        print()
        print(f"wrote {AUDIT_MD.relative_to(ROOT)}")

    # Exit code: 1 if any at-risk cases found, 0 if clean
    return 1 if at_risk else 0


if __name__ == "__main__":
    sys.exit(main())
