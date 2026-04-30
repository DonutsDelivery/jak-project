#!/usr/bin/env python3
"""auto_pattern_loop.py — orchestrator-driven feedback loop.

Runs the existing pattern extractors (ir2_type_cast_extract, type_cast_extractor)
end-to-end with WIP-stash isolation and apply_guard bisect-revert. Designed to
be invoked once per cron fire by the orchestrator, between dispatching agents.

Workflow per invocation:
  1. Read current offline_test.green count from latest.json (G0 primary metric).
  2. Stash any WIP in config files (Sonnet/Opus collision avoidance).
  3. Run ir2_type_cast_extract.py --apply --commit (uses apply_guard internally,
     which runs run.sh → offline_test_pass.py → updates latest.json).
  4. Re-read offline_test.green from latest.json; compare delta.
  5. Restore stash (pop, manual merge if conflict).
  6. Report: Δpass (primary), Δrc (secondary), candidates tried.

G0 compliance: verdict and exit code are based on Δpass (offline_test.green),
not Δrc. rc is shown as a secondary signal only. See STOP_CONDITIONS.md G0.

Output: .jakx_watch/research/auto_pattern_loop_<ts>.md

Exit code 0 if Δpass > 0, 1 if no pass growth, 2 if pass regression.

Usage:
  python3 scripts/jakx_watch/auto_pattern_loop.py [--dry-run] [--max-batch N]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "jakx_watch"
SNAP_DIR = ROOT / ".jakx_watch" / "history"
RESEARCH = ROOT / ".jakx_watch" / "research"
LOCK = "/tmp/jakx-decomp.lock"

WIP_PATHS = [
    "decompiler/config/jakx/all-types.gc",
    "decompiler/config/jakx/ntsc_v1/type_casts.jsonc",
    "decompiler/config/jakx/ntsc_v1/stack_structures.jsonc",
    "decompiler/config/jakx/ntsc_v1/label_types.jsonc",
    "decompiler/config/jakx/ntsc_v1/hacks.jsonc",
]

STASH_NAME = "auto-pattern-loop-wip"


def sh(cmd, cwd=ROOT, check=False, timeout=900):
    """Run shell command, return (returncode, stdout, stderr)."""
    p = subprocess.run(
        cmd, shell=True, cwd=cwd, capture_output=True, text=True,
        timeout=timeout,
    )
    if check and p.returncode != 0:
        sys.stderr.write(f"FAIL: {cmd}\nstdout: {p.stdout}\nstderr: {p.stderr}\n")
        sys.exit(1)
    return p.returncode, p.stdout, p.stderr


LATEST_JSON = ROOT / ".jakx_watch" / "history" / "latest.json"


def read_pass_count():
    """Read offline_test.green count from latest.json (G0 primary metric).

    Returns (green, amber, candidates) or (None, None, None) if unavailable.
    offline_test data is written by offline_test_pass.py inside run.sh, so it
    is always up-to-date after any decomp run.
    """
    if not LATEST_JSON.exists():
        return None, None, None
    try:
        d = json.load(open(LATEST_JSON))
        ot = d.get("offline_test", {})
        green = len(ot.get("green", []))
        amber = len(ot.get("amber", []))
        candidates = ot.get("candidates", green + amber)
        return green, amber, candidates
    except Exception:
        return None, None, None


def latest_snap():
    snaps = sorted(SNAP_DIR.glob("snap-*.json"), key=lambda p: p.stat().st_mtime)
    if not snaps:
        return None, None, None
    s = snaps[-1]
    d = json.load(open(s))
    sm = d["summary"]
    return s.name, sm["buckets"]["real-clean"], sm["sum_error_markers"]


def has_wip():
    rc, out, _ = sh("git status --porcelain " + " ".join(WIP_PATHS))
    return bool(out.strip())


def stash_wip():
    if not has_wip():
        return False
    rc, out, err = sh(
        f"git stash push -u -m '{STASH_NAME}' -- " + " ".join(WIP_PATHS)
    )
    return rc == 0 and "No local changes to save" not in (out + err)


def restore_wip():
    rc, out, _ = sh(f"git stash list | head -1")
    if STASH_NAME not in out:
        return True  # nothing to restore
    rc, out, err = sh("git stash pop")
    if rc != 0:
        sys.stderr.write(
            f"STASH POP CONFLICT — manual merge needed.\n"
            f"stdout: {out}\nstderr: {err}\n"
            f"Stash NAME: {STASH_NAME}. Use `git stash list` + `git stash pop`.\n"
        )
        return False
    return True


def run_extractor(dry=False, max_batch=10):
    """Run ir2_type_cast_extract with apply+commit."""
    args = ["python3", str(SCRIPTS / "ir2_type_cast_extract.py")]
    if dry:
        args += ["--dry-run", "--stats"]
    else:
        # err-slack=2: subclass-downcasts can legitimately expose 1-2 previously
        # hidden errors (type info was wrong before; now correct type reveals them).
        # This is fine — correctness matters more than the error count.
        args += ["--apply", "--commit", f"--batch-size={max_batch}", "--err-slack=2"]
    cmd = " ".join(args)
    rc, out, err = sh(cmd, timeout=1800)
    return rc, out + ("\n--STDERR--\n" + err if err else "")


def write_report(pre_pass, post_pass, pre_rc, post_rc, pre_err, post_err,
                 applied_log, stashed, dry):
    RESEARCH.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    p = RESEARCH / f"auto_pattern_loop_{ts}.md"
    delta_pass = (post_pass or 0) - (pre_pass or 0)
    delta_rc = (post_rc or 0) - (pre_rc or 0)
    delta_err = (post_err or 0) - (pre_err or 0)
    if dry:
        verdict = "DRY-RUN (no changes applied)"
    elif delta_pass > 0:
        verdict = "GROWTH"
    elif delta_pass == 0:
        verdict = "NO-GROWTH"
    else:
        verdict = "REGRESSION"
    body = f"""# auto_pattern_loop run {ts}

dry_run: {dry}
stashed_wip: {stashed}

## Result (G0: Δpass is primary)
| metric | pre | post | delta |
|---|---:|---:|---:|
| **offline_test pass (PRIMARY)** | **{pre_pass}** | **{post_pass}** | **{delta_pass:+d}** |
| real-clean (secondary) | {pre_rc} | {post_rc} | {delta_rc:+d} |
| errors | {pre_err} | {post_err} | {delta_err:+d} |

## Verdict
{verdict}

## Applier output (last 4000 chars)
```
{applied_log[-4000:]}
```
"""
    p.write_text(body)
    return p, delta_pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Count candidates only, don't apply or run decompiler")
    ap.add_argument("--max-batch", type=int, default=10,
                    help="Max candidates per applier invocation")
    args = ap.parse_args()

    print(f"[auto-loop] starting  dry={args.dry_run}  max-batch={args.max_batch}")

    # Read pre-run pass count (G0 primary) and rc (secondary)
    pre_pass, pre_amber, pre_candidates = read_pass_count()
    snap_pre, pre_rc, pre_err = latest_snap()
    print(f"[auto-loop] pre  pass={pre_pass} amber={pre_amber} rc={pre_rc} err={pre_err}")

    stashed = False
    if not args.dry_run:
        stashed = stash_wip()
        print(f"[auto-loop] stashed WIP: {stashed}")

    try:
        rc, out = run_extractor(dry=args.dry_run, max_batch=args.max_batch)
        print(f"[auto-loop] extractor exit={rc}")
    finally:
        if stashed:
            restored = restore_wip()
            print(f"[auto-loop] WIP restored: {restored}")

    if not args.dry_run:
        # Re-read pass + rc after extractor (apply_guard ran run.sh → offline_test_pass.py)
        post_pass, post_amber, _ = read_pass_count()
        snap_post, post_rc, post_err = latest_snap()
        print(f"[auto-loop] post pass={post_pass} amber={post_amber} rc={post_rc} err={post_err}")
    else:
        post_pass, post_amber = pre_pass, pre_amber
        post_rc, post_err = pre_rc, pre_err

    p, delta = write_report(pre_pass, post_pass, pre_rc, post_rc,
                            pre_err, post_err, out, stashed, args.dry_run)
    print(f"[auto-loop] report: {p}  delta_pass={delta:+d}")

    if delta > 0:
        sys.exit(0)
    elif delta == 0:
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
