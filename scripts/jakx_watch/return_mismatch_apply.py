#!/usr/bin/env python3
"""Apply return-type mismatch fixes to all-types.gc in batch.

For each (type, method-N, declared→actual) WARN from the decompiler, edits
the :methods block declaration in all-types.gc to match what the body returns.

Usage:
  python3 scripts/jakx_watch/return_mismatch_apply.py --dry-run
  python3 scripts/jakx_watch/return_mismatch_apply.py --top 3
  python3 scripts/jakx_watch/return_mismatch_apply.py --top 5 --commit
  python3 scripts/jakx_watch/return_mismatch_apply.py --patterns none:int,none:symbol

The script:
  1. Scans decompiler output for Return-type-mismatch WARNs.
  2. Finds the matching :methods lines in all-types.gc.
  3. Verifies parent/child type consistency before applying any change.
  4. Applies or prints (--dry-run) the edits.
  5. (Without --dry-run) re-runs the decompiler and measures the delta.
  6. Commits if WARN count drops with no new ERRORs, or reverts.
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import subprocess
import sys
from pathlib import Path

# Reuse scanner infrastructure
sys.path.insert(0, str(Path(__file__).parent))
from return_mismatch_scan import (  # noqa: E402
    build_method_line_index,
    scan_file,
    pick_decomp_dir,
    RE_METHOD_LINE,
    CURRENT_TYPES,
)

ROOT = Path(__file__).resolve().parents[2]
STATUS_MD = ROOT / ".jakx_watch" / "status.md"

# Structural vtable slots — never touch these
SKIP_VTABLE = {0, 1, 9}  # new, delete, asize-of

# Safe patterns ordered by count (declared → actual).
# "Safe" means: body is authoritative, declaration is just a copy-port guess.
SAFE_PATTERNS_ORDERED: list[tuple[str, str]] = [
    ("none", "int"),      # 475 — most common, body returns int, declared void
    ("none", "symbol"),   # 170
    ("int", "none"),      # 162 — body truly void, declaration overestimates
    ("none", "object"),   # 140
    ("none", "process"),  # 62
    ("int", "uint"),      # 43
    ("symbol", "none"),   # 40
    ("object", "none"),   # 36
]


# ---------------------------------------------------------------------------
# Type hierarchy
# ---------------------------------------------------------------------------

_RE_DEFTYPE_PARENT = re.compile(
    r"^\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(([\w<>!?:\-\+\*/=]+)\)"
)


def build_type_hierarchy(
    types_path: Path,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Parse all-types.gc for parent→child relationships.

    Returns (child_to_parent, parent_to_children).
    Skips lines inside block-comment regions ``#| ... |#``.
    """
    child_to_parent: dict[str, str] = {}
    parent_to_children: dict[str, list[str]] = collections.defaultdict(list)
    in_block_comment = False

    for line in types_path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if in_block_comment:
            if "|#" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("#|"):
            if "|#" not in stripped[2:]:
                in_block_comment = True
            continue
        if stripped.startswith(";;") or stripped.startswith(";"):
            continue

        m = _RE_DEFTYPE_PARENT.match(stripped)
        if m:
            child, parent = m.group(1), m.group(2)
            child_to_parent[child] = parent
            parent_to_children[parent].append(child)

    return child_to_parent, dict(parent_to_children)


def get_all_children(
    type_name: str, parent_to_children: dict[str, list[str]]
) -> set[str]:
    """Recursively collect all descendants of type_name."""
    result: set[str] = set()
    queue = list(parent_to_children.get(type_name, []))
    while queue:
        child = queue.pop()
        if child not in result:
            result.add(child)
            queue.extend(parent_to_children.get(child, []))
    return result


# ---------------------------------------------------------------------------
# Method entry scanning
# ---------------------------------------------------------------------------


def collect_method_entries(
    decomp_dir: Path,
) -> dict[str, dict[int, tuple[str, str]]]:
    """Scan all ``*_disasm.gc`` files.

    Returns ``{type_name: {vtable_idx: (declared, actual)}}``.
    When the same method has conflicting signals (multiple WARNs), takes
    the most-common (declared, actual) pair.
    """
    raw: dict[str, dict[int, list[tuple[str, str]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        for caller, parent, declared, actual, mnum in scan_file(fp):
            if parent and mnum is not None:
                raw[parent][mnum].append((declared, actual))

    consolidated: dict[str, dict[int, tuple[str, str]]] = {}
    for tp, methods in raw.items():
        consolidated[tp] = {}
        for mnum, pairs in methods.items():
            (decl, actual), _ = collections.Counter(pairs).most_common(1)[0]
            consolidated[tp][mnum] = (decl, actual)
    return consolidated


# ---------------------------------------------------------------------------
# Line replacement
# ---------------------------------------------------------------------------


def replace_return_type(line: str, old_type: str, new_type: str) -> str | None:
    """Replace the return type in a :methods entry line.

    Returns the modified line, or None if the line didn't match / type mismatch.
    """
    m = RE_METHOD_LINE.match(line)
    if not m:
        return None
    start, end = m.span(2)
    if line[start:end] != old_type:
        return None
    return line[:start] + new_type + line[end:]


# ---------------------------------------------------------------------------
# Fix planning
# ---------------------------------------------------------------------------


def plan_fixes(
    method_entries: dict[str, dict[int, tuple[str, str]]],
    method_line_index: dict[tuple[str, int], tuple[int, str]],
    parent_to_children: dict[str, list[str]],
    active_patterns: set[tuple[str, str]],
) -> list[tuple[int, str, str, str]]:
    """Return list of (line_no, old_line, new_line, fix_desc).

    Applies parent/child consistency checks: a fix is only planned when
    - the method exists in method_line_index (all-types.gc has the line), AND
    - no child declares the method with a DIFFERENT type (which would make
      the parent flip inconsistent — the child fix would need to be done first
      or together), AND
    - the vtable slot is not in SKIP_VTABLE.

    Child methods that share the same (declared, actual) as their parent are
    included in the same batch automatically.
    """
    planned_lines: set[int] = set()
    fixes: list[tuple[int, str, str, str]] = []

    def _add(tp: str, mnum: int, decl: str, actual: str, suffix: str = "") -> bool:
        key = (tp, mnum)
        entry = method_line_index.get(key)
        if not entry:
            return False
        line_no, old_line = entry
        if line_no in planned_lines:
            return False
        new_line = replace_return_type(old_line, decl, actual)
        if new_line is None:
            return False
        tag = f"{tp}::method-{mnum}: {decl} → {actual}{suffix}"
        fixes.append((line_no, old_line, new_line, tag))
        planned_lines.add(line_no)
        return True

    for tp, methods in sorted(method_entries.items()):
        for mnum in sorted(methods):
            decl, actual = methods[mnum]
            if (decl, actual) not in active_patterns:
                continue
            if mnum in SKIP_VTABLE:
                continue
            if (tp, mnum) not in method_line_index:
                continue

            # Parent/child consistency check.
            # For each child that ALSO declares this vtable slot, check that
            # its declared type matches decl (so we can flip it too) or
            # already equals actual (no change needed). If any child disagrees
            # with a different type, skip this type to avoid inconsistency.
            children = get_all_children(tp, parent_to_children)
            consistent = True
            for child in children:
                child_entry = method_line_index.get((child, mnum))
                if not child_entry:
                    continue
                child_line = child_entry[1]
                child_m = RE_METHOD_LINE.match(child_line)
                if not child_m:
                    continue
                child_decl = child_m.group(2)
                if child_decl != decl and child_decl != actual:
                    # Child has a different declared type — parent flip would
                    # create an inconsistency. Skip.
                    consistent = False
                    break
            if not consistent:
                continue

            added = _add(tp, mnum, decl, actual)
            if not added:
                continue

            # Also fix children that share the same (declared, actual).
            for child in sorted(children):
                if (child, mnum) not in method_line_index:
                    continue
                child_entry = method_line_index.get((child, mnum))
                if not child_entry:
                    continue
                child_line = child_entry[1]
                child_m = RE_METHOD_LINE.match(child_line)
                if not child_m:
                    continue
                if child_m.group(2) == decl:
                    _add(child, mnum, decl, actual, " (child)")

    return sorted(fixes, key=lambda x: x[0])


# ---------------------------------------------------------------------------
# Apply + measure
# ---------------------------------------------------------------------------


def apply_fixes(types_path: Path, fixes: list[tuple[int, str, str, str]]) -> None:
    """Apply fixes to all-types.gc. Verifies expected content before writing."""
    lines = types_path.read_text(errors="replace").splitlines(keepends=True)

    for line_no, old_line, new_line, _ in fixes:
        actual_content = lines[line_no - 1].rstrip("\r\n")
        if actual_content != old_line:
            raise ValueError(
                f"Line {line_no} content mismatch.\n"
                f"  expected: {old_line!r}\n"
                f"  got:      {actual_content!r}"
            )

    for line_no, old_line, new_line, _ in fixes:
        original = lines[line_no - 1]
        ending = "\n"
        for end in ("\r\n", "\n", "\r"):
            if original.endswith(end):
                ending = end
                break
        lines[line_no - 1] = new_line + ending

    types_path.write_text("".join(lines))


_RE_WARN_TOTAL = re.compile(r"^inline WARN\s+markers:\s+(\d+)", re.MULTILINE)
_RE_ERROR_TOTAL = re.compile(r"^inline ERROR markers:\s+(\d+)", re.MULTILINE)


def read_status_counts() -> tuple[int, int]:
    """Return (error_markers, warn_markers) from current status.md."""
    if not STATUS_MD.exists():
        return (-1, -1)
    text = STATUS_MD.read_text()
    em = _RE_ERROR_TOTAL.search(text)
    wm = _RE_WARN_TOTAL.search(text)
    errors = int(em.group(1)) if em else -1
    warns = int(wm.group(1)) if wm else -1
    return errors, warns


def run_decompiler() -> int:
    """Run the jakx_watch decompiler pass. Returns exit code."""
    env = {**os.environ, "JAKX_WATCH_FORCE": "1", "JAKX_WATCH_WAIT": "1"}
    result = subprocess.run(
        ["bash", "scripts/jakx_watch/run.sh"],
        cwd=ROOT,
        env=env,
    )
    return result.returncode


def revert_all_types() -> None:
    """Git-restore all-types.gc to HEAD."""
    subprocess.run(
        ["git", "checkout", "HEAD", "--", str(CURRENT_TYPES.relative_to(ROOT))],
        cwd=ROOT,
        check=True,
    )


def git_commit(message: str) -> None:
    rel = str(CURRENT_TYPES.relative_to(ROOT))
    subprocess.run(["git", "add", rel], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned edits without modifying files or running the decompiler.",
    )
    ap.add_argument(
        "--top",
        type=int,
        default=5,
        metavar="N",
        help="Use the top N safe patterns by WARN count (default: 5).",
    )
    ap.add_argument(
        "--patterns",
        metavar="decl:actual,...",
        help=(
            "Comma-separated list of declared:actual pairs to use instead of "
            "--top N (e.g. none:int,none:symbol)."
        ),
    )
    ap.add_argument(
        "--commit",
        action="store_true",
        help="Automatically commit if WARN count drops and no new ERRORs.",
    )
    ap.add_argument(
        "--decomp-out",
        help="Override the decompiler output directory.",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    # Determine active patterns
    if args.patterns:
        try:
            active_patterns: set[tuple[str, str]] = set()
            for tok in args.patterns.split(","):
                decl, actual = tok.strip().split(":")
                active_patterns.add((decl.strip(), actual.strip()))
        except ValueError:
            print(
                f"ERROR: --patterns must be comma-separated decl:actual pairs, "
                f"got: {args.patterns!r}",
                file=sys.stderr,
            )
            return 1
    else:
        active_patterns = set(SAFE_PATTERNS_ORDERED[: args.top])

    print(f"Active patterns ({len(active_patterns)}):")
    for decl, actual in SAFE_PATTERNS_ORDERED:
        if (decl, actual) in active_patterns:
            print(f"  {decl!r:12} → {actual!r}")
    print()

    # Scan decomp output
    decomp_dir = (
        Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    )
    if not decomp_dir.exists():
        print(f"ERROR: decomp dir not found: {decomp_dir}", file=sys.stderr)
        return 1
    print(f"Scanning {decomp_dir} ...")
    method_entries = collect_method_entries(decomp_dir)
    total_mismatches = sum(len(v) for v in method_entries.values())
    print(f"  {total_mismatches} method mismatches across {len(method_entries)} types")

    # Build indexes
    print(f"Building method line index from {CURRENT_TYPES.name} ...")
    method_line_index = build_method_line_index(CURRENT_TYPES)
    print(f"  {len(method_line_index)} method entries indexed")

    print("Building type hierarchy ...")
    _, parent_to_children = build_type_hierarchy(CURRENT_TYPES)

    # Plan fixes
    fixes = plan_fixes(
        method_entries, method_line_index, parent_to_children, active_patterns
    )

    if not fixes:
        print("No fixable methods found (all skipped by pattern/skip-vtable/consistency).")
        return 0

    print(f"\nPlanned {len(fixes)} edits:\n")
    for line_no, old_line, new_line, desc in fixes:
        print(f"  L{line_no:6d}  {desc}")
        print(f"           old: {old_line.strip()}")
        print(f"           new: {new_line.strip()}")

    if args.dry_run:
        print(f"\n[dry-run] {len(fixes)} edits would be applied. Pass without --dry-run to apply.")
        return 0

    # Record baseline
    err_before, warn_before = read_status_counts()
    print(f"\nBaseline:  errors={err_before}  warns={warn_before}")

    # Apply
    print(f"\nApplying {len(fixes)} edits to {CURRENT_TYPES.relative_to(ROOT)} ...")
    try:
        apply_fixes(CURRENT_TYPES, fixes)
    except ValueError as exc:
        print(f"ERROR applying fixes: {exc}", file=sys.stderr)
        return 1
    print("  done.")

    # Re-run decompiler
    print("\nRunning decompiler (JAKX_WATCH_FORCE=1 JAKX_WATCH_WAIT=1) ...")
    rc = run_decompiler()
    if rc not in (0, 1):
        print(f"WARN: decompiler exited {rc} — status.md may be stale", file=sys.stderr)

    # Measure delta
    err_after, warn_after = read_status_counts()
    print(f"\nAfter:     errors={err_after}  warns={warn_after}")

    # Guard: if status.md couldn't be parsed, -1 is returned — treat as failure
    if err_after == -1 or warn_after == -1:
        print(
            "ERROR: status.md did not contain expected markers after decompiler run.\n"
            "       Decompiler may have crashed or status.md was not updated.\n"
            "       Reverting to avoid committing on bad measurement.",
            file=sys.stderr,
        )
        revert_all_types()
        return 1

    delta_err = err_after - err_before
    delta_warn = warn_after - warn_before
    print(f"Delta:     Δerrors={delta_err:+d}  Δwarns={delta_warn:+d}")

    # Decision
    if delta_warn < 0 and delta_err <= 0:
        print(f"\n✓ WARN count dropped by {-delta_warn}. Keeping changes.")
        if args.commit:
            pat_summary = ",".join(
                f"{d}→{a}" for d, a in SAFE_PATTERNS_ORDERED if (d, a) in active_patterns
            )
            msg = (
                f"fix(jakx/all-types): return-mismatch apply batch "
                f"({pat_summary}) (Δwarn {warn_before}→{warn_after}, "
                f"-{-delta_warn})\n\n"
                f"Auto-applied {len(fixes)} :methods return-type corrections.\n"
                f"Patterns: {pat_summary}\n\n"
                f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
            )
            git_commit(msg)
            print("  Committed.")
        else:
            print("  Pass --commit to auto-commit.")
    elif delta_warn == 0 and delta_err <= 0:
        print("\n~ WARN count unchanged. Changes were no-ops for active patterns.")
        print("  Reverting to keep tree clean.")
        revert_all_types()
    else:
        if delta_err > 0:
            print(f"\n✗ ERROR count rose by {delta_err}. Reverting.", file=sys.stderr)
        else:
            print(f"\n✗ WARN count rose by {delta_warn}. Reverting.", file=sys.stderr)
        revert_all_types()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
