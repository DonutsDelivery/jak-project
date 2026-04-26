#!/usr/bin/env python3
"""cross_game_return_mismatch_consensus.py — multi-game consensus return-type fixer.

For each (type, method_num) declared in any game's all-types.gc, collect
the "actual return type" each game's decompiled body produces. When N
games agree on the same actual_return, the declaration is high-confidence
and we apply the fix everywhere that disagrees.

Why this is stronger than per-game return-mismatch fix:
  - Per-game: trust a single decompiler's WARN (could be artifact)
  - Consensus: 2-of-3 or 3-of-4 game agreement is corroborating evidence
  - Catches missed jakx fixes that have jak2/jak3 corroboration
  - Upstream PR maintainers trust consensus-validated fixes more

Usage:
  # Default: scan all 4 games, require 2-of-N agreement, dry-run
  python3 scripts/jakx_watch/cross_game_return_mismatch_consensus.py
  # Apply only ultra-high-confidence (3+ games agree)
  python3 scripts/jakx_watch/cross_game_return_mismatch_consensus.py --min-agreement 3 --apply --commit
"""
from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "jakx_watch"
sys.path.insert(0, str(SCRIPTS))

from return_mismatch_scan import build_method_line_index, scan_file  # noqa: E402
from return_mismatch_apply import (  # noqa: E402
    SAFE_PATTERNS_ORDERED,
    SKIP_VTABLE,
    collect_method_entries,
    apply_fixes,
    replace_return_type,
    RE_METHOD_LINE,
)

GAMES = ("jak1", "jak2", "jak3", "jakx")


def paths_for(game: str) -> tuple[Path, Path]:
    return (
        ROOT / "decompiler_out" / game,
        ROOT / "decompiler" / "config" / game / "all-types.gc",
    )


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
    ap.add_argument("--min-agreement", type=int, default=2,
                    help="Min games that must agree on actual_return (default: 2)")
    ap.add_argument("--safe-only", action="store_true",
                    help="Only apply if pattern in SAFE_PATTERNS_ORDERED")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--game", action="append",
                    help="Limit to specific games (repeat). Default: all 4")
    ap.add_argument("--exclude-jakx", action="store_true",
                    help="Skip applying to jakx (for upstream-only PR work)")
    args = ap.parse_args()

    target_games = list(args.game) if args.game else list(GAMES)
    safe_set = set(SAFE_PATTERNS_ORDERED) if args.safe_only else None

    # Step 1: Per-game scan — collect (type, method_num) → actual_return
    print(f"[consensus] scanning {len(target_games)} games ...")
    per_game_observations: dict[str, dict[tuple[str, int], str]] = {}
    per_game_index: dict[str, dict[tuple[str, int], tuple[int, str]]] = {}
    for game in target_games:
        decomp_dir, all_types = paths_for(game)
        if not decomp_dir.exists() or not all_types.exists():
            print(f"  [{game}] skip (paths missing)")
            continue
        method_index = build_method_line_index(all_types)
        method_entries = collect_method_entries(decomp_dir)
        # collect_method_entries returns {type: {mnum: (declared, actual)}}
        observations = {}
        for tp, methods in method_entries.items():
            for mnum, (decl, actual) in methods.items():
                observations[(tp, mnum)] = actual
        per_game_observations[game] = observations
        per_game_index[game] = method_index
        print(f"  [{game}] {len(observations)} method observations, "
              f"{len(method_index)} method declarations indexed")

    # Step 2: Build cross-game consensus table
    # For each (type, mnum), collect {game: actual_return}
    cross_table: dict[tuple[str, int], dict[str, str]] = collections.defaultdict(dict)
    for game, obs in per_game_observations.items():
        for key, actual in obs.items():
            cross_table[key][game] = actual

    # Step 3: For each method, find consensus actual_return
    consensus_fixes: dict[str, list[tuple[int, str, str, str]]] = collections.defaultdict(list)
    consensus_skipped = 0
    consensus_no_agreement = 0
    for (tp, mnum), game_actuals in cross_table.items():
        if mnum in SKIP_VTABLE:
            continue
        if len(game_actuals) < args.min_agreement:
            continue
        # Tally actual_return votes
        actual_votes = collections.Counter(game_actuals.values())
        top_actual, top_count = actual_votes.most_common(1)[0]
        if top_count < args.min_agreement:
            consensus_no_agreement += 1
            continue

        # Apply to every game where: (a) game has its own body observation
        # matching consensus, AND (b) declaration disagrees with consensus.
        # Without (a) we'd be guessing — game G's body may actually return
        # something different (especially for jak1 which has no WARNs).
        for game in target_games:
            if args.exclude_jakx and game == "jakx":
                continue
            game_obs = per_game_observations.get(game, {})
            if (tp, mnum) not in game_obs:
                continue  # this game didn't observe this method's body
            if game_obs[(tp, mnum)] != top_actual:
                continue  # this game's body disagrees with consensus (divergence)
            method_index = per_game_index.get(game, {})
            if (tp, mnum) not in method_index:
                continue
            line_no, old_line = method_index[(tp, mnum)]
            m = RE_METHOD_LINE.match(old_line)
            if not m:
                continue
            current_decl = m.group(2)
            if current_decl == top_actual:
                continue  # already correct
            # Check pattern safety
            if safe_set is not None and (current_decl, top_actual) not in safe_set:
                consensus_skipped += 1
                continue
            new_line = replace_return_type(old_line, current_decl, top_actual)
            if new_line is None:
                continue
            tag = (f"{tp}::method-{mnum}: {current_decl} → {top_actual} "
                   f"(consensus {top_count}/{len(game_actuals)} games)")
            consensus_fixes[game].append((line_no, old_line, new_line, tag))

    total_fixes = sum(len(v) for v in consensus_fixes.values())
    print(f"\n[consensus] cross-table: {len(cross_table)} unique (type, method) pairs")
    print(f"[consensus] {total_fixes} planned cross-game fixes "
          f"(min-agreement={args.min_agreement}, safe-only={args.safe_only})")
    print(f"[consensus] {consensus_no_agreement} pairs lacked sufficient agreement")
    if consensus_skipped:
        print(f"[consensus] {consensus_skipped} skipped (pattern not in SAFE_PATTERNS_ORDERED)")

    if total_fixes == 0:
        print("[consensus] nothing to do")
        return 0

    print(f"\nplanned fixes by game:")
    for game, fixes in sorted(consensus_fixes.items()):
        print(f"  [{game}] {len(fixes)} fixes")

    # Show sample
    print(f"\nfirst 5 fixes overall:")
    sample_count = 0
    for game, fixes in sorted(consensus_fixes.items()):
        for line_no, old, new, tag in fixes[:5]:
            print(f"  [{game}] line {line_no}: {tag}")
            print(f"    - {old.strip()}")
            print(f"    + {new.strip()}")
            sample_count += 1
            if sample_count >= 5:
                break
        if sample_count >= 5:
            break

    if not args.apply:
        print(f"\n[consensus] dry-run; pass --apply to write")
        return 0

    # Apply per-game
    for game, fixes in sorted(consensus_fixes.items()):
        if not fixes:
            continue
        _, all_types = paths_for(game)
        print(f"\n[{game}] applying {len(fixes)} consensus fixes ...")
        apply_fixes(all_types, sorted(fixes, key=lambda x: x[0]))
        if args.commit:
            summary = (f"return-mismatch consensus batch "
                       f"({len(fixes)} methods, ≥{args.min_agreement}-game agreement)")
            sha = commit_change(game, all_types, summary)
            print(f"[{game}] committed {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
