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

GAMES = ("jak1", "jak2", "jak3", "jakx")


def status_md_for(game: str) -> Path:
    """Return the status.md path for a given game.

    jakx → .jakx_watch/status.md (full scanner suite, scripts/jakx_watch/run.sh)
    jak1/2/3 → .<game>_watch/status.md (minimal, scripts/game_watch/run.sh)
    """
    return ROOT / f".{game}_watch" / "status.md"

_RE_ERR_TOTAL = re.compile(r"^inline ERROR markers:\s+(\d+)", re.MULTILINE)
_RE_WARN_TOTAL = re.compile(r"^inline WARN\s+markers:\s+(\d+)", re.MULTILINE)
_RE_REAL_CLEAN = re.compile(r"^\s*real-clean\s*:\s*(\d+)", re.MULTILINE)
_RE_CATEGORY_LINE = re.compile(r"^\s+(\d+)\s+(.+)$")
_RE_DECOMP_PROGRESS = re.compile(
    r"decomp progress:\s*(\d+)/(\d+)\s+processed"
)
_RE_FILES_TOTAL = re.compile(r"^files total:\s+(\d+)", re.MULTILINE)
_RE_SPLIT_FAILED = re.compile(r"^\s+split-failed\s+:\s+(\d+)", re.MULTILINE)
# Crash detection — any of these in status.md means the decomp didn't complete
# normally and the snapshot can't be trusted as a baseline. Cycle 24 leak: the
# only check used to be "Assertion failed", but measure.py emits "C++ ASSERTION
# crash" + "unknown type(s) that crashed decomp:" instead, and run.sh writes
# "# <game>_watch status — FAILED" on zero-files-emitted aborts. None of those
# matched the old regex, so a crashed pre-state passed `valid` and got used as
# the baseline for committed edits (645fa14f3 revert).
#
# Triggers (any one is enough):
#   - "Assertion failed"                       — lowercase C++ assert string
#   - "C++ ASSERTION crash"                    — measure.py crash header
#   - "unknown type(s) that crashed decomp:"   — type-load fatal abort header
#   - "# <game>_watch status — FAILED"         — run.sh zero-files fast path
#   - "(N files blocked by crash;" with N>0    — partial-progress crash
# These do NOT trigger on the "## FATAL crashes" section header alone — that's
# emitted on every clean run by measure.py:304.
_RE_ASSERTION = re.compile(r"Assertion failed", re.MULTILINE)
_RE_CPP_ASSERTION_CRASH = re.compile(r"C\+\+ ASSERTION crash", re.MULTILINE)
_RE_UNKNOWN_TYPE_CRASH = re.compile(
    r"unknown type\(s\) that crashed decomp:", re.MULTILINE
)
_RE_RUNSH_FAILED = re.compile(r"^# \w+_watch status — FAILED", re.MULTILINE)
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
    real_clean: int = -1  # real-clean count (PRIMARY metric per user 2026-04-25)

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


def read_status(game: str = "jakx") -> StatusSnapshot:
    """Parse the game's status.md. Returns invalid snapshot on parse failure."""
    status_md = status_md_for(game)
    if not status_md.exists():
        return StatusSnapshot(-1, -1, {})
    text = status_md.read_text()
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

    rcm = _RE_REAL_CLEAN.search(text)
    real_clean = int(rcm.group(1)) if rcm else -1

    blocked_match = _RE_BLOCKED_COUNT.search(text)
    blocked_count = int(blocked_match.group(1)) if blocked_match else 0
    # `has_assertion` actually means "any decomp-crash signal", not just the
    # literal C++ assert. Kept the field name to avoid churning callers; the
    # detection set is the union of all known crash markers (see regex docs).
    has_assertion = (
        bool(_RE_ASSERTION.search(text))
        or bool(_RE_CPP_ASSERTION_CRASH.search(text))
        or bool(_RE_UNKNOWN_TYPE_CRASH.search(text))
        or bool(_RE_RUNSH_FAILED.search(text))
        or blocked_count > 0
    )

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
        real_clean=real_clean,
    )


def run_decompiler(game: str = "jakx", scope: list[str] | None = None) -> int:
    """Run the game-watch decompiler pass. Returns exit code.

    jakx → scripts/jakx_watch/run.sh (full scanner suite)
    jak1/2/3 → scripts/game_watch/run.sh --game <game> (minimal)

    Parameters
    ----------
    scope:
        If non-None, restrict decomp to this list of object names (basenames
        without _ir2.asm). Sets ALLOWED_OBJECTS env + NO_WIPE so the existing
        IR2 outside the scope is preserved. ~30 sec per ~50 files vs ~10 min
        full. Used by the iterative compounding loop's fast-validation path.
        WARNING: caller must include the clean-file invariant set in scope
        to detect regressions of currently-clean files (see impact_set.py
        union_with_clean()).
    """
    import json as _json
    base_env = {**os.environ}
    if scope is not None:
        # Empty scope is a no-op decomp; caller almost certainly meant
        # something else. Treat as misuse.
        if len(scope) == 0:
            print("[guard] WARN: scope=[] would skip all objects; running full decomp",
                  file=sys.stderr)
            scope = None
    if game == "jakx":
        env_extras = {"JAKX_WATCH_FORCE": "1", "JAKX_WATCH_WAIT": "1"}
        if scope is not None:
            env_extras["JAKX_WATCH_ALLOWED_OBJECTS"] = _json.dumps(sorted(scope))
            env_extras["JAKX_WATCH_NO_WIPE"] = "1"
        env = {**base_env, **env_extras}
        result = subprocess.run(
            ["bash", "scripts/jakx_watch/run.sh"],
            cwd=ROOT,
            env=env,
        )
    else:
        env_extras = {"GAME_WATCH_FORCE": "1", "GAME_WATCH_WAIT": "1"}
        if scope is not None:
            env_extras["GAME_WATCH_ALLOWED_OBJECTS"] = _json.dumps(sorted(scope))
            env_extras["GAME_WATCH_NO_WIPE"] = "1"
        env = {**base_env, **env_extras}
        result = subprocess.run(
            ["bash", "scripts/game_watch/run.sh", "--game", game],
            cwd=ROOT,
            env=env,
        )
    return result.returncode


def revert_files(paths: list[Path], game: str = "jakx",
                 scope: list[str] | None = None) -> None:
    """Git-restore files to HEAD state and refresh status.md to pre-edit state.

    If scope is provided, run a scoped re-decomp (~30 sec) to restore IR2 to
    the pre-edit state and update status.md. If scope is None, fall back to
    the legacy approach: unlink status.md so the next batch triggers a full
    rescan. (Opus cycle 17 finding 2026-04-26 — without invalidation the
    next batch reads a stale pre-state from the now-reverted working tree.)

    Scoped path is required for bisect-on-revert: every revert in the
    bisect tree would otherwise trigger a 10-min full decomp.
    """
    if not paths:
        return
    rel_paths = [str(p.relative_to(ROOT)) for p in paths]
    subprocess.run(
        ["git", "checkout", "HEAD", "--"] + rel_paths,
        cwd=ROOT,
        check=True,
    )
    if scope is not None and len(scope) > 0:
        # Scoped re-decomp: refreshes the IR2 of the same files we edited,
        # so status.md again reflects pre-edit state. Cheap (~30s).
        run_decompiler(game, scope=scope)
    else:
        status_md = status_md_for(game)
        if status_md.exists():
            status_md.unlink()


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
    game: str = "jakx",
    scope: list[str] | None = None,
    edited_types: set[str] | None = None,
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
    scope:
        If non-None, restrict the post-edit decomp to this list of object
        basenames. ~20× faster than full decomp; required for high-iteration
        compounding loops. Caller MUST union the impact set with the clean-
        file invariant (see impact_set.union_with_clean()) so any regression
        of a currently-clean file still gets caught. The pre-state read is
        always from the existing status.md (which reflects the prior full or
        scoped run); the post-state is read after the scoped re-decomp + a
        full-tree measure pass that recomputes totals from disk.
    edited_types:
        If provided AND scope is None, auto-compute scope from these types
        via impact_set.compute_impact_set() ∪ clean-file invariant. Only
        activates when env COMPOUND_LOOP_SCOPED=1 (otherwise falls back to
        full decomp — gives the iterative loop opt-in control without
        forcing fast-mode on every caller).
    """
    # Ensure pre-state reflects the current HEAD, not a stale/crashed status.md
    # from an earlier failed batch. Compare status.md's "last updated @ git SHA"
    # header to current HEAD; rescan if they differ or if the current state
    # looks like it was captured mid-crash.
    if game not in GAMES:
        return GuardResult(
            passed=False,
            reason=f"unknown game '{game}' — must be one of {GAMES}",
        )

    # Auto-compute scope from edited_types if loop has opted into fast mode.
    # COMPOUND_LOOP_SCOPED=1 is the master switch; without it, all callers
    # behave identically to the pre-fast-validation era (full decomp).
    if scope is None and edited_types and os.environ.get("COMPOUND_LOOP_SCOPED") == "1":
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from impact_set import compute_impact_set, union_with_clean
            impact = compute_impact_set(edited_types, game)
            scope = sorted(union_with_clean(impact, game))
            print(f"[guard:{label}] auto-scope: {len(impact)} impacted "
                  f"+ clean-union → {len(scope)} objects "
                  f"({len(edited_types)} types: {sorted(list(edited_types))[:5]}…)")
        except Exception as e:
            print(f"[guard:{label}] auto-scope failed ({e}); falling back to full decomp",
                  file=sys.stderr)
            scope = None

    pre = read_status(game)
    if _status_is_stale(pre):
        # Pre-rescan must always be FULL (not scoped) — a stale baseline
        # off a partial decomp can't be trusted as a reference point. After
        # this we have a clean global pre-state; subsequent in-batch decomp
        # may be scoped.
        print(f"[guard:{label}] status.md is stale — full rescan before pre-state read")
        run_decompiler(game, scope=None)
        pre = read_status(game)

    if not pre.valid:
        return GuardResult(
            passed=False,
            reason="status.md unreadable before edit — aborting without changes",
        )

    # Cycle 24 fix: even after a rescan, if the pre-state still shows a fatal
    # crash, the baseline is meaningless — applying edits on top of it would
    # commit against a poisoned baseline. Refuse to proceed; the crash is
    # almost certainly an uncommitted-WIP issue the caller needs to resolve.
    if pre.has_assertion:
        return GuardResult(
            passed=False,
            reason=(
                "pre-state shows decomp crash (FATAL crashes / unknown type / "
                "C++ ASSERTION / blocked files) — refusing to commit against a "
                "broken baseline. Likely uncommitted WIP breaking decomp; "
                "stash or revert and retry."
            ),
        )

    print(f"[guard:{label}] pre-state: errors={pre.errors} warns={pre.warns}")

    # Apply edits
    changed_files = edit_fn()
    edit_count = len(changed_files) if changed_files else 0
    scope_descr = f"scoped to {len(scope)} objects" if scope is not None else "full"
    print(f"[guard:{label}] {edit_count} file(s) modified; running decompiler ({scope_descr}) …")

    rc = run_decompiler(game, scope=scope)
    if rc not in (0, 1):
        print(f"[guard:{label}] decompiler exit {rc} — possible crash", file=sys.stderr)

    post = read_status(game)
    if not post.valid:
        print(
            f"[guard:{label}] status.md unreadable after run (decompiler crash?) — reverting",
            file=sys.stderr,
        )
        revert_files(changed_files, game, scope=scope)
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
        revert_files(changed_files, game, scope=scope)
        return GuardResult(
            passed=False,
            reason="decompiler assertion crash in post-state",
            delta_err=delta_err,
            delta_warn=delta_warn,
            edit_count=edit_count,
        )

    # --- VETO 2: coverage drop (processed-file count fell) ---
    # Skip for scoped runs: 'processed' comes from the decompiler log, which
    # for a scoped run records only the N scoped objects (not the full ~600).
    # Pre-state is from the prior full decomp so the drop is structural, not
    # a regression. files_total / real-clean cover the regression case.
    if scope is None and pre.processed >= 0 and post.processed >= 0:
        coverage_drop = pre.processed - post.processed
        if coverage_drop > coverage_drop_tolerance:
            print(
                f"[guard:{label}] FAIL — processed files dropped "
                f"{pre.processed} → {post.processed} "
                f"(drop={coverage_drop}, tolerance={coverage_drop_tolerance}), reverting",
                file=sys.stderr,
            )
            revert_files(changed_files, game, scope=scope)
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
            revert_files(changed_files, game, scope=scope)
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
            revert_files(changed_files, game, scope=scope)
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
        revert_files(changed_files, game, scope=scope)
        return GuardResult(
            passed=False,
            reason=f"WARNs did not decrease (Δwarn={delta_warn:+d})",
            delta_err=delta_err,
            delta_warn=delta_warn,
            edit_count=edit_count,
        )

    # --- VETO 6a: real-clean DECREASED (PRIMARY metric, per user 2026-04-25)
    # If rc went down, ALWAYS revert regardless of err delta. We lost a known-good file.
    delta_rc = (post.real_clean - pre.real_clean) if (pre.real_clean >= 0 and post.real_clean >= 0) else 0
    if delta_rc < 0:
        print(
            f"[guard:{label}] FAIL — real-clean dropped by {-delta_rc} ({pre.real_clean}→{post.real_clean}), reverting",
            file=sys.stderr,
        )
        revert_files(changed_files, game, scope=scope)
        return GuardResult(
            passed=False,
            reason=f"real-clean dropped by {-delta_rc} ({pre.real_clean}→{post.real_clean})",
            delta_err=delta_err,
            delta_warn=delta_warn,
            edit_count=edit_count,
        )

    # --- VETO 6b: error delta exceeds noise-floor for unlocked content
    # User rule (2026-04-25): err can grow when files unlock (newly-visible errors).
    # Noise floor: ~13.5 errors per newly-unlocked file. So allow err growth if it
    # stays below (rc_growth × 13.5) plus the explicit err_slack.
    # If rc grew → err growth is expected; only veto if it FAR exceeds noise floor.
    # If rc unchanged or err_slack is exceeded with no rc growth → veto.
    noise_floor = max(0, delta_rc * 14)  # 14 ≈ 13.5 rounded up, conservative
    effective_slack = err_slack + noise_floor
    if delta_err > effective_slack:
        print(
            f"[guard:{label}] FAIL — errors grew by {delta_err} (slack={err_slack} + noise-floor={noise_floor} for rc+{delta_rc}), reverting",
            file=sys.stderr,
        )
        revert_files(changed_files, game, scope=scope)
        return GuardResult(
            passed=False,
            reason=f"errors grew by {delta_err} (effective slack: {effective_slack}, rc delta: {delta_rc:+d})",
            delta_err=delta_err,
            delta_warn=delta_warn,
            edit_count=edit_count,
        )

    # If rc grew, log positively even if err nudged up
    if delta_rc > 0:
        print(
            f"[guard:{label}] rc+{delta_rc} ({pre.real_clean}→{post.real_clean}) — err Δ {delta_err:+d} within noise floor",
            file=sys.stderr,
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
                revert_files(changed_files, game, scope=scope)
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

        # Log convergence snapshot AFTER commit (sha is captured in row).
        # This gives inter-applier signal "for free" — every commit's row
        # in convergence.jsonl shows which metrics moved. If a return-mismatch
        # commit drops failed_type_prop_errors, that's compound signal across
        # patterns. If only return_mismatch_warns moves, the lanes are
        # independent. Without this, "are we compounding" was unanswerable.
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from convergence_metric import compute, append_log
            snap = compute(game)
            snap["label"] = label  # which applier produced this commit
            append_log(snap)
        except Exception as e:
            print(f"[guard:{label}] convergence_metric snapshot failed: {e}",
                  file=sys.stderr)

    return GuardResult(
        passed=True,
        reason="OK",
        delta_err=delta_err,
        delta_warn=delta_warn,
        edit_count=edit_count,
        commit_sha=sha,
    )


# ---- Bisect-on-revert -------------------------------------------------

def bisect_apply(
    fixes: list,
    file: Path,
    *,
    apply_fn: Callable[[list], None],
    label: str,
    game: str = "jakx",
    extract_blacklist_key: Callable[[object], tuple[str, str, str] | None] | None = None,
    extract_edited_types: Callable[[list], set[str]] | None = None,
    commit_on_pass: bool = False,
    commit_message_template: str = "",
    max_depth: int = 10,
    _depth: int = 0,
    **guard_kwargs,
) -> tuple[list, list]:
    """Apply a list of fixes with bisect-on-revert.

    If applying all fixes passes the guard: commit them, done.
    If they get reverted: split in halves, recurse on each. A single fix that
    fails gets recorded in the blacklist (via extract_blacklist_key) so the
    next iteration's planner skips it.

    Returns (kept_fixes, blacklisted_fixes). 'kept' = subsets that committed
    successfully across the recursion; 'blacklisted' = single fixes that
    individually failed.

    Cost: O(log N) decomp passes if all fixes are good, O(N) if all bad,
    O(N + log N · k) typical where k = good fix count. With scoped decomp
    (~30 sec) this is feasible up to N≈100; without scoping, prefer
    bisect only on small batches.

    Parameters
    ----------
    fixes:
        Opaque list of items the apply_fn understands.
    file:
        The single file modified by apply_fn (e.g. all-types.gc). Reverted
        via git checkout HEAD on guard failure.
    apply_fn:
        Function that applies a subset of fixes to the file. Idempotent in
        the sense that callers must support being invoked with any subset.
    label:
        Short string used in log messages and recursion path tags.
    extract_blacklist_key:
        If provided, called with a single fix (when isolated as bad) to
        extract (type, method, pattern) for the blacklist. Return None to
        skip blacklisting that fix (e.g., format unparseable).
    extract_edited_types:
        If provided, called with a fix subset to extract the set of type
        names being edited. Used by apply_guard to compute scoped decomp
        (only effective when COMPOUND_LOOP_SCOPED=1 in env).
    commit_on_pass:
        If True, commit each passing subset (one commit per recursive level
        that passes wholesale). False = applied but not committed (caller
        commits at the end).
    commit_message_template:
        f-string-style template; gets formatted with {n} (subset size) and
        {label} (current recursion path).
    max_depth:
        Recursion safety bound. Default 10 → handles up to 1024 fixes.
    """
    if not fixes:
        return [], []
    if _depth > max_depth:
        print(f"[bisect:{label}] WARN: max_depth {max_depth} reached "
              f"with {len(fixes)} fixes — giving up on this subtree",
              file=sys.stderr)
        return [], []

    edited_types = None
    if extract_edited_types:
        try:
            edited_types = extract_edited_types(fixes)
        except Exception as e:
            print(f"[bisect:{label}] extract_edited_types failed: {e}",
                  file=sys.stderr)

    def edit_fn():
        apply_fn(fixes)
        return [file]

    msg = ""
    if commit_on_pass:
        if commit_message_template:
            msg = commit_message_template.format(n=len(fixes), label=label)
        else:
            msg = (f"fix({game}): {label} bisect-pass ({len(fixes)} fixes)\n\n"
                   f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>\n")

    result = run_with_guard(
        edit_fn,
        label=f"{label}@{len(fixes)}",
        game=game,
        commit_on_pass=commit_on_pass,
        commit_message=msg,
        edited_types=edited_types,
        **guard_kwargs,
    )

    if result.passed:
        print(f"[bisect:{label}] PASS at size {len(fixes)} (depth={_depth})")
        return list(fixes), []

    # Failed. If singleton, blacklist it.
    if len(fixes) == 1:
        blacklisted = list(fixes)
        if extract_blacklist_key:
            try:
                key = extract_blacklist_key(fixes[0])
                if key is not None:
                    type_name, method, pattern = key
                    # Lazy import to avoid circular dep at module load
                    sys.path.insert(0, str(Path(__file__).parent))
                    import blacklist as _bl  # noqa
                    _bl.add(game, type_name, method, pattern,
                            reason=result.reason)
                    print(f"[bisect:{label}] BLACKLISTED "
                          f"{type_name}::{method} {pattern} ({result.reason})")
            except Exception as e:
                print(f"[bisect:{label}] blacklist add failed: {e}",
                      file=sys.stderr)
        return [], blacklisted

    # Bisect: split halves, recurse.
    mid = len(fixes) // 2
    left = fixes[:mid]
    right = fixes[mid:]
    print(f"[bisect:{label}] split {len(fixes)} → {len(left)} + {len(right)} "
          f"(depth={_depth})")

    left_kept, left_bl = bisect_apply(
        left, file,
        apply_fn=apply_fn, label=f"{label}.L", game=game,
        extract_blacklist_key=extract_blacklist_key,
        extract_edited_types=extract_edited_types,
        commit_on_pass=commit_on_pass,
        commit_message_template=commit_message_template,
        max_depth=max_depth, _depth=_depth + 1,
        **guard_kwargs,
    )
    right_kept, right_bl = bisect_apply(
        right, file,
        apply_fn=apply_fn, label=f"{label}.R", game=game,
        extract_blacklist_key=extract_blacklist_key,
        extract_edited_types=extract_edited_types,
        commit_on_pass=commit_on_pass,
        commit_message_template=commit_message_template,
        max_depth=max_depth, _depth=_depth + 1,
        **guard_kwargs,
    )
    return (left_kept + right_kept), (left_bl + right_bl)
