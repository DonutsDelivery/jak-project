#!/usr/bin/env python3
"""V6 GUARDED apply — per-batch decomp gate + surgical per-file revert.

Synthesized from user guidance:
  - apply_guard.py: status.md pre/post snapshot signal infrastructure
  - v3 bisect: per-file delta analysis -> only revert commits touching files
    that regressed (preserves winners in mixed batch)

Per-batch flow:
  1. Pre-batch: take snapshot via measure.py (per_file errors, categories).
  2. Apply N candidates as N separate commits, FRESH classify each (so post-
     prior-batch line indices are accurate; fixes the v6_broad_apply line-drift
     bug where stale plan indices caused method_add to write into wrong type).
  3. Run decomp under flock /tmp/jakx-decomp.lock.
  4. Post-batch: take snapshot.
  5. Compare per_file: any file with post.errors > pre.errors → REGRESSED.
     Any commit whose jakx_file is in regressed set → REVERT.
     Commits whose jakx_file is unchanged or improved → KEEP.
     This is surgical — preserves winners in mixed batch.
  6. Adapt batch size: 4 consecutive passes (no reverts) → double; any reverts
     in batch → halve. Floor=4, ceiling=128.

Stops:
  - candidate pool exhausted
  - --max-batches reached
  - 5 consecutive batches with all reverted (catastrophic poisoning)
  - status.md unparseable post-decomp (decompiler crash) → revert whole batch
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "jakx_watch"))

from multigame_v6_broad_apply import (
    index_all_types,
    classify_candidate,
    apply_plan,
    load_jsonc,
    write_jsonc_preserving_format,
    ALL_TYPES,
    TYPE_CASTS,
    STACK_STRUCTS,
    JSON_INPUT,
)

DECOMP_BIN = ROOT / "build" / "Release" / "decompiler" / "decompiler.real"
DECOMP_BIN_WRAPPER = ROOT / "build" / "Release" / "decompiler" / "decompiler"
DECOMP_CONFIG = ROOT / "decompiler" / "config" / "jakx" / "jakx_config.jsonc"
DECOMP_OUT = ROOT / "decompiler_out"
ISO_DATA = ROOT / "iso_data"
HISTORY_DIR = ROOT / ".jakx_watch" / "history"
LOCK = "/tmp/jakx-decomp.lock"


def run_git(args, check=True):
    r = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.stderr.write(f"git {args} FAILED: {r.stderr}\n")
        raise RuntimeError(r.stderr)
    return r


def head_sha() -> str:
    return run_git(["rev-parse", "HEAD"]).stdout.strip()


def short_sha(sha: str) -> str:
    return sha[:9]


def take_snapshot(label: str) -> dict:
    """Run measure.py to write snapshot, return loaded dict."""
    print(f"  [snapshot:{label}] measuring …", file=sys.stderr)
    r = subprocess.run(
        ["python3", "scripts/jakx_watch/measure.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        sys.stderr.write(f"  measure.py failed: {r.stderr}\n")
    # Find the most recent snap-*.json
    snaps = sorted(HISTORY_DIR.glob("snap-*.json"), key=lambda p: p.stat().st_mtime)
    if not snaps:
        return {"per_file": {}}
    return json.loads(snaps[-1].read_text())


def run_decomp() -> tuple[bool, str]:
    """Run decomp under flock. Returns (ok, log_path)."""
    log_path = f"/tmp/decomp-v6g-{int(time.time())}.log"
    # Clear output dir for fresh measurement
    if (DECOMP_OUT / "jakx").exists():
        for p in (DECOMP_OUT / "jakx").glob("*"):
            if p.is_file():
                p.unlink()
    # Use the wrapper if present (it adds flock automatically), else flock manually.
    if DECOMP_BIN_WRAPPER.exists() and DECOMP_BIN.exists() and DECOMP_BIN_WRAPPER.read_bytes()[:4] != b"\x7fELF":
        cmd = [str(DECOMP_BIN_WRAPPER), str(DECOMP_CONFIG), str(ISO_DATA),
               str(DECOMP_OUT), "--version", "ntsc_v1"]
    else:
        cmd = ["flock", LOCK, str(DECOMP_BIN), str(DECOMP_CONFIG), str(ISO_DATA),
               str(DECOMP_OUT), "--version", "ntsc_v1"]
    with open(log_path, "w") as fp:
        r = subprocess.run(cmd, cwd=ROOT, stdout=fp, stderr=subprocess.STDOUT,
                           timeout=600)
    return (r.returncode == 0, log_path)


def per_file_deltas(pre: dict, post: dict) -> dict:
    """Return {file: {pre_err, post_err, delta, regressed: bool, newly_real_clean, ...}}."""
    pre_pf = pre.get("per_file", {})
    post_pf = post.get("per_file", {})
    out = {}
    for f in set(pre_pf) | set(post_pf):
        b = pre_pf.get(f, {})
        p = post_pf.get(f, {})
        be = b.get("error", 0) if b else None
        pe = p.get("error", 0) if p else None
        delta = (pe or 0) - (be or 0) if be is not None and pe is not None else 0
        out[f] = {
            "pre_err": be,
            "post_err": pe,
            "delta": delta,
            "pre_cat": b.get("category"),
            "post_cat": p.get("category"),
            "regressed": be is not None and pe is not None and pe > be,
            "newly_real_clean": (b.get("category") != "real-clean"
                                 and p.get("category") == "real-clean"),
            "lost_real_clean": (b.get("category") == "real-clean"
                                and p.get("category") != "real-clean"),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(JSON_INPUT))
    ap.add_argument("--cycle-tag", default="V6")
    ap.add_argument("--blacklist-json", default="")
    ap.add_argument("--extra-blacklist-json", action="append", default=[])
    ap.add_argument("--no-skip-zero-error", action="store_true")
    ap.add_argument("--no-skip-curated", action="store_true")
    ap.add_argument("--no-method-add", action="store_true")
    ap.add_argument("--no-extern-add", action="store_true")
    ap.add_argument("--method-add-max-gap", type=int, default=4)
    ap.add_argument("--initial-batch-size", type=int, default=50)
    ap.add_argument("--max-batch-size", type=int, default=128)
    ap.add_argument("--min-batch-size", type=int, default=4)
    ap.add_argument("--max-batches", type=int, default=20)
    ap.add_argument("--err-slack-frac", type=float, default=0.0,
                    help="Frac of pre.total_err allowed to grow before "
                         "treating whole batch as catastrophic (default 0).")
    args = ap.parse_args()

    research_dir = ROOT / ".jakx_watch" / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    log_path = research_dir / f"{args.cycle_tag}_GUARDED_LOG.md"
    state_path = research_dir / f"{args.cycle_tag}_GUARDED_STATE.json"

    # Load candidate pool
    print(f"[{args.cycle_tag}] loading {args.input}", file=sys.stderr)
    data = json.loads(Path(args.input).read_text())
    matches = [m for m in data.get("matches", []) if m.get("candidate_patch")]
    print(f"[{args.cycle_tag}] {len(matches)} matches with patches", file=sys.stderr)

    # Type blacklist (cumulative)
    banned_types: set[str] = set()
    bl_paths = []
    if args.blacklist_json and Path(args.blacklist_json).exists():
        bl_paths.append(args.blacklist_json)
    for p in args.extra_blacklist_json:
        if Path(p).exists():
            bl_paths.append(p)
    for p in bl_paths:
        bl = json.loads(Path(p).read_text())
        banned_types |= set(bl.get("banned_types", []))
    print(f"[{args.cycle_tag}] banned types ({len(banned_types)}): {sorted(banned_types)}",
          file=sys.stderr)

    base_ctx = {
        "banned_types": banned_types,
        "skip_zero_error_files": not args.no_skip_zero_error,
        "skip_curated_slots": not args.no_skip_curated,
        "enable_extern_add": not args.no_extern_add,
        "enable_method_add": not args.no_method_add,
        "method_add_max_gap": args.method_add_max_gap,
    }

    # ---- Take initial snapshot ----
    pre = take_snapshot("initial")
    initial_err = sum(v.get("error", 0) for v in pre.get("per_file", {}).values())
    initial_rc = sum(1 for v in pre.get("per_file", {}).values()
                     if v.get("category") == "real-clean")
    print(f"[{args.cycle_tag}] initial: files={len(pre.get('per_file', {}))} "
          f"err={initial_err} real-clean={initial_rc}", file=sys.stderr)

    log_lines = [f"# {args.cycle_tag} guarded apply log\n",
                 f"- pool size: {len(matches)}\n",
                 f"- initial: err={initial_err} rc={initial_rc}\n",
                 f"- initial batch size: {args.initial_batch_size}\n\n",
                 f"## Per-batch log\n"]

    # ---- Outer batch loop ----
    pool_idx = 0
    batch_size = args.initial_batch_size
    batches_run = 0
    consecutive_total_failures = 0
    cum_applied = 0
    cum_reverted = 0
    cum_kept = 0
    cum_skipped = 0
    cycle_state = {
        "input": args.input,
        "cycle_tag": args.cycle_tag,
        "initial_err": initial_err,
        "initial_rc": initial_rc,
        "batches": [],
        "matcher_failures": [],
    }

    while pool_idx < len(matches) and batches_run < args.max_batches:
        # Update file_errors ctx from current decomp output
        jakx_file_errors: dict[str, int] = {}
        for f in pre.get("per_file", {}).items():
            pass
        for fname, info in pre.get("per_file", {}).items():
            jakx_file_errors[fname] = info.get("error", 0)
        ctx = {**base_ctx, "jakx_file_errors": jakx_file_errors}

        slice_start = pool_idx
        slice_end = min(pool_idx + batch_size, len(matches))
        batch_candidates = matches[slice_start:slice_end]

        # Apply each candidate as its own commit
        all_types_text = ALL_TYPES.read_text(encoding="utf-8")
        type_casts = load_jsonc(TYPE_CASTS) if TYPE_CASTS.exists() else {}
        stack_structs = load_jsonc(STACK_STRUCTS) if STACK_STRUCTS.exists() else {}
        types_idx = index_all_types(all_types_text)

        applied_commits: list[dict] = []  # one per candidate that committed
        skipped: list[dict] = []

        head_pre_batch = head_sha()

        for cand in batch_candidates:
            decision = classify_candidate(cand, types_idx, ctx=ctx)
            if decision["action"] != "apply":
                skipped.append({"jakx_fn": cand["jakx_fn"],
                                "jakx_file": cand["jakx_file"],
                                "reason": decision["reason"]})
                continue
            plan = decision["plan"]
            new_at, new_tc, new_ss, info = apply_plan(
                plan, all_types_text, type_casts, stack_structs, types_idx,
            )
            if new_at is None:
                skipped.append({"jakx_fn": cand["jakx_fn"],
                                "jakx_file": cand["jakx_file"],
                                "reason": f"apply-fail:{info}"})
                continue
            # Write to disk
            ALL_TYPES.write_text(new_at)
            if new_tc != type_casts:
                write_jsonc_preserving_format(TYPE_CASTS, new_tc)
            if new_ss != stack_structs:
                write_jsonc_preserving_format(STACK_STRUCTS, new_ss)
            # Commit
            run_git(["add",
                     "decompiler/config/jakx/all-types.gc",
                     "decompiler/config/jakx/ntsc_v1/type_casts.jsonc",
                     "decompiler/config/jakx/ntsc_v1/stack_structures.jsonc"])
            msg = (f"cand: {plan['jakx_fn']} @ {plan['jakx_file']} "
                   f"<- {plan['src_corpus']} ({plan['tier']})\n\n"
                   f"v6-guarded batch {batches_run+1}\nactions: {info}\n")
            r = subprocess.run(
                ["git", "commit", "-m", msg, "--allow-empty"],
                cwd=ROOT, capture_output=True, text=True,
            )
            if r.returncode != 0:
                skipped.append({"jakx_fn": cand["jakx_fn"],
                                "jakx_file": cand["jakx_file"],
                                "reason": f"commit-fail:{r.stderr[:80]}"})
                # Roll back working tree to HEAD to recover
                run_git(["checkout", "HEAD", "--",
                         "decompiler/config/jakx/all-types.gc",
                         "decompiler/config/jakx/ntsc_v1/type_casts.jsonc",
                         "decompiler/config/jakx/ntsc_v1/stack_structures.jsonc"], check=False)
                # Re-load disk state
                all_types_text = ALL_TYPES.read_text(encoding="utf-8")
                type_casts = load_jsonc(TYPE_CASTS) if TYPE_CASTS.exists() else {}
                stack_structs = load_jsonc(STACK_STRUCTS) if STACK_STRUCTS.exists() else {}
                types_idx = index_all_types(all_types_text)
                continue
            sha = head_sha()
            applied_commits.append({
                "sha": sha,
                "jakx_fn": plan["jakx_fn"],
                "jakx_file": plan["jakx_file"],
                "src_corpus": plan["src_corpus"],
                "tier": plan["tier"],
                "info": info,
            })
            # Update in-memory state for next iter
            all_types_text = new_at
            type_casts = new_tc
            stack_structs = new_ss
            types_idx = index_all_types(all_types_text)

        cum_skipped += len(skipped)
        batches_run += 1

        if not applied_commits:
            # Whole slice rejected during classify/apply
            log_lines.append(
                f"- batch {batches_run} N={batch_size} pool[{slice_start}:{slice_end}]: "
                f"applied=0 skipped={len(skipped)} (no commits)\n"
            )
            print(f"[{args.cycle_tag}] batch {batches_run}: 0 applied "
                  f"(skipped {len(skipped)})", file=sys.stderr)
            cycle_state["batches"].append({
                "batch": batches_run, "n": batch_size, "applied": 0,
                "skipped": skipped, "reverted": [], "kept": [],
                "delta_err": 0, "decomp_ok": True,
            })
            pool_idx = slice_end
            continue

        # ---- Decomp ----
        print(f"[{args.cycle_tag}] batch {batches_run} N={batch_size}: "
              f"{len(applied_commits)} commits applied — running decomp …",
              file=sys.stderr)
        decomp_ok, dlog = run_decomp()
        if not decomp_ok:
            # Catastrophic — decompiler exited non-zero. Read last N log lines
            # to find the issue, revert ALL commits in this batch.
            tail = ""
            try:
                tail = Path(dlog).read_text()[-1500:]
            except Exception:
                pass
            print(f"[{args.cycle_tag}] decompiler exit != 0 — reverting {len(applied_commits)} commits",
                  file=sys.stderr)
            print(f"  last log: {tail[-500:]}", file=sys.stderr)
            # Revert in REVERSE order
            for c in reversed(applied_commits):
                subprocess.run(["git", "revert", "--no-edit", c["sha"]],
                               cwd=ROOT, capture_output=True)
            cum_reverted += len(applied_commits)
            consecutive_total_failures += 1
            log_lines.append(
                f"- batch {batches_run} N={batch_size} CATASTROPHIC: decomp crashed, "
                f"reverted all {len(applied_commits)} commits. log tail: {tail[-200:]!r}\n"
            )
            cycle_state["batches"].append({
                "batch": batches_run, "n": batch_size,
                "applied": len(applied_commits),
                "skipped": skipped,
                "reverted": [c["sha"] for c in applied_commits],
                "kept": [],
                "delta_err": None,
                "decomp_ok": False,
                "log_tail": tail[-500:],
            })
            cycle_state["matcher_failures"].append({
                "batch": batches_run, "kind": "catastrophic_decomp_crash",
                "candidates": applied_commits,
            })
            # Halve batch size
            batch_size = max(args.min_batch_size, batch_size // 2)
            if consecutive_total_failures >= 3:
                print(f"[{args.cycle_tag}] 3 consecutive catastrophic — STOP",
                      file=sys.stderr)
                break
            pool_idx = slice_end
            continue

        consecutive_total_failures = 0

        # ---- Snapshot post ----
        post = take_snapshot(f"batch{batches_run}")
        deltas = per_file_deltas(pre, post)

        # ---- Identify regressed files ----
        regressed_files = {f: d for f, d in deltas.items() if d.get("regressed")}
        lost_rc_files = {f: d for f, d in deltas.items() if d.get("lost_real_clean")}
        # ---- Identify commits to revert ----
        # Commit revert criterion: commit's jakx_file is in regressed_files OR lost_rc_files.
        revert_files_set = set(regressed_files) | set(lost_rc_files)
        to_revert: list[dict] = [c for c in applied_commits
                                  if c["jakx_file"] in revert_files_set]
        to_keep: list[dict] = [c for c in applied_commits
                               if c["jakx_file"] not in revert_files_set]

        # Compute delta totals
        total_pre = sum(v.get("error", 0) for v in pre.get("per_file", {}).values())
        total_post = sum(v.get("error", 0) for v in post.get("per_file", {}).values())
        delta_err = total_post - total_pre

        # ---- Surgical revert ----
        revert_shas: list[str] = []
        if to_revert:
            print(f"[{args.cycle_tag}] surgical revert: {len(to_revert)} of {len(applied_commits)} "
                  f"({len(regressed_files)} regressed files, {len(lost_rc_files)} lost-rc)",
                  file=sys.stderr)
            # Revert in reverse-chronological order
            for c in sorted(to_revert, key=lambda x: -applied_commits.index(x)):
                r = subprocess.run(["git", "revert", "--no-edit", c["sha"]],
                                   cwd=ROOT, capture_output=True, text=True)
                if r.returncode != 0:
                    print(f"  revert {c['sha'][:9]} failed: {r.stderr[:150]}", file=sys.stderr)
                    subprocess.run(["git", "revert", "--abort"], cwd=ROOT, capture_output=True)
                else:
                    revert_shas.append(c["sha"])
            # Re-run decomp + snapshot to update post for next batch baseline
            decomp_ok2, _ = run_decomp()
            if decomp_ok2:
                post = take_snapshot(f"batch{batches_run}-post-revert")

        cum_applied += len(applied_commits)
        cum_reverted += len(revert_shas)
        cum_kept += len(to_keep)

        # ---- Adapt batch size ----
        revert_rate = len(to_revert) / max(1, len(applied_commits))
        if revert_rate == 0 and batches_run >= 2:
            # Pure pass — grow
            new_size = min(args.max_batch_size, batch_size * 2)
            if new_size != batch_size:
                print(f"[{args.cycle_tag}] -> batch size {batch_size} -> {new_size}",
                      file=sys.stderr)
            batch_size = new_size
        elif revert_rate > 0.5:
            new_size = max(args.min_batch_size, batch_size // 2)
            if new_size != batch_size:
                print(f"[{args.cycle_tag}] -> batch size {batch_size} -> {new_size} (high revert)",
                      file=sys.stderr)
            batch_size = new_size

        log_lines.append(
            f"- batch {batches_run} N={batch_size} pool[{slice_start}:{slice_end}]: "
            f"applied={len(applied_commits)} kept={len(to_keep)} "
            f"reverted={len(revert_shas)} skipped={len(skipped)} "
            f"Δerr={delta_err:+d} regressed_files={len(regressed_files)} "
            f"newly_rc={sum(1 for d in deltas.values() if d['newly_real_clean'])}\n"
        )
        print(f"[{args.cycle_tag}] batch {batches_run}: kept={len(to_keep)} "
              f"reverted={len(revert_shas)} Δerr={delta_err:+d}",
              file=sys.stderr)

        cycle_state["batches"].append({
            "batch": batches_run, "n": batch_size,
            "applied": len(applied_commits),
            "skipped": skipped,
            "reverted": revert_shas,
            "kept": [{"sha": c["sha"], "jakx_fn": c["jakx_fn"], "jakx_file": c["jakx_file"]}
                     for c in to_keep],
            "delta_err": delta_err,
            "decomp_ok": True,
            "regressed_files": list(regressed_files.keys()),
            "lost_real_clean_files": list(lost_rc_files.keys()),
            "newly_real_clean": [f for f, d in deltas.items() if d["newly_real_clean"]],
        })

        if to_revert:
            cycle_state["matcher_failures"].append({
                "batch": batches_run, "kind": "per_file_revert",
                "reverted": [{"sha": c["sha"], "jakx_fn": c["jakx_fn"],
                              "jakx_file": c["jakx_file"], "tier": c["tier"],
                              "src_corpus": c["src_corpus"]} for c in to_revert],
                "regressed_files": list(regressed_files.keys()),
            })

        # New baseline for next batch
        pre = post
        pool_idx = slice_end

    # ---- Final report ----
    final_pf = pre.get("per_file", {})
    final_err = sum(v.get("error", 0) for v in final_pf.values())
    final_rc = sum(1 for v in final_pf.values() if v.get("category") == "real-clean")

    log_lines.append("\n## Cycle summary\n")
    log_lines.append(f"- batches run: {batches_run}\n")
    log_lines.append(f"- candidates committed (kept): {cum_kept}\n")
    log_lines.append(f"- candidates reverted: {cum_reverted}\n")
    log_lines.append(f"- candidates skipped pre-apply: {cum_skipped}\n")
    log_lines.append(f"- final batch size: {batch_size}\n")
    log_lines.append(f"- error delta: {initial_err} -> {final_err} ({final_err - initial_err:+d})\n")
    log_lines.append(f"- real-clean delta: {initial_rc} -> {final_rc} ({final_rc - initial_rc:+d})\n")
    log_path.write_text("".join(log_lines))

    cycle_state["summary"] = {
        "batches_run": batches_run,
        "kept": cum_kept,
        "reverted": cum_reverted,
        "skipped": cum_skipped,
        "final_batch_size": batch_size,
        "final_err": final_err,
        "final_rc": final_rc,
        "delta_err_total": final_err - initial_err,
        "delta_rc_total": final_rc - initial_rc,
    }
    state_path.write_text(json.dumps(cycle_state, indent=2, default=str))
    print(f"\n[{args.cycle_tag}] DONE: batches={batches_run} kept={cum_kept} "
          f"reverted={cum_reverted} Δerr={final_err - initial_err:+d} "
          f"Δrc={final_rc - initial_rc:+d}", file=sys.stderr)
    print(f"  log -> {log_path}\n  state -> {state_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
