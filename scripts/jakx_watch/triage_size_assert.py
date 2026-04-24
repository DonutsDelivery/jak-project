#!/usr/bin/env python3
"""Triage size_assert mismatches into fixable, review-needed, and false-positive categories.

Reads the audit output and classifies each mismatch by examining the deftype in all-types.gc:
- FALSE_POSITIVE: has :dynamic, bitfield parent, overlay-at, or other reasons
- REAL_DELTA_SMALL: abs(diff) ≤ 8 bytes — likely safe to fix
- REAL_DELTA_LARGE: abs(diff) > 8 bytes — needs review

Emits `.jakx_watch/size_assert_fixable.md` sorted by actionability.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TYPES_PATH = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
AUDIT_MD = ROOT / ".jakx_watch" / "size_assert_audit.md"
FIXABLE_MD = ROOT / ".jakx_watch" / "size_assert_fixable.md"

RE_DEFTYPE_START = re.compile(r"^\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(([\w<>!?:\-\+\*/=]*)")
RE_FIELD = re.compile(r"^\s*\([^\)]*\)")
RE_DYNAMIC = re.compile(r":dynamic")
RE_OVERLAY_AT = re.compile(r":overlay-at")
RE_BITFIELD = re.compile(r":bitfield\s+#t")


def extract_mismatch_table(audit_md_path: Path) -> list[dict]:
    """Extract mismatch rows from size_assert_audit.md."""
    if not audit_md_path.exists():
        return []

    text = audit_md_path.read_text(errors="replace")

    # Find the "Real mismatches" section
    start = text.find("## Real mismatches")
    if start == -1:
        return []

    end = text.find("##", start + 1)
    if end == -1:
        end = len(text)

    section = text[start:end]

    # Parse table rows
    mismatches = []
    in_table = False
    for line in section.splitlines():
        if "|" not in line:
            continue
        if "declared" in line and "computed" in line:
            in_table = True
            continue
        if not in_table or line.strip().startswith("|---"):
            continue

        # Parse row: | `type` | `#0x...` | `#0x...` | diff | line |
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue

        type_name = parts[1].strip("`")
        try:
            declared_hex = parts[2].strip("`").replace("#", "")
            computed_hex = parts[3].strip("`").replace("#", "")
            diff = int(parts[4])
            lineno = int(parts[5])

            mismatches.append({
                "type": type_name,
                "declared": int(declared_hex, 16),
                "computed": int(computed_hex, 16),
                "diff": diff,
                "lineno": lineno,
            })
        except (ValueError, IndexError):
            continue

    return mismatches


def find_deftype_lines(types_path: Path, type_name: str, start_line: int) -> list[str]:
    """Find deftype in all-types.gc around the given line and return all lines."""
    if not types_path.exists():
        return []

    lines = types_path.read_text(errors="replace").splitlines()

    # Search near the given line number (0-indexed)
    search_start = max(0, start_line - 5)
    search_end = min(len(lines), start_line + 50)

    deftype_lines = []
    found = False
    paren_depth = 0

    for i in range(search_start, search_end):
        line = lines[i]

        if not found:
            m = RE_DEFTYPE_START.match(line.strip())
            if m and m.group(1) == type_name:
                found = True
                paren_depth = 1

        if found:
            deftype_lines.append(line)
            paren_depth += line.count("(") - line.count(")")
            if paren_depth <= 0:
                break

    return deftype_lines


def classify_mismatch(type_name: str, diff: int, types_path: Path, lineno: int) -> str:
    """Classify a mismatch as FALSE_POSITIVE, REAL_DELTA_SMALL, or REAL_DELTA_LARGE."""
    deftype_lines = find_deftype_lines(types_path, type_name, lineno - 1)

    if not deftype_lines:
        return "UNRESOLVABLE"

    # Join all lines and check for false-positive patterns
    full_text = "\n".join(deftype_lines)

    # Check for :dynamic, :overlay-at, etc.
    if RE_DYNAMIC.search(full_text):
        return "FALSE_POSITIVE"
    if RE_OVERLAY_AT.search(full_text):
        return "FALSE_POSITIVE"
    if RE_BITFIELD.search(full_text):
        return "FALSE_POSITIVE"

    # Classify by diff magnitude
    abs_diff = abs(diff)
    if abs_diff <= 8:
        return "REAL_DELTA_SMALL"
    else:
        return "REAL_DELTA_LARGE"


def triage_mismatches(mismatches: list[dict], types_path: Path) -> dict:
    """Classify all mismatches and return organized results."""
    classified = {
        "REAL_DELTA_SMALL": [],
        "REAL_DELTA_LARGE": [],
        "FALSE_POSITIVE": [],
        "UNRESOLVABLE": [],
    }

    for m in mismatches:
        classification = classify_mismatch(m["type"], m["diff"], types_path, m["lineno"])
        m["classification"] = classification
        classified[classification].append(m)

    return classified


def write_fixable_md(classified: dict) -> None:
    """Write `.jakx_watch/size_assert_fixable.md` with triaged results."""
    lines = [
        "# size-assert fixable queue",
        "",
        f"_source: scripts/jakx_watch/triage_size_assert.py_",
        "",
    ]

    # Summary
    total = sum(len(v) for v in classified.values())
    small = len(classified["REAL_DELTA_SMALL"])
    large = len(classified["REAL_DELTA_LARGE"])
    fp = len(classified["FALSE_POSITIVE"])
    un = len(classified["UNRESOLVABLE"])

    lines.extend([
        f"## Summary",
        "",
        f"**{small} fixable** (±1-8 bytes) | **{large} review-needed** (>8 bytes) | "
        f"**{fp} false-positive** | **{un} unresolvable** | _Total: {total}_",
        "",
    ])

    # Actionable mismatches (REAL_DELTA_SMALL)
    if classified["REAL_DELTA_SMALL"]:
        lines.extend([
            "## Actionable fixes (±1-8 bytes — safe to fix)",
            "",
            "| type | declared | computed | diff | line |",
            "|------|----------|----------|-----:|-----:|",
        ])
        for m in sorted(classified["REAL_DELTA_SMALL"], key=lambda x: x["lineno"]):
            lines.append(
                f"| `{m['type']}` | `#{hex(m['declared'])[2:]}` | `#{hex(m['computed'])[2:]}` | "
                f"{m['diff']:+d} | {m['lineno']} |"
            )
        lines.append("")

        lines.extend([
            "**Fix pattern:** For each type, change `:size-assert #x<declared>` → `:size-assert #x<computed>` in all-types.gc",
            "",
        ])

    # Large mismatches (REAL_DELTA_LARGE)
    if classified["REAL_DELTA_LARGE"]:
        lines.extend([
            "## Review needed (>8 bytes — may need deeper investigation)",
            "",
            "| type | declared | computed | diff | line |",
            "|------|----------|----------|-----:|-----:|",
        ])
        for m in sorted(classified["REAL_DELTA_LARGE"], key=lambda x: abs(x["diff"]), reverse=True):
            lines.append(
                f"| `{m['type']}` | `#{hex(m['declared'])[2:]}` | `#{hex(m['computed'])[2:]}` | "
                f"{m['diff']:+d} | {m['lineno']} |"
            )
        lines.append("")

    # False positives
    if classified["FALSE_POSITIVE"]:
        lines.extend([
            "## False positives (audit filters should skip these — check manually)",
            "",
            "| type | declared | computed | diff | line |",
            "|------|----------|----------|-----:|-----:|",
        ])
        for m in sorted(classified["FALSE_POSITIVE"], key=lambda x: x["lineno"]):
            lines.append(
                f"| `{m['type']}` | `#{hex(m['declared'])[2:]}` | `#{hex(m['computed'])[2:]}` | "
                f"{m['diff']:+d} | {m['lineno']} |"
            )
        lines.append("")

    FIXABLE_MD.parent.mkdir(parents=True, exist_ok=True)
    FIXABLE_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {FIXABLE_MD.relative_to(ROOT)}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Triage size_assert mismatches into fixable and review queues."
    )
    ap.add_argument("--audit-md", type=Path, default=AUDIT_MD)
    ap.add_argument("--types", type=Path, default=TYPES_PATH)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    mismatches = extract_mismatch_table(args.audit_md)
    if not mismatches:
        print("error: no mismatches found in audit markdown", file=sys.stderr)
        return 1

    print(f"Triaging {len(mismatches)} mismatches...", file=sys.stderr)

    classified = triage_mismatches(mismatches, args.types)

    print(
        f"  {len(classified['REAL_DELTA_SMALL'])} actionable  "
        f"{len(classified['REAL_DELTA_LARGE'])} review-needed  "
        f"{len(classified['FALSE_POSITIVE'])} false-positive",
        file=sys.stderr,
    )

    if not args.no_write:
        write_fixable_md(classified)

    return 0


if __name__ == "__main__":
    sys.exit(main())
