#!/usr/bin/env python3
"""Near-clean opportunity scanner.

Identifies real-partial files with few errors and classifies what each
needs to become real-clean. Outputs an actionable queue for A1/A2.

Categories:
  * NO_TYPE_ANALYSIS — inspect method on unknown type → needs deftype in all-types.gc
  * FAILED_TYPE_PROP — type-prop load failure → needs type_casts.jsonc hint
  * NOT_CONVERTED — function not converted to expressions → needs mips2c
  * BITFIELD_FAIL — bitfield enum decode failure → needs enum field in all-types.gc
  * FAILED_STORE — failed store operation → type_casts.jsonc or all-types.gc
  * OTHER — unknown pattern

Usage:
  python3 scripts/jakx_watch/near_clean_scan.py [--max-errors N]

Output: .jakx_watch/near_clean_queue.md
"""

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DECOMP_OUT = ROOT / ".jakx_watch/decomp_out/jakx"
OUTPUT = ROOT / ".jakx_watch/near_clean_queue.md"

RE_ERROR = re.compile(r"ERROR: (.+)")
RE_FAILED = re.compile(r";; failed (.+)")
RE_DEFTYPE_CONTEXT = re.compile(r"type analysis.*Cannot decompile|no type analysis")
RE_TYPE_NAME = re.compile(r"\(method \d+ (\S+)\)")


def classify_error(msg: str) -> tuple[str, str]:
    """Return (category, detail) for an error message."""
    if "no type analysis" in msg or "has unknown type" in msg:
        m = re.search(r"\(method \d+ (\S+)\)", msg)
        type_name = m.group(1) if m else "?"
        return "NO_TYPE_ANALYSIS", f"type {type_name!r} not registered in all-types.gc"
    if "not converted to expressions" in msg:
        return "NOT_CONVERTED", "complex MIPS/SIMD → needs mips2c"
    if "Could not figure out load" in msg or "failed type prop" in msg:
        op = re.search(r"\(set! \S+ (.+?)\)", msg)
        op_str = op.group(0)[:60] if op else msg[:60]
        return "FAILED_TYPE_PROP", f"type_casts.jsonc hint needed for: {op_str}"
    if "Failed to decompile bitfield enum" in msg or "bitfield" in msg.lower():
        enum = re.search(r"enum (\S+)\.", msg)
        enum_name = enum.group(1) if enum else "?"
        return "BITFIELD_FAIL", f"add missing bit to enum {enum_name!r} in all-types.gc"
    if "Failed store" in msg:
        return "FAILED_STORE", "type_casts.jsonc or all-types.gc field fix"
    if "FPR -> GPR" in msg:
        return "FPR_GPR", "C++ decompiler fix (overlay field alias)"
    return "OTHER", msg[:80]


def scan_file(path: Path) -> list[tuple[str, str, str]]:
    """Return list of (error_type, category, detail) tuples."""
    text = path.read_text(errors="replace")
    results = []
    
    # Get context for each error: find function name before error
    lines = text.split("\n")
    current_fn = "?"
    for i, line in enumerate(lines):
        if line.startswith(";; definition for ") or line.startswith("(defun ") or line.startswith("(defmethod "):
            current_fn = line.strip()[:80]
        if ";; ERROR:" in line:
            msg = line.split(";; ERROR:", 1)[1].strip()
            cat, detail = classify_error(msg)
            results.append((current_fn, cat, detail))
        elif ";; failed" in line:
            msg = line.split(";; failed", 1)[1].strip()
            cat, detail = classify_error("failed " + msg)
            results.append((current_fn, cat, detail))
    return results


def get_defun_count(path: Path) -> int:
    text = path.read_text(errors="replace")
    return len(re.findall(r"^\(def(?:un|method) ", text, re.MULTILINE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-errors", type=int, default=3,
                        help="Max errors/failed per file to include (default: 3)")
    args = parser.parse_args()

    if not DECOMP_OUT.exists():
        print(f"ERROR: decomp_out not found: {DECOMP_OUT}", file=sys.stderr)
        sys.exit(1)

    files = sorted(DECOMP_OUT.glob("*_disasm.gc"))
    if not files:
        print("ERROR: decomp_out is empty — run decompiler first", file=sys.stderr)
        sys.exit(1)

    # Scan all files
    candidates = []
    for fp in files:
        errors = scan_file(fp)
        if not errors:
            continue  # real-clean (or split-failed with no markers in our scan)
        defun_ct = get_defun_count(fp)
        if defun_ct == 0:
            continue  # split-failed, skip
        if len(errors) <= args.max_errors:
            name = fp.name[: -len("_disasm.gc")]
            candidates.append((name, defun_ct, errors))

    # Sort by error count, then by defun count (larger files first)
    candidates.sort(key=lambda x: (len(x[2]), -x[1]))

    # Build output
    lines = [
        "# Near-clean Opportunity Queue",
        "",
        f"_Files with ≤{args.max_errors} errors that are blocking real-clean status._",
        "_Fix the indicated issue → reseed REF → offline-test goes green._",
        "",
        f"Total candidates: {len(candidates)}",
        "",
    ]

    # Group by error count
    by_count = defaultdict(list)
    for name, defun_ct, errors in candidates:
        by_count[len(errors)].append((name, defun_ct, errors))

    for err_count in sorted(by_count.keys()):
        lines.append(f"## {err_count}-error files ({len(by_count[err_count])} files)")
        lines.append("")
        for name, defun_ct, errors in sorted(by_count[err_count], key=lambda x: -x[1]):
            lines.append(f"### `{name}` ({defun_ct} fns)")
            for fn_ctx, cat, detail in errors:
                lines.append(f"  - **{cat}**: {detail}")
                lines.append(f"    _(in: {fn_ctx[:70]})_")
            lines.append("")

    # Category summary
    all_errors = [(cat, detail) for _, _, errors in candidates for _, cat, detail in errors]
    cat_counts = Counter(cat for cat, _ in all_errors)
    lines.append("## Category summary")
    lines.append("")
    for cat, count in cat_counts.most_common():
        lines.append(f"  - **{cat}**: {count} errors across {len(candidates)} files")
    lines.append("")

    output = "\n".join(lines)
    OUTPUT.write_text(output)
    print(f"Written: {OUTPUT}")
    print(f"Candidates: {len(candidates)} files with ≤{args.max_errors} errors")
    for err_count, flist in sorted(by_count.items()):
        print(f"  {err_count} error(s): {len(flist)} files")

    # Print categories
    print("\nTop error categories:")
    for cat, count in cat_counts.most_common(5):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
