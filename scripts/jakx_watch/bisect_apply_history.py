#!/usr/bin/env python3
"""bisect_apply_history.py — measure per-commit metric impact for a list of commits.

For each commit in the supplied list (oldest first), checkout the parent
state of the all-types.gc (or a list of files) to establish a baseline,
then walk forward applying each commit's version of those files in turn,
re-running game_watch decomp at every step and reporting Δrc / Δerr /
Δwarn / Δsplit-failed.

Use case: cycle 23 cleanup investigation. We had 3 jak3 commits and 3
jak2 commits flagged as possible regression sources. This tool measures
each one's actual impact under identical methodology (same game_watch
config across all data points), so the bisect is comparable.

Usage:
  python3 scripts/jakx_watch/bisect_apply_history.py \\
      --game jak3 \\
      --commits 010e5b8e5,36962a734,fa79677b3 \\
      --files decompiler/config/jak3/all-types.gc

  # Multiple files per commit:
  python3 scripts/jakx_watch/bisect_apply_history.py \\
      --game jakx --commits A,B,C \\
      --files decompiler/config/jakx/all-types.gc,decompiler/config/jakx/ntsc_v1/type_casts.jsonc

Output: prints a table to stdout with one row per (state):

  step                rc    err    warn    split    decomp_s
  pre-A             ...    ...    ...      ...        ...
  post-A            ...    ...    ...      ...        ...
  post-B            ...    ...    ...      ...        ...
  ...

Restores HEAD state on completion (or on error).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import read_status  # noqa: E402

GAMES = ("jak1", "jak2", "jak3", "jakx")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, check=check,
                          capture_output=True, text=True)


def head_sha() -> str:
    return git("rev-parse", "HEAD").stdout.strip()


def checkout_files_at(sha: str, files: list[str]) -> None:
    """git checkout <sha> -- <files>  (single call)."""
    git("checkout", sha, "--", *files)


def files_clean_at_head(files: list[str]) -> bool:
    """Return True if all files match HEAD (no unstaged diff)."""
    r = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *files],
        cwd=ROOT,
    )
    return r.returncode == 0


def run_decompiler(game: str) -> int:
    """Run the game-watch decomp pass. Returns exit code."""
    if game == "jakx":
        env = {**os.environ, "JAKX_WATCH_FORCE": "1", "JAKX_WATCH_WAIT": "1"}
        r = subprocess.run(["bash", "scripts/jakx_watch/run.sh"],
                           cwd=ROOT, env=env)
    else:
        env = {**os.environ, "GAME_WATCH_FORCE": "1", "GAME_WATCH_WAIT": "1"}
        r = subprocess.run(["bash", "scripts/game_watch/run.sh", "--game", game],
                           cwd=ROOT, env=env)
    return r.returncode


def measure(game: str, label: str) -> tuple[dict, float]:
    """Run decomp and return ({rc,err,warn,files,split}, decomp_seconds)."""
    t0 = time.time()
    rc = run_decompiler(game)
    dt = time.time() - t0
    s = read_status(game)
    return ({
        "rc": s.real_clean,
        "err": s.errors,
        "warn": s.warns,
        "files": s.files_total,
        "split": s.split_failed,
        "decomp_rc": rc,
    }, dt)


def fmt_row(label: str, m: dict, dt: float) -> str:
    return (f"{label:30s}  "
            f"rc={m['rc']} err={m['err']} warn={m['warn']} "
            f"files={m['files']} split={m['split']}  "
            f"(decomp {dt:.0f}s)")


def fmt_delta(prev: dict, cur: dict) -> str:
    drc = cur["rc"] - prev["rc"]
    derr = cur["err"] - prev["err"]
    dwarn = cur["warn"] - prev["warn"]
    dsplit = cur["split"] - prev["split"]
    return (f"  Δrc={drc:+d} Δerr={derr:+d} "
            f"Δwarn={dwarn:+d} Δsplit={dsplit:+d}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, choices=GAMES)
    ap.add_argument("--commits", required=True,
                    help="Comma-separated commit list, oldest first")
    ap.add_argument("--files", required=True,
                    help="Comma-separated file paths to checkout per step "
                         "(usually decompiler/config/<game>/all-types.gc)")
    ap.add_argument("--no-restore", action="store_true",
                    help="Skip HEAD restore at end (faster if you want to "
                         "iterate more on the final state)")
    args = ap.parse_args()

    commits = [c.strip() for c in args.commits.split(",") if c.strip()]
    files = [f.strip() for f in args.files.split(",") if f.strip()]

    if not commits:
        print("ERROR: --commits is empty", file=sys.stderr)
        return 1
    if not files:
        print("ERROR: --files is empty", file=sys.stderr)
        return 1

    saved_head = head_sha()
    print(f"[bisect:{args.game}] saved HEAD={saved_head}")
    print(f"[bisect:{args.game}] commits={commits}")
    print(f"[bisect:{args.game}] files={files}")

    if not files_clean_at_head(files):
        print(f"ERROR: files have unstaged changes:", file=sys.stderr)
        for f in files:
            print(f"  {f}", file=sys.stderr)
        print("Stash or commit first.", file=sys.stderr)
        return 1

    # Resolve commits to full SHAs (so checkout works even after future
    # rebases — and so we can compute parent-of-oldest)
    short_to_full = {}
    for c in commits:
        try:
            full = git("rev-parse", c).stdout.strip()
            short_to_full[c] = full
        except subprocess.CalledProcessError:
            print(f"ERROR: cannot resolve commit '{c}'", file=sys.stderr)
            return 1

    parent = git("rev-parse", f"{commits[0]}^").stdout.strip()
    print(f"[bisect:{args.game}] parent (pre-{commits[0]}) = {parent[:12]}")
    print()

    rows = []
    prev = None

    try:
        # Step 0: parent (pre-everything)
        checkout_files_at(parent, files)
        m, dt = measure(args.game, f"pre-{commits[0]}")
        label = f"pre-{commits[0]}"
        line = fmt_row(label, m, dt)
        print(line + (fmt_delta(prev, m) if prev else ""))
        rows.append((label, m, dt))
        prev = m

        # Steps 1..N: apply each commit's version
        for c in commits:
            checkout_files_at(short_to_full[c], files)
            m, dt = measure(args.game, f"post-{c}")
            label = f"post-{c}"
            line = fmt_row(label, m, dt)
            print(line + fmt_delta(prev, m))
            rows.append((label, m, dt))
            prev = m
    finally:
        if not args.no_restore:
            try:
                checkout_files_at(saved_head, files)
                print(f"\n[bisect:{args.game}] restored files to HEAD ({saved_head[:12]})")
            except subprocess.CalledProcessError as e:
                print(f"WARN: failed to restore HEAD: {e}", file=sys.stderr)

    # Summary table
    print("\n## Summary")
    print(f"{'step':32s}  {'rc':>4s}  {'err':>5s}  {'warn':>5s}  {'split':>5s}  Δrc  Δerr  Δwarn")
    prev_m = None
    for label, m, _ in rows:
        if prev_m is None:
            print(f"{label:32s}  {m['rc']:4d}  {m['err']:5d}  "
                  f"{m['warn']:5d}  {m['split']:5d}  (baseline)")
        else:
            drc = m['rc'] - prev_m['rc']
            derr = m['err'] - prev_m['err']
            dwarn = m['warn'] - prev_m['warn']
            print(f"{label:32s}  {m['rc']:4d}  {m['err']:5d}  "
                  f"{m['warn']:5d}  {m['split']:5d}  "
                  f"{drc:+3d}  {derr:+4d}  {dwarn:+5d}")
        prev_m = m

    return 0


if __name__ == "__main__":
    sys.exit(main())
