#!/usr/bin/env python3
"""Audit :size-assert declarations in GOAL deftypes against computed field sizes.

Deftypes declare `:size-assert #xNNN` to catch layout bugs at load time. If the
declared size doesn't match the actual computed size from `:field` specs, the
runtime throws rc=134 and blocks downstream decomp. This auditor flags mismatches
before they crash the scanner.

Parses `decompiler/config/jakx/all-types.gc`, computes field sizes from parent +
fields, and compares against declared `:size-assert`. Emits `.jakx_watch/size_assert_audit.md`
with mismatches, unresolvables, and pass count.

Exit 1 if any mismatches found; 0 otherwise.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
TYPES_PATH = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
AUDIT_MD = ROOT / ".jakx_watch" / "size_assert_audit.md"

# Primitive type sizes (hardcoded)
PRIMITIVE_SIZES = {
    "int8": 1,
    "uint8": 1,
    "int16": 2,
    "uint16": 2,
    "int32": 4,
    "uint32": 4,
    "float": 4,
    "pointer": 4,
    "basic": 4,
    "int64": 8,
    "uint64": 8,
    "uint128": 16,
    "int128": 16,
    "structure": 0,  # Base class, no inherited size
    "symbol": 4,
    "type": 4,
    "object": 0,
}

# Regex patterns
RE_BLOCK_COMMENT_START = re.compile(r"#\|")
RE_BLOCK_COMMENT_END = re.compile(r"\|\#")
RE_DEFTYPE = re.compile(r"^\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(([\w<>!?:\-\+\*/=]*)")
RE_FIELD = re.compile(
    r"^\s*\(([\w<>!?:\-\+\*/=]+)\s+([\w<>!?:\-\+\*/=\[\]]+)(?:\s+(\d+))?(.*)?\)"
)
RE_SIZE_ASSERT = re.compile(r":size-assert\s+(#x[\da-fA-F]+)")
RE_OFFSET = re.compile(r":offset(?:-assert)?\s+(\d+)")
RE_INLINE = re.compile(r":inline")
RE_DYNAMIC = re.compile(r":dynamic")


def parse_all_types(types_path: Path) -> dict:
    """Parse all-types.gc and return {type_name: {deftype_data}}.

    Skips block-commented deftypes. For each active deftype, extracts:
      - parent: parent type name
      - size_assert: declared :size-assert value (int, hex stripped)
      - fields: list of {name, type, inline, array_count, offset, lineno}
      - lineno: line where deftype is declared
    """
    if not types_path.exists():
        return {}

    lines = types_path.read_text(errors="replace").splitlines()
    deftypes: dict = {}
    in_block_comment = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Track block comments
        if RE_BLOCK_COMMENT_START.search(line):
            in_block_comment = True
        if RE_BLOCK_COMMENT_END.search(line):
            in_block_comment = False
            i += 1
            continue

        if in_block_comment:
            i += 1
            continue

        # Skip single-line comments
        if stripped.startswith(";;") or stripped.startswith(";"):
            i += 1
            continue

        # Detect deftype start
        m = RE_DEFTYPE.match(stripped)
        if not m:
            i += 1
            continue

        type_name = m.group(1)
        parent_name = m.group(2) if m.group(2) else "object"
        start_lineno = i + 1  # Convert to 1-indexed line number

        # Parse the deftype body until closing paren
        size_assert = None
        fields = []

        # Count parens on the deftype line itself
        comment_idx = line.find(";;")
        if comment_idx == -1:
            deftype_line_clean = line
        else:
            deftype_line_clean = line[:comment_idx]

        paren_depth = deftype_line_clean.count("(") - deftype_line_clean.count(")")

        # Scan forward to collect all lines until closing paren
        j = i + 1
        while j < len(lines) and paren_depth > 0:
            body_line = lines[j]

            # Count parens (excluding comments)
            comment_idx = body_line.find(";;")
            if comment_idx == -1:
                body_stripped = body_line
            else:
                body_stripped = body_line[:comment_idx]

            paren_depth += body_stripped.count("(") - body_stripped.count(")")

            # Parse this line
            body_line_stripped = body_line.strip()

            # Look for :size-assert
            m_assert = RE_SIZE_ASSERT.search(body_line)
            if m_assert:
                hex_str = m_assert.group(1)  # e.g. "#x10"
                try:
                    # Strip #x prefix and convert from hex
                    size_assert = int(hex_str[2:], 16) if hex_str.startswith("#x") else int(hex_str, 16)
                except ValueError:
                    pass

            # Look for field definitions (lines starting with '(')
            if body_line_stripped.startswith("(") and not body_line_stripped.startswith("(:"):
                fm = RE_FIELD.match(body_line_stripped)
                if fm:
                    field_name = fm.group(1)
                    field_type = fm.group(2)
                    array_count = int(fm.group(3)) if fm.group(3) else None
                    tail = fm.group(4) or ""

                    # Check for :inline, :offset, :dynamic
                    is_inline = RE_INLINE.search(tail) is not None
                    is_dynamic = RE_DYNAMIC.search(tail) is not None

                    offset_match = RE_OFFSET.search(tail)
                    offset = int(offset_match.group(1)) if offset_match else None

                    fields.append({
                        "name": field_name,
                        "type": field_type,
                        "inline": is_inline,
                        "array_count": array_count,
                        "offset": offset,
                        "dynamic": is_dynamic,
                        "lineno": j + 1,
                    })

            j += 1

        deftypes[type_name] = {
            "parent": parent_name,
            "size_assert": size_assert,
            "fields": fields,
            "lineno": start_lineno,
        }

        i = j  # Skip to end of deftype

    return deftypes


def get_type_size(type_name: str, all_types: dict, seen: set) -> Optional[int]:
    """Recursively compute the size of a type from parent + fields.

    Returns None if type is unresolvable (forward-ref, commented, or has :dynamic fields).
    """
    # Check for cycles
    if type_name in seen:
        return None

    # Check primitives
    if type_name in PRIMITIVE_SIZES:
        return PRIMITIVE_SIZES[type_name]

    # Check if type is defined
    if type_name not in all_types:
        return None

    type_def = all_types[type_name]
    seen_copy = seen | {type_name}

    # Start with parent size
    parent_name = type_def["parent"]
    if parent_name and parent_name != "object":
        parent_size = get_type_size(parent_name, all_types, seen_copy)
        if parent_size is None:
            return None
    else:
        parent_size = 0

    # Compute size from fields
    size = parent_size

    for field in type_def["fields"]:
        if field["dynamic"]:
            return None  # Can't compute size with :dynamic fields

        # Get field type size
        field_type = field["type"]

        # Handle array types like "int32" vs "int32 4"
        base_type = field_type
        array_mult = field["array_count"] if field["array_count"] else 1

        field_type_size = get_type_size(base_type, all_types, seen_copy)
        if field_type_size is None:
            return None

        # If :inline, embed the struct; otherwise pointer
        if field["inline"]:
            field_size = field_type_size * array_mult
        else:
            field_size = 4  # Pointer size

        # Update size based on explicit offset or computed
        if field["offset"] is not None:
            size = max(size, field["offset"] + field_size)
        else:
            # Align size to field alignment (assume 4-byte for most types)
            alignment = min(field_type_size, 4)
            size = (size + alignment - 1) // alignment * alignment
            size += field_size

    return size


def has_dynamic_fields(type_def: dict) -> bool:
    """Check if type has any :dynamic fields or :inline-array with :dynamic."""
    for field in type_def["fields"]:
        if field["dynamic"]:
            return True
        # Check for :inline-array with :dynamic (array_count > 1 and dynamic)
        if field["array_count"] and field["array_count"] > 1 and field["dynamic"]:
            return True
    return False


def is_bitfield_parent(parent_name: str, all_types: dict) -> bool:
    """Check if parent type is a bitfield (uint32/64/128)."""
    if parent_name in ("uint32", "uint64", "uint128"):
        return True
    # Could also check if parent has `:bitfield #t` but primitives above are the main case
    return False


def audit_types(all_types: dict) -> tuple[list, list, list, int]:
    """Audit all types and return (mismatches, false_positives, unresolvables, passes).

    Returns:
        (mismatches, false_positives, unresolvables, pass_count)

    Each mismatch: {type, declared, computed, diff, lineno}
    Each false_positive: {type, reason, lineno}
    Each unresolvable: {type, reason, lineno}
    """
    mismatches = []
    false_positives = []
    unresolvables = []
    passes = 0

    for type_name, type_def in sorted(all_types.items()):
        if type_def["size_assert"] is None:
            continue  # No size assertion to check

        # Skip types with :dynamic fields (can't compute size)
        if has_dynamic_fields(type_def):
            false_positives.append({
                "type": type_name,
                "reason": ":dynamic field",
                "lineno": type_def["lineno"],
            })
            continue

        # Skip types with bitfield parents
        if is_bitfield_parent(type_def["parent"], all_types):
            false_positives.append({
                "type": type_name,
                "reason": "bitfield parent",
                "lineno": type_def["lineno"],
            })
            continue

        computed_size = get_type_size(type_name, all_types, set())

        if computed_size is None:
            unresolvables.append({
                "type": type_name,
                "reason": "forward-ref or unresolvable parent",
                "lineno": type_def["lineno"],
            })
            continue

        declared_size = type_def["size_assert"]
        if declared_size != computed_size:
            mismatches.append({
                "type": type_name,
                "declared": declared_size,
                "computed": computed_size,
                "diff": computed_size - declared_size,
                "lineno": type_def["lineno"],
            })
        else:
            passes += 1

    return mismatches, false_positives, unresolvables, passes


def write_audit_md(mismatches: list, false_positives: list, unresolvables: list, passes: int, total: int) -> None:
    """Write .jakx_watch/size_assert_audit.md report."""
    lines = [
        "# size-assert audit",
        "",
        f"_source: scripts/jakx_watch/size_assert_audit.py  ·  generated: {Path().cwd().name}_",
        "",
        f"Found **{len(mismatches)} real mismatches** · {len(false_positives)} false positives · "
        f"{len(unresolvables)} unresolvable · {passes} clean (out of {total} checked)",
        "",
    ]

    if mismatches:
        lines.extend([
            "## Real mismatches (fix these — they may crash the scanner when activated)",
            "",
            "| type | declared | computed | diff | line |",
            "|------|----------|----------|-----:|-----:|",
        ])
        for m in sorted(mismatches, key=lambda x: x["lineno"]):
            lines.append(
                f"| `{m['type']}` | `#{hex(m['declared'])}` | `#{hex(m['computed'])}` | "
                f"{m['diff']:+d} | {m['lineno']} |"
            )
        lines.append("")
    else:
        lines.extend([
            f"**All {passes} types with :size-assert pass** — no real mismatches found.",
            "",
        ])

    if false_positives:
        lines.extend([
            "## False positives (skipped — can't compute size)",
            "",
            "| type | reason | line |",
            "|------|--------|-----:|",
        ])
        for fp in sorted(false_positives, key=lambda x: x["lineno"]):
            lines.append(f"| `{fp['type']}` | {fp['reason']} | {fp['lineno']} |")
        lines.append("")

    if unresolvables:
        lines.extend([
            "## Unresolvable (forward-refs / commented-out parents)",
            "",
            "| type | reason | line |",
            "|------|--------|-----:|",
        ])
        for u in sorted(unresolvables, key=lambda x: x["lineno"]):
            lines.append(f"| `{u['type']}` | {u['reason']} | {u['lineno']} |")
        lines.append("")

    lines.extend([
        "## How to use",
        "",
        "1. For each **real mismatch**, check the actual field layout in `all-types.gc` at the line shown.",
        "2. Recompute the size manually (sum of parent size + all field offsets + field sizes).",
        "3. Update `:size-assert` to match the computed value.",
        "4. Re-run `bash scripts/jakx_watch/run.sh` to validate the fix.",
        "",
        "**Why:** rc=134 at runtime means declared size != actual size, blocking the whole level.",
        "Catching these early prevents scanner crashes.",
    ])

    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {AUDIT_MD.relative_to(ROOT)}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit GOAL deftype :size-assert declarations against computed field sizes."
    )
    ap.add_argument("--no-write", action="store_true", help="Skip writing output markdown")
    ap.add_argument("--types", type=Path, default=TYPES_PATH, help="Path to all-types.gc")
    args = ap.parse_args()

    if not args.types.exists():
        print(f"error: {args.types} not found", file=sys.stderr)
        return 1

    # Parse and audit
    all_types = parse_all_types(args.types)
    mismatches, false_positives, unresolvables, passes = audit_types(all_types)
    total = len([t for t in all_types.values() if t["size_assert"] is not None])

    print(f"size-assert audit: {len(mismatches)} real mismatches, {len(false_positives)} false positives, "
          f"{len(unresolvables)} unresolvable, {passes} clean (out of {total})")

    if mismatches:
        print("\nTop 10 real mismatches:")
        for m in sorted(mismatches, key=lambda x: abs(x["diff"]), reverse=True)[:10]:
            print(f"  {m['type']:40s} declared #{hex(m['declared']):>6s}  computed #{hex(m['computed']):>6s}  "
                  f"diff {m['diff']:+d}  (L{m['lineno']})")

    if not args.no_write:
        write_audit_md(mismatches, false_positives, unresolvables, passes, total)

    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
