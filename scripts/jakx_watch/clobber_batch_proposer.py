#!/usr/bin/env python3
"""Generate a git-apply patch that comments out ALL active define-extern clobbers.

A 'clobber' is a (define-extern FOO <type>) at line >59000 where (deftype FOO ...)
is already active earlier in all-types.gc.  Commenting it out (prepending ';;') is
always safe: the deftype is already active and the late extern is redundant.

This script does NOT modify all-types.gc.  It writes:
  .jakx_watch/clobber_batch_proposal.patch  — ready for `git apply`
  .jakx_watch/clobber_batch_proposal.md     — summary with apply instructions

A1/A2: review the MD, then `git apply .jakx_watch/clobber_batch_proposal.patch`.

Usage:
  python3 scripts/jakx_watch/clobber_batch_proposer.py
  python3 scripts/jakx_watch/clobber_batch_proposer.py --dry-run   # stdout only
  python3 scripts/jakx_watch/clobber_batch_proposer.py --top N     # first N by line
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# Import clobber_scan to reuse the scan() logic
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from clobber_scan import scan  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
OUTPUT_PATCH = ROOT / ".jakx_watch" / "clobber_batch_proposal.patch"
OUTPUT_MD = ROOT / ".jakx_watch" / "clobber_batch_proposal.md"
CONTEXT_LINES = 3


def build_patch(lines_orig: list[str], clobber_indices: set[int]) -> str:
    """Return unified diff that comments out the given 0-based line indices."""
    lines_new = []
    for idx, line in enumerate(lines_orig):
        if idx in clobber_indices:
            # Preserve leading whitespace, prepend ;;
            stripped = line.rstrip("\n")
            lines_new.append(f";;{stripped}\n")
        else:
            lines_new.append(line)

    rel = "decompiler/config/jakx/all-types.gc"
    diff = difflib.unified_diff(
        lines_orig,
        lines_new,
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
        n=CONTEXT_LINES,
    )
    return "".join(diff)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--types", default=str(ALL_TYPES))
    ap.add_argument("--top", type=int, default=None,
                    help="Only include first N clobbers (by extern_line). "
                         "Default: all.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print patch to stdout instead of writing files.")
    ap.add_argument("--no-write", action="store_true",
                    help="Skip writing output files (alias for --dry-run).")
    args = ap.parse_args()

    types_path = Path(args.types)
    text = types_path.read_text(errors="replace")
    lines = text.splitlines(keepends=True)

    _active_dt, active_clobbers, already_fixed = scan(text)

    # Sort by extern_line ascending (earliest = most cascade-unblocking first)
    active_clobbers.sort(key=lambda r: r["extern_line"])

    if args.top is not None:
        active_clobbers = active_clobbers[: args.top]

    if not active_clobbers:
        print("No active clobbers found — nothing to propose.", file=sys.stderr)
        return 0

    clobber_indices = {r["extern_line"] - 1 for r in active_clobbers}  # 0-based
    patch = build_patch(lines, clobber_indices)

    # Validate the patch is non-empty
    if not patch.strip():
        print("ERROR: generated patch is empty", file=sys.stderr)
        return 2

    removed = sum(1 for l in patch.splitlines() if l.startswith("-") and not l.startswith("---"))
    print(f"active clobbers:   {len(active_clobbers)}")
    print(f"already fixed:     {len(already_fixed)}")
    print(f"patch hunks:       {patch.count('@@ ')}")
    print(f"lines to comment:  {removed}")

    if args.dry_run or args.no_write:
        print(patch)
        return 0

    OUTPUT_PATCH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATCH.write_text(patch)
    print(f"\nwrote {OUTPUT_PATCH.relative_to(ROOT)}", file=sys.stderr)

    # Build summary MD
    lines_md = [
        "# jakx clobber batch proposal",
        "",
        f"_source: `scripts/jakx_watch/clobber_batch_proposer.py`_",
        "",
        "## What this does",
        "",
        "Comments out `(define-extern FOO <type>)` lines at line >59000 where "
        "`(deftype FOO ...)` is already active earlier in `all-types.gc`.  "
        "These late externs overwrite the type entry with `object`, breaking "
        "typecheck for all REF files that depend on these types.",
        "",
        "**This patch is safe to apply in bulk** — every entry here has a confirmed "
        "active deftype earlier in the file.  The only effect is to stop the clobber.",
        "",
        "## Apply instructions",
        "",
        "> **Note:** `all-types.gc` is concurrently modified by A1/A2. "
        "Regenerate the patch immediately before applying to avoid stale-context errors:",
        "",
        "```bash",
        "# From the repo root:",
        "python3 scripts/jakx_watch/clobber_batch_proposer.py   # regenerate fresh",
        "git apply .jakx_watch/clobber_batch_proposal.patch",
        "# Then verify and commit:",
        "bash scripts/jakx_watch/run.sh   # or JAKX_WATCH_FORCE=1 bash ...",
        "git add decompiler/config/jakx/all-types.gc",
        'git commit -m "config(jakx): comment out all active define-extern clobbers"',
        "```",
        "",
        "## Summary",
        "",
        f"| stat | value |",
        f"|------|------:|",
        f"| active clobbers in patch | {len(active_clobbers)} |",
        f"| already fixed (not in patch) | {len(already_fixed)} |",
        f"| patch file | `.jakx_watch/clobber_batch_proposal.patch` |",
        "",
        "## Clobbers included in patch",
        "",
        "All {n} clobbers sorted by extern_line (ascending = earliest first = "
        "most cascade-unblocking).".format(n=len(active_clobbers)),
        "",
        "| extern_line | type name | extern_type | deftype_line | parent |",
        "|------------:|-----------|-------------|-------------:|--------|",
    ]
    for r in active_clobbers:
        lines_md.append(
            f"| L{r['extern_line']} | `{r['name']}` | `{r['extern_type']}` "
            f"| L{r['deftype_line']} | `{r['parent']}` |"
        )
    lines_md += [
        "",
        "---",
        "",
        "## Why all are safe",
        "",
        "- Every type listed has an **active** `(deftype ...)` earlier in the file "
        "(not block-commented, not line-commented).",
        "- The late `(define-extern)` is the standard OpenGOAL forward-declaration "
        "pattern — but these were never cleaned up after the deftype was added.",
        "- Commenting them out restores the type to its full deftype representation.",
        "- No functional code references these externs at runtime; they only affect "
        "the GOAL compiler's type table during compilation.",
        "",
        "## Risk",
        "",
        "**Low.** If any type's deftype itself has an assertion error (bad "
        "offset-assert, method-count-assert), commenting the extern exposes that "
        "error instead of hiding it behind `object`.  This is the desired behaviour "
        "— it surfaces the real bug rather than silencing it.",
        "",
        "Re-run `clobber_scan.py` after applying to verify count drops to 0 "
        "(or near-zero if new deftypes were added since this scan).",
    ]
    OUTPUT_MD.write_text("\n".join(lines_md) + "\n")
    print(f"wrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
