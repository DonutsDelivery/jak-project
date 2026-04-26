#!/usr/bin/env python3
"""iterative_compound_loop.py — chain extractors until convergence.

Run all available extractors in sequence per iteration. After each, the
decompiler re-runs and downstream extractors may see NEW candidates that
weren't visible before (because earlier fixes unblocked type prop). Loop
until 3 consecutive iterations produce zero change.

This compounds in two ways:
  1. Cascade: extractor A unblocks files that extractor B can now scan deeper
  2. Cross-game corroboration: consensus tool's high-confidence fixes corroborate
     the per-game tools' aggressive patterns

Tools chained per iteration (in order):
  1. cross_game_return_mismatch_consensus (ultra-safe, cross-corroborated)
  2. return_mismatch_apply --top 5 (per-game safe patterns)
  3. ir2_type_cast_extract (per-game, with apply_guard for jakx)
  4. ir2_store_cast_extract (per-game)

Each tool's commit lands separately so apply_guard / bisect can revert
the bad subset.

Usage:
  python3 scripts/jakx_watch/iterative_compound_loop.py --game jakx --max-iters 5
  python3 scripts/jakx_watch/iterative_compound_loop.py --game jakx --tools consensus,return_mismatch
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "jakx_watch"
STATUS_MD = ROOT / ".jakx_watch" / "status.md"

_RE_RC = re.compile(r"^\s*real-clean\s*:\s*(\d+)", re.MULTILINE)
_RE_ERR = re.compile(r"^inline ERROR markers:\s+(\d+)", re.MULTILINE)
_RE_WARN = re.compile(r"^inline WARN\s+markers:\s+(\d+)", re.MULTILINE)


def read_status() -> tuple[int, int, int]:
    """Parse rc / err / warn from status.md. Returns (-1, -1, -1) if unreadable."""
    if not STATUS_MD.exists():
        return (-1, -1, -1)
    text = STATUS_MD.read_text()
    rc_m = _RE_RC.search(text)
    err_m = _RE_ERR.search(text)
    warn_m = _RE_WARN.search(text)
    return (
        int(rc_m.group(1)) if rc_m else -1,
        int(err_m.group(1)) if err_m else -1,
        int(warn_m.group(1)) if warn_m else -1,
    )


def run_decompiler() -> int:
    """Run jakx_watch/run.sh — only valid for jakx."""
    import os
    env = {**os.environ, "JAKX_WATCH_FORCE": "1", "JAKX_WATCH_WAIT": "1"}
    r = subprocess.run(["bash", "scripts/jakx_watch/run.sh"], cwd=ROOT, env=env)
    return r.returncode


def run_tool(name: str, cmd: list[str], timeout: int = 1200) -> tuple[int, str]:
    """Run a tool, return (exit_code, last_50_lines_of_output)."""
    print(f"\n[loop] running: {name}")
    print(f"[loop]   $ {' '.join(cmd)}")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        dt = time.time() - t0
        out = (r.stdout or "") + (r.stderr or "")
        tail = "\n".join(out.splitlines()[-50:])
        print(f"[loop]   exit={r.returncode} ({dt:.1f}s)")
        # Print only last few lines for visibility
        for line in out.splitlines()[-5:]:
            print(f"[loop]     {line}")
        return r.returncode, tail
    except subprocess.TimeoutExpired:
        return -1, f"TIMEOUT after {timeout}s"


TOOLS = {
    "consensus": {
        "cmd": ["python3", "scripts/jakx_watch/cross_game_return_mismatch_consensus.py",
                "--min-agreement", "2", "--apply", "--commit"],
        "decomp_after": True,
    },
    "return_mismatch": {
        "cmd": ["python3", "scripts/jakx_watch/return_mismatch_apply.py",
                "--top", "5", "--commit"],
        "decomp_after": False,  # tool calls apply_guard which decomps internally
    },
    "type_cast": {
        "cmd": ["python3", "scripts/jakx_watch/ir2_type_cast_extract.py",
                "--apply", "--commit", "--batch-size", "15"],
        "decomp_after": False,
    },
    "store_cast": {
        "cmd": ["python3", "scripts/jakx_watch/ir2_store_cast_extract.py",
                "--apply", "--commit", "--batch-size", "15"],
        "decomp_after": False,
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="jakx", choices=("jakx",),
                    help="Game to compound on (only jakx supported — needs status.md)")
    ap.add_argument("--max-iters", type=int, default=5,
                    help="Max iterations before stopping")
    ap.add_argument("--zero-delta-stop", type=int, default=2,
                    help="Stop after N consecutive zero-Δ iterations")
    ap.add_argument("--tools", default="consensus,return_mismatch,type_cast,store_cast",
                    help="Comma-separated tool names to chain")
    args = ap.parse_args()

    tool_names = args.tools.split(",")
    for tn in tool_names:
        if tn not in TOOLS:
            print(f"ERROR: unknown tool '{tn}'. Valid: {list(TOOLS)}", file=sys.stderr)
            return 1

    print(f"[loop] iterative compound loop on {args.game}")
    print(f"[loop] tools: {tool_names}")
    print(f"[loop] max-iters: {args.max_iters}, zero-delta-stop: {args.zero_delta_stop}")

    # Initial baseline
    pre_rc, pre_err, pre_warn = read_status()
    if pre_rc < 0:
        print("[loop] status.md missing — running initial decomp")
        run_decompiler()
        pre_rc, pre_err, pre_warn = read_status()
    print(f"[loop] baseline: rc={pre_rc} err={pre_err} warn={pre_warn}")

    session_start_rc = pre_rc
    session_start_err = pre_err
    session_start_warn = pre_warn

    zero_delta_count = 0
    for it in range(1, args.max_iters + 1):
        print(f"\n{'='*60}\n[loop] ITERATION {it}\n{'='*60}")
        iter_start_rc, iter_start_err, iter_start_warn = read_status()

        for tn in tool_names:
            tool = TOOLS[tn]
            run_tool(tn, tool["cmd"])
            if tool.get("decomp_after"):
                print(f"[loop] re-decomping after {tn} ...")
                run_decompiler()

        # Final decomp at end of iteration to get true post-state
        print(f"\n[loop] iteration {it} complete — running final decomp ...")
        run_decompiler()

        post_rc, post_err, post_warn = read_status()
        d_rc = post_rc - iter_start_rc
        d_err = post_err - iter_start_err
        d_warn = post_warn - iter_start_warn
        print(f"\n[loop] iteration {it} delta: rc={d_rc:+d} err={d_err:+d} warn={d_warn:+d}")
        print(f"[loop] absolute: rc={post_rc} err={post_err} warn={post_warn}")

        if d_rc == 0 and d_err == 0 and d_warn == 0:
            zero_delta_count += 1
            print(f"[loop] zero-delta iteration ({zero_delta_count}/{args.zero_delta_stop})")
            if zero_delta_count >= args.zero_delta_stop:
                print(f"[loop] converged after {it} iterations")
                break
        else:
            zero_delta_count = 0

    final_rc, final_err, final_warn = read_status()
    total_d_rc = final_rc - session_start_rc
    total_d_err = final_err - session_start_err
    total_d_warn = final_warn - session_start_warn
    print(f"\n{'='*60}")
    print(f"[loop] SESSION TOTAL: rc={total_d_rc:+d} err={total_d_err:+d} warn={total_d_warn:+d}")
    print(f"[loop] final state:   rc={final_rc} err={final_err} warn={final_warn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
