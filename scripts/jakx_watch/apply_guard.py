#!/usr/bin/env python3
"""Shared regression-gate for jakx_watch bulk-apply scripts.

Usage::

    from apply_guard import run_with_guard, GuardResult

    def my_edits() -> list[Path]:
        # apply changes, return list of modified files
        return [CURRENT_TYPES]

    result = run_with_guard(my_edits, label="my-batch", commit_on_pass=True)
    if not result.passed:
        print("Regression detected, reverted:", result.reason)
        sys.exit(1)
    print(f"Committed {result.commit_sha}: Δerr={result.delta_err} Δwarn={result.delta_warn}")

The gate:
  1. Reads pre-state from status.md (total err + warn + top-8 category breakdown).
  2. Calls edit_fn() which applies edits and returns a list of modified file paths.
  3. Re-runs the decompiler (flock-serialized via run.sh with JAKX_WATCH_FORCE=1 +
     JAKX_WATCH_WAIT=1).
  4. Reads new status.md.
  5. If status.md is unreadable (decompiler crash), or total_err grew beyond
     ``err_slack``, or any category regressed beyond ``category_regressions_allowed``:
     reverts all changed files via ``git checkout HEAD -- <path>``, returns FAIL.
  6. Otherwise: optionally commits, returns PASS with Δerr, Δwarn.
"""
from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
STATUS_MD = ROOT / ".jakx_watch" / "status.md"

_RE_ERR_TOTAL = re.compile(r"^inline ERROR markers:\s+(\d+)", re.MULTILINE)
_RE_WARN_TOTAL = re.compile(r"^inline WARN\s+markers:\s+(\d+)", re.MULTILINE)
_RE_CATEGORY_LINE = re.compile(r"^\s+(\d+)\s+(.+)$")
_RE_DECOMP_PROGRESS = re.compile(
    r"decomp progress:\s*(\d+)/(\d+)\s+processed"
)
_RE_FILES_TOTAL = re.compile(r"^files total:\s+(\d+)", re.MULTILINE)
_RE_SPLIT_FAILED = re.compile(r"^\s+split-failed\s+:\s+(\d+)", re.MULTILINE)
# Match only actual crash content — not the "## FATAL crashes" section header,
# which is present on every clean run. "Assertion failed" = literal C++ assert;
# "files blocked by crash" with non-zero count = scanner recorded crashes.
_RE_ASSERTION = re.compile(r"Assertion failed", re.MULTILINE)
_RE_BLOCKED_COUNT = re.compile(
    r"decomp progress:\s*\d+/\d+\s+processed\s*\((\d+)\s+files?\s+blocked",
    re.MULTILINE,
)
_RE_STATUS_HEAD_SHA = re.compile(r"last updated @ git ([0-9a-f]{7,40})", re.MULTILINE)


def _current_head_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT
        ).decode().strip()
    except subprocess.CalledProcessError:
        return ""


def _status_is_stale(snap: "StatusSnapshot") -> bool:
    """Return True if current status.md looks stale or crash-captured.
    Stale conditions:
      - File missing or unparseable
      - Captures an in-progress crash (has_assertion, partial processed count)

    Note: we intentionally do NOT trigger on SHA mismatch alone. In a batch
    loop, status.md is written pre-commit, then HEAD advances at commit time.
    status.md's recorded SHA lags by one commit, but its CONTENT reflects
    the current working-tree state (= HEAD post-commit). Triggering rescan
    on SHA mismatch would waste a full scanner run between every iteration.
    """
    if not snap.valid:
        return True
    if snap.has_assertion:
        return True
    if snap.processed > 0 and snap.total > 0 and snap.processed < snap.total:
        return True
    return False


@dataclasses.dataclass
class StatusSnapshot:
    errors: int
    warns: int
    categories: dict[str, int]  # top-8 error category text → count
    # Coverage / crash fields
    processed: int = -1     # files decompiled this run
    total: int = -1         # total files known
    files_total: int = -1   # "files total:" line (may differ from total)
    split_failed: int = -1  # split-failed count
    has_assertion: bool = False  # "Assertion failed" in status.md

    @property
    def valid(self) -> bool:
        return self.errors >= 0 and self.warns >= 0


@dataclasses.dataclass
class GuardResult:
    passed: bool
    reason: str
    delta_err: int = 0
    delta_warn: int = 0
    edit_count: int = 0
    commit_sha: str = ""


def read_status() -> StatusSnapshot:
    """Parse current status.md. Returns invalid snapshot on parse failure."""
    if not STATUS_MD.exists():
        return StatusSnapshot(-1, -1, {})
    text = STATUS_MD.read_text()
    em = _RE_ERR_TOTAL.search(text)
    wm = _RE_WARN_TOTAL.search(text)
    errors = int(em.group(1)) if em else -1
    warns = int(wm.group(1)) if wm else -1

    # Coverage metrics
    pm = _RE_DECOMP_PROGRESS.search(text)
    processed = int(pm.group(1)) if pm else -1
    total = int(pm.group(2)) if pm else -1

    fm = _RE_FILES_TOTAL.search(text)
    files_total = int(fm.group(1)) if fm else -1

    sm = _RE_SPLIT_FAILED.search(text)
    split_failed = int(sm.group(1)) if sm else -1

    blocked_match = _RE_BLOCKED_COUNT.search(text)
    blocked_count = int(blocked_match.group(1)) if blocked_match else 0
    has_assertion = bool(_RE_ASSERTION.search(text)) or blocked_count > 0

    # Parse top-8 ERROR categories block
    categories: dict[str, int] = {}
    in_top8 = False
    for line in text.splitlines():
        if line.startswith("top 8 ERROR categories:"):
            in_top8 = True
            continue
        if in_top8:
            if not line.strip():
                break
            m = _RE_CATEGORY_LINE.match(line)
            if m:
                categories[m.group(2).strip()] = int(m.group(1))
            elif line.strip() and not line.startswith("top"):
                break

    return StatusSnapshot(
        errors=errors,
        warns=warns,
        categories=categories,
        processed=processed,
        total=total,
        files_total=files_total,
        split_failed=split_failed,
        has_assertion=has_assertion,
    )


def run_decompiler() -> int:
    """Run the jakx_watch decompiler pass. Returns exit code."""
    env = {**os.environ, "JAKX_WATCH_FORCE": "1", "JAKX_WATCH_WAIT": "1"}
    result = subprocess.run(
        ["bash", "scripts/jakx_watch/run.sh"],
        cwd=ROOT,
        env=env,
    )
    return result.returncode


def revert_files(paths: list[Path]) -> None:
    """Git-restore files to HEAD state."""
    if not paths:
        return
    rel_paths = [str(p.relative_to(ROOT)) for p in paths]
    subprocess.run(
        ["git", "checkout", "HEAD", "--"] + rel_paths,
        cwd=ROOT,
        check=True,
    )


def commit_files(paths: list[Path], message: str) -> str:
    """Stage and commit files. Returns the new commit SHA."""
    if not paths:
        return ""
    rel_paths = [str(p.relative_to(ROOT)) for p in paths]
    subprocess.run(["git", "add"] + rel_paths, cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    sha = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT
    ).decode().strip()
    return sha


def run_with_guard(
    edit_fn: Callable[[], list[Path]],
    *,
    label: str,
    err_slack: int = 0,
    warn_slack: int = 0,
    warn_must_decrease: bool = False,
    coverage_drop_tolerance: int = 5,
    split_failed_slack: int = 5,
    allow_assertion: bool = False,
    category_regressions_allowed: dict[str, int] | None = None,
    commit_on_pass: bool = False,
    commit_message: str = "",
) -> GuardResult:
    """Apply edits and gate on decompiler regression.

    Parameters
    ----------
    edit_fn:
        Called with no arguments. Must apply edits to disk and return a list of
        modified file paths (for revert on failure / stage on success).
    label:
        Short label for log messages (used in default commit message too).
    err_slack:
        Allow up to this many new errors without failing. Default 0 (strict).
    warn_slack:
        Allow up to this many new warnings. Default 0.
    warn_must_decrease:
        If True, veto if WARN count did not drop (Δwarn >= 0). Useful for
        WARN-reduction scripts that should only commit real improvements.
    coverage_drop_tolerance:
        Veto if processed-file count drops by more than this. Default 5.
        Catches decompiler crashes that truncate output (fewer files processed
        = fewer errors, making Δerr look positive when it isn't).
    split_failed_slack:
        Veto if split-failed count grows by more than this. Default 5.
    allow_assertion:
        If False (default), veto if status.md contains "Assertion failed" or
        "FATAL crashes" — indicates a C++ crash in the decompiler.
    category_regressions_allowed:
        Dict mapping error category substring → max allowed increase. If a
        category grows beyond its allowance, the gate fails. Default: no
        per-category checks beyond the total err_slack.
    commit_on_pass:
        If True, commit the changed files on a passing gate.
    commit_message:
        Commit message to use when commit_on_pass=True. A minimal default is
        used when empty.
    """
    # Ensure pre-state reflects the current HEAD, not a stale/crashed status.md
    # from an earlier failed batch. Compare status.md's "last updated @ git SHA"
    # header to current HEAD; rescan if they differ or if the current state
    # looks like it was captured mid-crash.
    pre = read_status()
    if _status_is_stale(pre):
        print(f"[guard:{label}] status.md is stale — rescanning before pre-state read")
        run_decompiler()
        pre = read_status()

    if not pre.valid:
        return GuardResult(
            passed=False,
            reason="status.md unreadable before edit — aborting without changes",
        )

    print(f"[guard:{label}] pre-state: errors={pre.errors} warns={pre.warns}")

    # Apply edits
    changed_files = edit_fn()
    edit_count = len(changed_files) if changed_files else 0
    print(f"[guard:{label}] {edit_count} file(s) modified; running decompiler …")

    rc = run_decompiler()
    if rc not in (0, 1):
        print(f"[guard:{label}] decompiler exit {rc} — possible crash", file=sys.stderr)

    post = read_status()
    if not post.valid:
        print(
            f"[guard:{label}] status.md unreadable after run (decompiler crash?) — reverting",
            file=sys.stderr,
        )
        revert_files(changed_files)
        return GuardResult(
            passed=False,
            reason="status.md unreadable after decompiler run",
            edit_count=edit_count,
        )

    delta_err = post.errors - pre.errors
    delta_warn = post.warns - pre.warns
    print(
        f"[guard:{label}] post-state: errors={post.errors} warns={post.warns} "
        f"processed={post.processed}/{post.total} split_failed={post.split_failed} "
        f"(Δerr={delta_err:+d} Δwarn={delta_warn:+d})"
    )

    # --- VETO 1: assertion / crash in output ---
    if not allow_assertion and post.has_assertion:
        print(
            f"[guard:{label}] FAIL — status.md contains 'Assertion failed' / "
            f"'FATAL crashes' — decompiler crashed, reverting",
            file=sys.stderr,
        )
        revert_files(changed_files)
        return GuardResult(
            passed=False,
            reason="decompiler assertion crash in post-state",
            delta_err=delta_err,
            delta_warn=delta_warn,
            edit_count=edit_count,
        )

    # --- VETO 2: coverage drop (processed-file count fell) ---
    if pre.processed >= 0 and post.processed >= 0:
        coverage_drop = pre.processed - post.processed
        if coverage_drop > coverage_drop_tolerance:
            print(
                f"[guard:{label}] FAIL — processed files dropped "
                f"{pre.processed} → {post.processed} "
                f"(drop={coverage_drop}, tolerance={coverage_drop_tolerance}), reverting",
                file=sys.stderr,
            )
            revert_files(changed_files)
            return GuardResult(
                passed=False,
                reason=(
                    f"coverage dropped by {coverage_drop} files "
                    f"(pre={pre.processed} post={post.processed})"
                ),
                delta_err=delta_err,
                delta_warn=delta_warn,
                edit_count=edit_count,
            )

    # --- VETO 3: files_total dropped meaningfully ---
    if pre.files_total >= 0 and post.files_total >= 0:
        files_drop = pre.files_total - post.files_total
        if files_drop > 2:
            print(
                f"[guard:{label}] FAIL — files_total dropped "
                f"{pre.files_total} → {post.files_total} (drop={files_drop}), reverting",
                file=sys.stderr,
            )
            revert_files(changed_files)
            return GuardResult(
                passed=False,
                reason=(
                    f"files_total dropped by {files_drop} "
                    f"(pre={pre.files_total} post={post.files_total})"
                ),
                delta_err=delta_err,
                delta_warn=delta_warn,
                edit_count=edit_count,
            )

    # --- VETO 4: split-failed grew too much ---
    if pre.split_failed >= 0 and post.split_failed >= 0:
        split_grew = post.split_failed - pre.split_failed
        if split_grew > split_failed_slack:
            print(
                f"[guard:{label}] FAIL — split-failed grew "
                f"{pre.split_failed} → {post.split_failed} "
                f"(grew={split_grew}, slack={split_failed_slack}), reverting",
                file=sys.stderr,
            )
            revert_files(changed_files)
            return GuardResult(
                passed=False,
                reason=f"split-failed grew by {split_grew} (pre={pre.split_failed} post={post.split_failed})",
                delta_err=delta_err,
                delta_warn=delta_warn,
                edit_count=edit_count,
            )

    # --- VETO 5: warn must decrease ---
    if warn_must_decrease and delta_warn >= 0:
        print(
            f"[guard:{label}] FAIL — WARNs did not decrease "
            f"(Δwarn={delta_warn:+d}), reverting",
            file=sys.stderr,
        )
        revert_files(changed_files)
        return GuardResult(
            passed=False,
            reason=f"WARNs did not decrease (Δwarn={delta_warn:+d})",
            delta_err=delta_err,
            delta_warn=delta_warn,
            edit_count=edit_count,
        )

    # --- VETO 6: total error delta ---
    if delta_err > err_slack:
        print(
            f"[guard:{label}] FAIL — errors grew by {delta_err} (slack={err_slack}), reverting",
            file=sys.stderr,
        )
        revert_files(changed_files)
        return GuardResult(
            passed=False,
            reason=f"errors grew by {delta_err} (allowed slack: {err_slack})",
            delta_err=delta_err,
            delta_warn=delta_warn,
            edit_count=edit_count,
        )

    # Check per-category regressions
    if category_regressions_allowed:
        for cat_substr, allowance in category_regressions_allowed.items():
            pre_count = next(
                (v for k, v in pre.categories.items() if cat_substr in k), 0
            )
            post_count = next(
                (v for k, v in post.categories.items() if cat_substr in k), 0
            )
            grown = post_count - pre_count
            if grown > allowance:
                print(
                    f"[guard:{label}] FAIL — category '{cat_substr}' grew by {grown} "
                    f"(allowance={allowance}), reverting",
                    file=sys.stderr,
                )
                revert_files(changed_files)
                return GuardResult(
                    passed=False,
                    reason=f"category '{cat_substr}' grew by {grown} (allowed: {allowance})",
                    delta_err=delta_err,
                    delta_warn=delta_warn,
                    edit_count=edit_count,
                )

    # PASS
    sha = ""
    if commit_on_pass and changed_files:
        msg = commit_message or (
            f"fix(jakx): {label} (Δerr {pre.errors}→{post.errors}, "
            f"Δwarn {pre.warns}→{post.warns})\n\n"
            f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
        )
        sha = commit_files(changed_files, msg)
        print(f"[guard:{label}] committed as {sha}")

    return GuardResult(
        passed=True,
        reason="OK",
        delta_err=delta_err,
        delta_warn=delta_warn,
        edit_count=edit_count,
        commit_sha=sha,
    )
