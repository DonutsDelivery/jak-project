#!/usr/bin/env python3
"""cross_game_return_mismatch_apply.py — apply return-mismatch fixes to jak1/2/3.

Reuses return_mismatch_apply's plan_fixes + apply_fixes logic but routes
paths via --game flag. For non-jakx games there's no apply_guard
infrastructure (no .jakx_watch/ status.md / decomp pipeline), so this tool:

  - Validates per-pattern using the same SAFE_PATTERNS_ORDERED
  - Performs parent/child consistency checks via MethodBodyReader
  - Edits all-types.gc directly
  - Optionally commits the change locally
  - Does NOT auto-revert (no game-watch metric to gate on)

Recommended workflow:
  1. Dry-run: see exactly which lines would change
     python3 scripts/jakx_watch/cross_game_return_mismatch_apply.py --game jak3 --dry-run
  2. Per-pattern apply with commit (one commit per pattern, easier upstream PR review)
     python3 scripts/jakx_watch/cross_game_return_mismatch_apply.py --game jak3 --pattern none:int --commit
  3. Iterate through SAFE_PATTERNS_ORDERED for each game

The local commits become the basis for upstream OpenGOAL PRs later.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "jakx_watch"
sys.path.insert(0, str(SCRIPTS))

from return_mismatch_scan import build_method_line_index  # noqa: E402
from return_mismatch_apply import (  # noqa: E402
    SAFE_PATTERNS_ORDERED,
    SKIP_VTABLE,
    collect_method_entries,
    plan_fixes,
    apply_fixes,
    build_type_hierarchy,
)
from method_body_reader import MethodBodyReader  # noqa: E402
from apply_guard import run_with_guard, bisect_apply  # noqa: E402
from fix_tag_helpers import (  # noqa: E402
    parse_fix_tag,
    extract_edited_types_from_fixes,
    filter_blacklisted,
)

GAMES = ("jak1", "jak2", "jak3")


def paths_for(game: str) -> tuple[Path, Path]:
    """Return (decomp_dir, all_types_path)."""
    return (
        ROOT / "decompiler_out" / game,
        ROOT / "decompiler" / "config" / game / "all-types.gc",
    )


def parse_pattern(s: str) -> tuple[str, str]:
    if ":" not in s:
        raise argparse.ArgumentTypeError(f"pattern must be 'declared:actual', got {s!r}")
    decl, actual = s.split(":", 1)
    return (decl, actual)


def commit_change(game: str, all_types: Path, summary: str) -> str:
    rel = str(all_types.relative_to(ROOT))
    subprocess.run(["git", "add", rel], cwd=ROOT, check=True)
    msg = (
        f"fix({game}/all-types): {summary}\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>\n"
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=ROOT, check=True)
    sha = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT
    ).decode().strip()
    return sha


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True, choices=GAMES)
    ap.add_argument("--pattern", type=parse_pattern, action="append",
                    help="Single pattern to apply, e.g. 'none:int' "
                         "(repeat for multiple). Default: SAFE_PATTERNS_ORDERED")
    ap.add_argument("--top", type=int, default=0,
                    help="Use top-N safe patterns (0 = all SAFE)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--commit", action="store_true",
                    help="Stage + commit after apply")
    ap.add_argument("--no-body-validate", action="store_true",
                    help="Skip MethodBodyReader child-body validation")
    ap.add_argument("--no-guard", action="store_true",
                    help="Skip apply_guard regression-check (faster, no auto-revert). "
                         "Default: use apply_guard now that .<game>_watch/ infra exists.")
    ap.add_argument("--bisect", action="store_true",
                    help="On guard failure, recursively halve the fix set to "
                         "isolate bad apples. Each isolated bad fix is added "
                         "to .compound_loop/blacklist.json. Pairs well with "
                         "COMPOUND_LOOP_SCOPED=1 (each bisect step is a "
                         "scoped ~30s decomp instead of 10min).")
    args = ap.parse_args()

    decomp_dir, all_types = paths_for(args.game)
    if not decomp_dir.exists() or not all_types.exists():
        print(f"ERROR: paths missing for {args.game}", file=sys.stderr)
        return 1

    if args.pattern:
        active_patterns = set(args.pattern)
    elif args.top > 0:
        active_patterns = set(SAFE_PATTERNS_ORDERED[: args.top])
    else:
        active_patterns = set(SAFE_PATTERNS_ORDERED)

    print(f"[{args.game}] using {len(active_patterns)} patterns: {sorted(active_patterns)}")
    print(f"[{args.game}] indexing {all_types.name} ...")
    method_line_index = build_method_line_index(all_types)
    _, parent_to_children = build_type_hierarchy(all_types)
    print(f"[{args.game}] {len(method_line_index)} method declarations")

    print(f"[{args.game}] scanning {decomp_dir} for WARNs ...")
    method_entries = collect_method_entries(decomp_dir)
    n_methods_with_mismatch = sum(len(m) for m in method_entries.values())
    print(f"[{args.game}] {n_methods_with_mismatch} methods have WARN data")

    reader = None if args.no_body_validate else MethodBodyReader(decomp_dir)
    fixes = plan_fixes(method_entries, method_line_index, parent_to_children,
                       active_patterns, reader=reader)
    print(f"[{args.game}] planned {len(fixes)} edits")

    # Filter against persistent blacklist (fixes that previously failed
    # apply_guard's regression-gate). Without this filter, every iteration
    # would re-attempt the same losing patches and waste a decomp cycle.
    fixes, skipped_bl = filter_blacklisted(fixes, args.game)
    if skipped_bl:
        print(f"[{args.game}] skipped {skipped_bl} blacklisted candidate(s); "
              f"{len(fixes)} remain")

    if not fixes:
        print(f"[{args.game}] nothing to do")
        return 0

    # Per-pattern breakdown
    pattern_count = {}
    for _, _, _, tag in fixes:
        # tag format: "type::method-N: decl → actual ..."
        try:
            parts = tag.split(": ", 1)[1]
            decl_actual = parts.split(" → ", 1)
            decl = decl_actual[0]
            actual = decl_actual[1].split(" ", 1)[0]
            pattern_count[(decl, actual)] = pattern_count.get((decl, actual), 0) + 1
        except (IndexError, ValueError):
            pass

    print(f"\nplanned edits by pattern:")
    for (d, a), c in sorted(pattern_count.items(), key=lambda x: -x[1])[:20]:
        print(f"  {c:>5}  {d} → {a}")

    if args.dry_run:
        print(f"\n[{args.game}] dry-run; first 10 edits:")
        for line_no, old, new, tag in fixes[:10]:
            print(f"  {all_types.name}:{line_no}  {tag}")
            print(f"    - {old.strip()}")
            print(f"    + {new.strip()}")
        return 0

    # Build short summary for commit message
    if len(active_patterns) == 1:
        d, a = next(iter(active_patterns))
        summary = f"return-mismatch {d}→{a} ({len(fixes)} methods)"
    else:
        summary = (f"return-mismatch batch ({len(fixes)} methods, "
                   f"{len(pattern_count)} patterns)")

    if args.no_guard:
        # Old behavior: write directly, optional commit, no validation.
        print(f"\n[{args.game}] applying {len(fixes)} edits to {all_types} (NO GUARD)")
        apply_fixes(all_types, fixes)
        print(f"[{args.game}] applied")
        if args.commit:
            sha = commit_change(args.game, all_types, summary)
            print(f"[{args.game}] committed {sha}")
        return 0

    # Default: use apply_guard for auto-validation.
    # Requires .<game>_watch/ infrastructure (jakx always has it; jak1/2/3
    # supported via scripts/game_watch/run.sh + measure_minimal.py).
    print(f"\n[{args.game}] applying {len(fixes)} edits via apply_guard ...")
    msg = (f"fix({args.game}/all-types): {summary}\n\n"
           f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>\n")

    edited_types = extract_edited_types_from_fixes(fixes)

    if args.bisect:
        # Recursive bisect: kept_fixes commit in subsets, blacklisted_fixes
        # are isolated bad apples added to .compound_loop/blacklist.json.
        msg_template = (f"fix({args.game}/all-types): return-mismatch "
                        f"bisect-pass ({{n}} fixes) [{{label}}]\n\n"
                        f"Co-Authored-By: Claude Opus 4.7 (1M context) "
                        f"<noreply@anthropic.com>\n")

        def apply_subset(subset):
            apply_fixes(all_types, subset)

        kept, blacklisted = bisect_apply(
            fixes, all_types,
            apply_fn=apply_subset,
            label=f"return-mismatch-{args.game}",
            game=args.game,
            extract_blacklist_key=lambda f: parse_fix_tag(f[3]),
            extract_edited_types=extract_edited_types_from_fixes,
            commit_on_pass=args.commit,
            commit_message_template=msg_template,
        )
        print(f"\n[{args.game}] BISECT DONE: {len(kept)}/{len(fixes)} fixes kept; "
              f"{len(blacklisted)} blacklisted")
        return 0

    def edit_fn():
        apply_fixes(all_types, fixes)
        return [all_types]

    result = run_with_guard(
        edit_fn,
        label=f"return-mismatch-{args.game}",
        commit_on_pass=args.commit,
        commit_message=msg,
        game=args.game,
        edited_types=edited_types,
    )
    if not result.passed:
        print(f"[{args.game}] FAIL — {result.reason}")
        return 2
    print(f"[{args.game}] PASS — Δerr={result.delta_err}, Δwarn={result.delta_warn}, "
          f"sha={result.commit_sha[:10] if result.commit_sha else '(no commit)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
