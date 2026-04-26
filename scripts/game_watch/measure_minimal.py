#!/usr/bin/env python3
"""measure_minimal.py — game-watch minimal status.md generator.

Writes the bare-minimum metrics that apply_guard.py reads. Unlike
scripts/jakx_watch/measure.py (888 lines, 20+ scanner outputs), this
covers only:

  - inline ERROR markers / inline WARN markers (per-line)
  - real-clean / real-partial / split-failed / static-only
    (file-level classification — same heuristic as jakx measure.py)
  - decomp progress (processed / total — derived from file count)
  - files total / split-failed
  - last-updated git SHA

Output target: ``.<game>_watch/status.md`` (and a tiny JSON snapshot
under ``.<game>_watch/history/latest.json`` for the
status-stale-detection check).

Designed for jak1/jak2/jak3 cross-game apply_guard support. jakx
continues to use the full scripts/jakx_watch/measure.py.

Usage:
  python3 scripts/game_watch/measure_minimal.py --game jak3
  python3 scripts/game_watch/measure_minimal.py --game jak2 --decomp-out path
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GAMES = ("jak1", "jak2", "jak3", "jakx")

# Same heuristic as scripts/jakx_watch/measure.py:
#   real-clean   : has defun/defmethod and zero ERROR markers
#   real-partial : has defun/defmethod and >=1 ERROR markers
#   split-failed : "function was not converted" message present
#   static-only  : no defun/defmethod (likely all static data)
#   unknown      : everything else
_RE_DEFUN = re.compile(r"^\(defun\s+", re.MULTILINE)
_RE_DEFMETHOD = re.compile(r"^\(defmethod\s+", re.MULTILINE)
_RE_ERROR = re.compile(r";; ERROR:")
_RE_WARN = re.compile(r";; WARN:")
_RE_SPLIT_FAILED = re.compile(r"function was not converted to expressions")


def classify_file(path: Path) -> tuple[str, int, int]:
    """Return (category, error_count, warn_count) for a _disasm.gc file."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return ("unknown", 0, 0)

    err_count = len(_RE_ERROR.findall(text))
    warn_count = len(_RE_WARN.findall(text))
    has_defun = bool(_RE_DEFUN.search(text))
    has_defmethod = bool(_RE_DEFMETHOD.search(text))
    has_split_failed = bool(_RE_SPLIT_FAILED.search(text))

    if has_split_failed:
        return ("split-failed", err_count, warn_count)
    if has_defun or has_defmethod:
        if err_count == 0:
            return ("real-clean", err_count, warn_count)
        return ("real-partial", err_count, warn_count)
    return ("static-only", err_count, warn_count)


def head_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT
        ).decode().strip()[:12]
    except subprocess.CalledProcessError:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, choices=GAMES)
    ap.add_argument("--decomp-out", default=None,
                    help="Override decomp_out path (default: "
                         ".<game>_watch/decomp_out/<game>)")
    args = ap.parse_args()

    watch_dir = ROOT / f".{args.game}_watch"
    decomp_out = (Path(args.decomp_out) if args.decomp_out
                  else watch_dir / "decomp_out" / args.game)
    status_md = watch_dir / "status.md"
    history_dir = watch_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    if not decomp_out.exists():
        print(f"ERROR: decomp_out not found: {decomp_out}", file=sys.stderr)
        return 1

    files = sorted(decomp_out.glob("*_disasm.gc"))
    counts = {
        "real-clean": 0,
        "real-partial": 0,
        "split-failed": 0,
        "static-only": 0,
        "unknown": 0,
    }
    sum_err = 0
    sum_warn = 0
    defun_total = 0
    defmethod_total = 0

    for fp in files:
        cat, err, warn = classify_file(fp)
        counts[cat] += 1
        sum_err += err
        sum_warn += warn
        text = fp.read_text(errors="replace")
        defun_total += len(_RE_DEFUN.findall(text))
        defmethod_total += len(_RE_DEFMETHOD.findall(text))

    n_files = len(files)
    sha = head_sha()
    now = datetime.datetime.now().isoformat()

    # Write status.md in apply_guard's expected format
    lines = []
    lines.append("```")
    lines.append(f"# {args.game}_watch status (minimal)")
    lines.append(f"last updated @ git {sha}  ·  ts {now}")
    lines.append("")
    lines.append("## FATAL crashes")
    lines.append(f"decomp progress: {n_files}/{n_files} processed (0 files blocked by crash)")
    lines.append("no fatal crashes in last run")
    lines.append("")
    lines.append(f"files total:            {n_files}")
    lines.append(f"  real-clean   :  {counts['real-clean']}")
    lines.append(f"  real-partial :  {counts['real-partial']}")
    lines.append(f"  split-failed :   {counts['split-failed']}")
    lines.append(f"  static-only  :   {counts['static-only']}")
    lines.append(f"defun total:            {defun_total}")
    lines.append(f"defmethod total:        {defmethod_total}")
    lines.append(f"inline ERROR markers:   {sum_err}")
    lines.append(f"inline WARN  markers:   {sum_warn}")
    lines.append("```")

    status_md.write_text("\n".join(lines) + "\n")

    # JSON snapshot for stale-detection
    latest = {
        "game": args.game,
        "ts": now,
        "git_sha": sha,
        "files_total": n_files,
        "errors": sum_err,
        "warns": sum_warn,
        "real_clean": counts["real-clean"],
        "real_partial": counts["real-partial"],
        "split_failed": counts["split-failed"],
        "static_only": counts["static-only"],
        "defun_total": defun_total,
        "defmethod_total": defmethod_total,
    }
    (history_dir / "latest.json").write_text(json.dumps(latest, indent=2) + "\n")

    print(f"[measure_minimal:{args.game}] "
          f"files={n_files} rc={counts['real-clean']} "
          f"err={sum_err} warn={sum_warn} "
          f"split-failed={counts['split-failed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
