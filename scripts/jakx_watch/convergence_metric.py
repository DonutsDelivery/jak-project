#!/usr/bin/env python3
"""convergence_metric.py — position metrics with ceilings, not direction signals.

rc/err are derivatives. They tell you "things got better" but not "we are 47%
of the way to done." Without a ceiling you can't tell acceleration from
deceleration; +47 rc this session could be 5% of remaining work or 0.5%.

This computes position metrics for jakx. Each metric has a defined ceiling
so the fraction-completed is a real number, not a vibe:

  signatures_complete  — methods with non-degenerate signatures
                         (decl_return matches body_return AND no `object`
                         parameter types AND not stub method-N)
                         CEILING: total method declarations
  unknown_type_refs    — IR2 references to types the decompiler can't
                         resolve. Each is a typing gap.
                         CEILING: 0
  failed_type_prop_ops — type-prop failures across all IR2 ops
                         CEILING: 0
  return_mismatch      — methods with declared-return ≠ body-return
                         CEILING: 0 (subset of signatures_complete)
  files_real_clean     — files with 0 ERROR markers
                         CEILING: total IR2 files

Output: appended to .compound_loop/convergence.jsonl as one row per run.
Each row: {ts, sha, game, ...metrics}. Trend = diff successive rows.

Usage:
  python3 scripts/jakx_watch/convergence_metric.py --game jakx
  python3 scripts/jakx_watch/convergence_metric.py --game jakx --json
  python3 scripts/jakx_watch/convergence_metric.py --trend 10  # last 10 rows
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOUND_LOOP_DIR = ROOT / ".compound_loop"
CONVERGENCE_LOG = COMPOUND_LOOP_DIR / "convergence.jsonl"

GAMES = ("jak1", "jak2", "jak3", "jakx")


def decomp_out_dir(game: str) -> Path:
    primary = ROOT / f".{game}_watch" / "decomp_out" / game
    if primary.exists() and any(primary.glob("*_ir2.asm")):
        return primary
    return ROOT / "decompiler_out" / game


# Minimum plausible file count — guards against picking an empty / barely
# initialized dir as a "stable" snapshot. The actual file count can vary
# legitimately as type-load failures crash specific files in/out of decomp,
# so we don't enforce a per-game floor.
MIN_PLAUSIBLE_IR2 = 50


def stable_decomp_dir(
    game: str, max_wait: int = 30, max_age_seconds: int = 3600,
) -> Path | None:
    """Return a decomp dir that looks settled and recent, or None.

    Stable = newest IR2 mtime in (now - max_age, now - 5sec). 5sec age is
    enough to confirm the decomp pipeline finished writing (no torn reads).
    max_age default 1h: after that, the snap describes state that may not
    match HEAD — refuse rather than log a misleading "current" row.

    File-count floor is just MIN_PLAUSIBLE_IR2 (50) to guard against
    near-empty dirs. The actual count can legitimately swing as type-load
    failures crash files in/out of decomp, so we don't enforce per-game
    floors.

    Watch dir is preferred when settled+recent (it's the freshest); falls
    back to canonical decompiler_out/<game>/ if watch is empty/stale.
    Returns None when no dir qualifies.
    """
    import time as _time
    deadline = _time.time() + max_wait

    while _time.time() < deadline:
        watch = ROOT / f".{game}_watch" / "decomp_out" / game
        canon = ROOT / "decompiler_out" / game
        now = _time.time()

        for cand in (watch, canon):
            if not cand.exists():
                continue
            files = list(cand.glob("*_ir2.asm"))
            if len(files) < MIN_PLAUSIBLE_IR2:
                continue
            newest = max((p.stat().st_mtime for p in files), default=0)
            age = now - newest
            if 5 <= age <= max_age_seconds:
                return cand
        _time.sleep(2)

    return None


def all_types_path(game: str) -> Path:
    return ROOT / "decompiler" / "config" / game / "all-types.gc"


# ---- Metric implementations -----------------------------------------------

# In :methods blocks, a method declaration looks like:
#   (NAME (_type_ ARGS...) RET) ;; SLOT_NUMBER
# Examples:
#   (inline-array-class-method-10 (_type_) none) ;; 10
#   (dead-pool-method-14 (_type_ type int object) none) ;; 14
#   (find-by-key (_type_ string) actor-hash-bucket) ;; 9
RE_METHOD_DECL = re.compile(
    r"^\s*\((?P<name>[\w\-!?<>=+\*/]+)\s+"
    r"\(_type_(?P<params>[^()]*)\)\s+"
    r"(?P<ret>[\w\-!?<>=+\*/]+)\)"
    r"\s*(?:;;.*)?$",
    re.MULTILINE,
)

# IR2 markers
RE_RETURN_MISMATCH = re.compile(
    r";; WARN: Return type mismatch \([^)]+\) vs [^.]+\.", re.MULTILINE
)
# Lowercase "failed" — that's what the decompiler actually emits.
# Examples: ";; ERROR: failed type prop at 24: add failed: ..."
RE_FAILED_TYPE_PROP = re.compile(r";; ERROR: failed type prop", re.MULTILINE)
# "Failed static ref finding" — the other major typing failure
RE_FAILED_STATIC_REF = re.compile(r";; ERROR: Failed static ref finding", re.MULTILINE)
# "Function may read a register that is not set" — caller/sig issue
RE_REG_NOT_SET = re.compile(r";; ERROR: Function may read a register", re.MULTILINE)
RE_ERROR_MARKER = re.compile(r"^;; ERROR:", re.MULTILINE)


def count_signatures(types_path: Path) -> tuple[int, int]:
    """Return (total_method_decls, complete_decls).

    A decl is "complete" if it has no `object` parameter type and the method
    name isn't bare 'method-N'. These are the heuristic markers of a real
    signature vs. a stub left after sig_passthrough placeholders.
    """
    if not types_path.exists():
        return (0, 0)
    text = types_path.read_text(errors="replace")
    total = 0
    complete = 0
    for m in RE_METHOD_DECL.finditer(text):
        total += 1
        method_name = m.group(1)
        params = m.group("params").split()
        if method_name.startswith("method-") and method_name[7:].isdigit():
            continue  # stub name
        if "object" in params:
            continue  # placeholder param
        complete += 1
    return (total, complete)


def scan_ir2_metrics(decomp_dir: Path) -> dict[str, int]:
    """Walk all IR2 files and tally markers."""
    if not decomp_dir.exists():
        return {
            "files_total": 0,
            "files_real_clean": 0,
            "return_mismatch_warns": 0,
            "failed_type_prop_errors": 0,
            "failed_static_ref_errors": 0,
            "reg_not_set_errors": 0,
        }
    files_total = 0
    files_real_clean = 0
    rm_warns = 0
    ftp_errs = 0
    fsr_errs = 0
    reg_errs = 0
    for p in decomp_dir.glob("*_ir2.asm"):
        files_total += 1
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        n_err = len(RE_ERROR_MARKER.findall(text))
        if n_err == 0:
            files_real_clean += 1
        rm_warns += len(RE_RETURN_MISMATCH.findall(text))
        ftp_errs += len(RE_FAILED_TYPE_PROP.findall(text))
        fsr_errs += len(RE_FAILED_STATIC_REF.findall(text))
        reg_errs += len(RE_REG_NOT_SET.findall(text))
    return {
        "files_total": files_total,
        "files_real_clean": files_real_clean,
        "return_mismatch_warns": rm_warns,
        "failed_type_prop_errors": ftp_errs,
        "failed_static_ref_errors": fsr_errs,
        "reg_not_set_errors": reg_errs,
    }


def head_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT
        ).decode().strip()
    except subprocess.CalledProcessError:
        return ""


def compute(game: str, wait_for_stable: bool = True) -> dict:
    """Compute the full metric snapshot for game.

    If wait_for_stable, pick a decomp dir whose file count is plausible and
    whose newest IR2 settled >5 sec ago. Falls back to whichever dir has the
    most files. If no stable dir found, marks snap with unstable=True so
    downstream analysis can filter races out.
    """
    types_path = all_types_path(game)
    if wait_for_stable:
        decomp_dir = stable_decomp_dir(game)
    else:
        decomp_dir = decomp_out_dir(game)
    total_decls, complete_decls = count_signatures(types_path)
    if decomp_dir is None:
        ir2 = scan_ir2_metrics(ROOT / "nonexistent")  # zeros
        unstable = True
    else:
        ir2 = scan_ir2_metrics(decomp_dir)
        unstable = ir2["files_total"] < MIN_PLAUSIBLE_IR2
    snap = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "sha": head_sha()[:12],
        "game": game,
        "unstable": unstable,
        # Position metrics with ceilings
        "method_decls_total": total_decls,
        "method_decls_complete": complete_decls,
        "method_decls_complete_pct": (
            round(100.0 * complete_decls / total_decls, 2) if total_decls else 0.0
        ),
        "files_real_clean_pct": (
            round(100.0 * ir2["files_real_clean"] / ir2["files_total"], 2)
            if ir2["files_total"] else 0.0
        ),
        # Direction metrics (kept for compat with old graphs)
        **ir2,
    }
    return snap


def append_log(snap: dict) -> None:
    COMPOUND_LOOP_DIR.mkdir(parents=True, exist_ok=True)
    with CONVERGENCE_LOG.open("a") as f:
        f.write(json.dumps(snap) + "\n")


def show_trend(n: int, game_filter: str | None = None) -> None:
    """Print last N rows + per-metric deltas."""
    if not CONVERGENCE_LOG.exists():
        print("(no convergence.jsonl yet — run without --trend first)")
        return
    rows = []
    for line in CONVERGENCE_LOG.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if game_filter and r.get("game") != game_filter:
            continue
        rows.append(r)
    rows = rows[-n:]
    if not rows:
        print("(no rows match)")
        return
    print(f"\n{'ts':<20} {'sha':<10} {'game':<5} {'sig%':<6} "
          f"{'rc%':<6} {'rm':<6} {'ftp':<6} {'fsr':<5} {'rns':<5} {'!':<2}")
    print("-" * 80)
    prev_stable = None
    for r in rows:
        marker = "RACE" if r.get("unstable") else "  "
        line = (f"{r['ts']:<20} {r['sha']:<10} {r['game']:<5} "
                f"{r['method_decls_complete_pct']:<6.2f} "
                f"{r['files_real_clean_pct']:<6.2f} "
                f"{r['return_mismatch_warns']:<6d} "
                f"{r['failed_type_prop_errors']:<6d} "
                f"{r.get('failed_static_ref_errors', 0):<5d} "
                f"{r.get('reg_not_set_errors', 0):<5d} "
                f"{marker:<4}")
        # Only compute deltas against previous STABLE row
        if prev_stable and not r.get("unstable"):
            d_sig = r['method_decls_complete'] - prev_stable['method_decls_complete']
            d_rc = r['files_real_clean'] - prev_stable['files_real_clean']
            d_ftp = r['failed_type_prop_errors'] - prev_stable['failed_type_prop_errors']
            line += f"   Δsig{d_sig:+d} Δrc{d_rc:+d} Δftp{d_ftp:+d}"
        print(line)
        if not r.get("unstable"):
            prev_stable = r


def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", choices=GAMES, default="jakx")
    ap.add_argument("--json", action="store_true",
                    help="Print full snapshot JSON (also appends to log)")
    ap.add_argument("--no-log", action="store_true",
                    help="Compute + print but don't append to convergence.jsonl")
    ap.add_argument("--trend", type=int, default=0,
                    help="Show last N rows + deltas (skips compute)")
    args = ap.parse_args()

    if args.trend > 0:
        show_trend(args.trend, game_filter=args.game)
        return 0

    snap = compute(args.game)
    if not args.no_log:
        append_log(snap)

    if args.json:
        print(json.dumps(snap, indent=2))
    else:
        print(f"\n=== {args.game} convergence @ {snap['sha']} ===")
        print(f"signatures complete:  {snap['method_decls_complete']:>5}/"
              f"{snap['method_decls_total']:<5}  "
              f"({snap['method_decls_complete_pct']:.2f}% of ceiling)")
        print(f"files real-clean:     {snap['files_real_clean']:>5}/"
              f"{snap['files_total']:<5}  "
              f"({snap['files_real_clean_pct']:.2f}% of ceiling)")
        print(f"return-mismatch WARNs:{snap['return_mismatch_warns']:>5}  "
              f"(ceiling: 0)")
        print(f"failed type-prop errs:{snap['failed_type_prop_errors']:>5}  "
              f"(ceiling: 0)")
        print(f"failed static-ref errs:{snap['failed_static_ref_errors']:>4}  "
              f"(ceiling: 0)")
        print(f"reg-not-set errors:   {snap['reg_not_set_errors']:>5}  "
              f"(ceiling: 0)")
        if not args.no_log:
            print(f"\nappended to {CONVERGENCE_LOG.relative_to(ROOT)}")
            print(f"trend: python3 scripts/jakx_watch/convergence_metric.py "
                  f"--game {args.game} --trend 10")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
