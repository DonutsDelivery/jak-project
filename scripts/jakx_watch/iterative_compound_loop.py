#!/usr/bin/env python3
"""iterative_compound_loop.py — chain ALL extractors across ALL games until convergence.

Each iteration runs:
  1. cross_game_return_mismatch_consensus (cross-corroborated, all games)
  2. For each target game, in order:
     a. return_mismatch_apply --top 5 (per-game safe patterns)
     b. ir2_type_cast_extract --game G (per-game type_cast)
     c. ir2_store_cast_extract (jakx for now, until --game added)
  3. Decomp each game via apply_guard / game_watch (apply_guard handles per-tool)
  4. Measure deltas via game-specific status.md

Compounds in three ways:
  - Tool cascade: A's fix unblocks B's candidates within an iteration
  - Cross-game corroboration: consensus tool's fix is one game's evidence for another's
  - Game cross-feed: jak3's clean state strengthens jakx's consensus signal

Each tool's commit lands separately; apply_guard handles bisect-revert per batch.

Usage:
  python3 scripts/jakx_watch/iterative_compound_loop.py             # all games, all tools
  python3 scripts/jakx_watch/iterative_compound_loop.py --game jakx # jakx only
  python3 scripts/jakx_watch/iterative_compound_loop.py --tools consensus,return_mismatch
  python3 scripts/jakx_watch/iterative_compound_loop.py --max-iters 3 --zero-delta-stop 1
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "jakx_watch"

GAMES = ("jak1", "jak2", "jak3", "jakx")

_RE_RC = re.compile(r"^\s*real-clean\s*:\s*(\d+)", re.MULTILINE)
_RE_ERR = re.compile(r"^inline ERROR markers:\s+(\d+)", re.MULTILINE)
_RE_WARN = re.compile(r"^inline WARN\s+markers:\s+(\d+)", re.MULTILINE)


def status_md_for(game: str) -> Path:
    return ROOT / f".{game}_watch" / "status.md"


def read_status(game: str) -> tuple[int, int, int]:
    """Parse rc / err / warn from game's status.md. Returns (-1, -1, -1) if missing."""
    sp = status_md_for(game)
    if not sp.exists():
        return (-1, -1, -1)
    text = sp.read_text()
    rc_m = _RE_RC.search(text)
    err_m = _RE_ERR.search(text)
    warn_m = _RE_WARN.search(text)
    return (
        int(rc_m.group(1)) if rc_m else -1,
        int(err_m.group(1)) if err_m else -1,
        int(warn_m.group(1)) if warn_m else -1,
    )


def run_decompiler(game: str) -> int:
    """Run game-specific decomp pipeline."""
    if game == "jakx":
        env = {**os.environ, "JAKX_WATCH_FORCE": "1", "JAKX_WATCH_WAIT": "1"}
        r = subprocess.run(["bash", "scripts/jakx_watch/run.sh"], cwd=ROOT, env=env)
    else:
        env = {**os.environ, "GAME_WATCH_FORCE": "1", "GAME_WATCH_WAIT": "1"}
        r = subprocess.run(
            ["bash", "scripts/game_watch/run.sh", "--game", game],
            cwd=ROOT, env=env,
        )
    return r.returncode


def run_tool(label: str, cmd: list[str], timeout: int = 1800) -> int:
    """Run a tool, print the last few output lines."""
    print(f"\n[loop] {label}")
    print(f"[loop]   $ {' '.join(cmd)}")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        dt = time.time() - t0
        out = (r.stdout or "") + (r.stderr or "")
        print(f"[loop]   exit={r.returncode} ({dt:.1f}s)")
        for line in out.splitlines()[-6:]:
            print(f"[loop]     {line}")
        return r.returncode
    except subprocess.TimeoutExpired:
        print(f"[loop]   TIMEOUT after {timeout}s")
        return -1


# Per-tool wiring: which command + which games it supports
def cmd_consensus() -> list[str]:
    """Cross-game consensus pass — operates on all games at once via internal logic."""
    return ["python3", "scripts/jakx_watch/cross_game_return_mismatch_consensus.py",
            "--min-agreement", "2", "--apply", "--commit"]


def cmd_return_mismatch(game: str, top: int = 5) -> list[str]:
    if game == "jakx":
        return ["python3", "scripts/jakx_watch/return_mismatch_apply.py",
                "--top", str(top), "--commit"]
    return ["python3", "scripts/jakx_watch/cross_game_return_mismatch_apply.py",
            "--game", game, "--top", str(top), "--commit"]


def cmd_type_cast(game: str, batch: int = 15) -> list[str]:
    return ["python3", "scripts/jakx_watch/ir2_type_cast_extract.py",
            "--game", game, "--apply", "--commit", "--batch-size", str(batch)]


def cmd_store_cast(game: str, batch: int = 15) -> list[str]:
    # store_cast_extract doesn't yet have --game; falls back to jakx-only.
    if game != "jakx":
        return None
    return ["python3", "scripts/jakx_watch/ir2_store_cast_extract.py",
            "--apply", "--commit", "--batch-size", str(batch)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="all", choices=("all",) + GAMES,
                    help="Target game (default: all). 'all' iterates jakx, jak3, jak2 (skip jak1 — clean).")
    ap.add_argument("--max-iters", type=int, default=3,
                    help="Max iterations per session")
    ap.add_argument("--zero-delta-stop", type=int, default=1,
                    help="Stop after N consecutive zero-Δ iterations across all target games")
    ap.add_argument("--tools",
                    default="consensus,return_mismatch,type_cast,store_cast",
                    help="Comma-separated tool names to chain per iteration")
    ap.add_argument("--top", type=int, default=5,
                    help="--top N for return_mismatch_apply (default: 5)")
    ap.add_argument("--batch-size", type=int, default=15,
                    help="--batch-size for type_cast / store_cast extractors")
    args = ap.parse_args()

    if args.game == "all":
        # jak1 has 0 return-mismatch WARNs upstream, skip it.
        target_games = ["jakx", "jak3", "jak2"]
    else:
        target_games = [args.game]

    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    valid_tools = {"consensus", "return_mismatch", "type_cast", "store_cast"}
    for t in tools:
        if t not in valid_tools:
            print(f"ERROR: unknown tool '{t}'. Valid: {sorted(valid_tools)}", file=sys.stderr)
            return 1

    print(f"[loop] target games: {target_games}")
    print(f"[loop] tools per iter: {tools}")
    print(f"[loop] max-iters: {args.max_iters}, zero-delta-stop: {args.zero_delta_stop}")

    # Initial baseline per game
    baselines: dict[str, tuple[int, int, int]] = {}
    for g in target_games:
        rc, err, warn = read_status(g)
        if rc < 0:
            print(f"[loop] {g}: status.md missing — bootstrapping decomp")
            run_decompiler(g)
            rc, err, warn = read_status(g)
        baselines[g] = (rc, err, warn)
        print(f"[loop] {g} baseline: rc={rc} err={err} warn={warn}")

    session_start = dict(baselines)

    zero_delta_count = 0
    for it in range(1, args.max_iters + 1):
        print(f"\n{'='*64}\n[loop] ITERATION {it}\n{'='*64}")
        iter_start = {g: read_status(g) for g in target_games}

        # 1) Cross-game consensus (operates on all games at once)
        if "consensus" in tools:
            run_tool("consensus", cmd_consensus())

        # 2-4) Per-game tools, in game order
        for game in target_games:
            print(f"\n[loop] --- game: {game} ---")
            if "return_mismatch" in tools:
                run_tool(f"return_mismatch [{game}]",
                         cmd_return_mismatch(game, args.top))
            if "type_cast" in tools:
                run_tool(f"type_cast [{game}]",
                         cmd_type_cast(game, args.batch_size))
            if "store_cast" in tools:
                cmd = cmd_store_cast(game, args.batch_size)
                if cmd is not None:
                    run_tool(f"store_cast [{game}]", cmd)

        # Measure
        iter_end = {g: read_status(g) for g in target_games}
        any_change = False
        print(f"\n[loop] iter {it} per-game deltas:")
        for g in target_games:
            ds_rc = iter_end[g][0] - iter_start[g][0]
            ds_err = iter_end[g][1] - iter_start[g][1]
            ds_warn = iter_end[g][2] - iter_start[g][2]
            print(f"[loop]   {g}: rc={ds_rc:+d} err={ds_err:+d} warn={ds_warn:+d}  "
                  f"(abs: rc={iter_end[g][0]} err={iter_end[g][1]} warn={iter_end[g][2]})")
            if ds_rc != 0 or ds_err != 0 or ds_warn != 0:
                any_change = True

        if not any_change:
            zero_delta_count += 1
            print(f"[loop] zero-delta iteration ({zero_delta_count}/{args.zero_delta_stop})")
            if zero_delta_count >= args.zero_delta_stop:
                print(f"[loop] converged after {it} iterations")
                break
        else:
            zero_delta_count = 0

    # Session summary
    print(f"\n{'='*64}")
    print(f"[loop] SESSION SUMMARY")
    print(f"{'='*64}")
    for g in target_games:
        final = read_status(g)
        start = session_start[g]
        print(f"[loop] {g}: rc {start[0]:>4}→{final[0]:<4} (Δ{final[0]-start[0]:+d})  "
              f"err {start[1]:>5}→{final[1]:<5} (Δ{final[1]-start[1]:+d})  "
              f"warn {start[2]:>5}→{final[2]:<5} (Δ{final[2]-start[2]:+d})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
