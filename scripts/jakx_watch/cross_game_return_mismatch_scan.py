#!/usr/bin/env python3
"""cross_game_return_mismatch_scan.py — scan return-type mismatch WARNs in jak1/2/3.

Reuses return_mismatch_scan's helpers but accepts --game so it reads the
correct decompiler_out/ + all-types.gc paths. Produces a dry-run report
suitable for review before any apply (especially relevant when changes
would be submitted upstream to OpenGOAL).

Usage:
  python3 scripts/jakx_watch/cross_game_return_mismatch_scan.py --game jak3
  python3 scripts/jakx_watch/cross_game_return_mismatch_scan.py --game jak2 --top 20
  python3 scripts/jakx_watch/cross_game_return_mismatch_scan.py --game jak1 --pattern none:int

Output:
  Console summary +
  .jakx_watch/research/cross_game_return_mismatch_<game>_<ts>.md
"""
from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "jakx_watch"
sys.path.insert(0, str(SCRIPTS))

from return_mismatch_scan import (  # noqa: E402
    build_method_line_index,
    scan_file,
)

GAMES = ("jak1", "jak2", "jak3", "jakx")


def paths_for(game: str) -> tuple[Path, Path]:
    """Return (decomp_dir, all_types_path) for given game."""
    decomp_dir = ROOT / "decompiler_out" / game
    all_types = ROOT / "decompiler" / "config" / game / "all-types.gc"
    return decomp_dir, all_types


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True, choices=GAMES)
    ap.add_argument("--top", type=int, default=15,
                    help="Top N patterns to show (default: 15)")
    ap.add_argument("--pattern",
                    help="Filter to single pattern, e.g. 'none:int'")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    decomp_dir, all_types = paths_for(args.game)
    if not decomp_dir.exists():
        print(f"ERROR: {decomp_dir} missing — has {args.game} been decompiled?",
              file=sys.stderr)
        return 1
    if not all_types.exists():
        print(f"ERROR: {all_types} missing", file=sys.stderr)
        return 1

    pattern_filter = None
    if args.pattern:
        try:
            decl, actual = args.pattern.split(":")
            pattern_filter = (decl, actual)
        except ValueError:
            print(f"ERROR: --pattern must be 'declared:actual'", file=sys.stderr)
            return 1

    print(f"[{args.game}] scanning {decomp_dir} ...")
    method_index = build_method_line_index(all_types)
    print(f"[{args.game}] indexed {len(method_index)} method declarations from {all_types.name}")

    pattern_counts: collections.Counter = collections.Counter()
    parent_counts: collections.Counter = collections.Counter()
    specific_counts: collections.Counter = collections.Counter()
    method_entries: dict[str, dict[int, list[tuple[str, str]]]] = (
        collections.defaultdict(lambda: collections.defaultdict(list))
    )
    file_counts: collections.Counter = collections.Counter()
    total = 0

    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        rows = scan_file(fp)
        if not rows:
            continue
        fname = fp.name[: -len("_disasm.gc")]
        for caller, parent, declared, actual, mnum in rows:
            if pattern_filter and (declared, actual) != pattern_filter:
                continue
            total += 1
            file_counts[fname] += 1
            pattern_counts[(declared, actual)] += 1
            if parent:
                parent_counts[parent] += 1
                specific_counts[(parent, declared, actual)] += 1
                if mnum is not None:
                    method_entries[parent][mnum].append((declared, actual))

    print(f"\n[{args.game}] return-mismatch WARNs: {total}")
    print(f"\ntop {args.top} (declared, actual) patterns:")
    for (decl, actual), c in pattern_counts.most_common(args.top):
        print(f"  {c:>5}  declared={decl:<14} actual={actual}")

    print(f"\ntop 15 parent types:")
    for parent, c in parent_counts.most_common(15):
        print(f"  {c:>4}  {parent}")

    if args.no_write:
        return 0

    research_dir = ROOT / ".jakx_watch" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    out_path = research_dir / f"cross_game_return_mismatch_{args.game}_{ts}.md"

    body = [f"# {args.game} return-type mismatch scan ({ts})", "",
            f"**Total WARNs:** {total}",
            f"**Files affected:** {len(file_counts)}",
            f"**Method index size:** {len(method_index)}",
            "",
            "## Top patterns",
            "",
            "| count | declared | actual |",
            "|---:|---|---|"]
    for (decl, actual), c in pattern_counts.most_common(args.top):
        body.append(f"| {c} | `{decl}` | `{actual}` |")

    body.extend(["", "## Top parent types (likely batch-fix targets)", "",
                 "| count | parent type | resolvable methods |",
                 "|---:|---|---:|"])
    for parent, c in parent_counts.most_common(20):
        # How many method numbers we can locate in all-types.gc?
        methods_in_index = sum(
            1 for mnum in method_entries.get(parent, {})
            if (parent, mnum) in method_index
        )
        body.append(f"| {c} | `{parent}` | {methods_in_index} |")

    body.extend(["", "## Per-method actionable list (locatable in all-types.gc)", "",
                 "| type | method | declared | actual | line |",
                 "|---|---:|---|---|---:|"])
    flat_actionable = []
    for parent, mns in method_entries.items():
        for mnum, mismatches in mns.items():
            key = (parent, mnum)
            if key not in method_index:
                continue
            line_no, _ = method_index[key]
            # Get most-common (declared, actual) for this method
            decl, actual = collections.Counter(mismatches).most_common(1)[0][0]
            flat_actionable.append((parent, mnum, decl, actual, line_no, len(mismatches)))
    # Sort by mismatch count desc
    flat_actionable.sort(key=lambda r: -r[5])
    for parent, mnum, decl, actual, line_no, count in flat_actionable[:50]:
        body.append(f"| `{parent}` | {mnum} | `{decl}` | `{actual}` | {line_no} |")

    body.extend(["", f"_Showing top 50 of {len(flat_actionable)} actionable methods._",
                 "",
                 "## Notes",
                 "",
                 "- Vtable slots 0/1/9 (new/delete/asize-of) are structural and excluded by apply tools",
                 "- `declared` = current `:methods` block return type (probably wrong)",
                 "- `actual` = what the decompiled body actually returns (usually right)",
                 "- Apply via a tool that respects parent/child consistency (see return_mismatch_apply.py for jakx pattern)",
                 ""])

    out_path.write_text("\n".join(body))
    print(f"\nReport: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
