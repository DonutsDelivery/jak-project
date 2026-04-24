#!/usr/bin/env python3
"""Empirically rank git commits by their decomp metric impact.

For each consecutive pair of snapshots (ordered by timestamp), compute metric
deltas and attribute them to the commit SHA from the newer snapshot. Classify
each commit as WINNER (reduces errors significantly), LOSER (increases errors),
or NEUTRAL.

Output:
  * .jakx_watch/history/commit_impact.md — markdown table sorted by Δerr
  * .jakx_watch/history/commit_impact.json — same data as JSON for tools
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
HISTORY_DIR = ROOT / ".jakx_watch" / "history"
OUTPUT_MD = HISTORY_DIR / "commit_impact.md"
OUTPUT_JSON = HISTORY_DIR / "commit_impact.json"


def parse_snap_filename(filename: str) -> str | None:
    """Extract timestamp from snap-YYYYMMDDTHHMMSS-<SHA>.json.

    Returns timestamp_str or None if format doesn't match.
    Note: The SHA in the filename may be truncated/unreliable; we use
    git_sha from the JSON itself instead.
    """
    m = re.match(r"snap-(\d{8}T\d{6})-", filename)
    if m:
        return m.group(1)
    return None


def load_snapshot(snap_path: Path) -> dict:
    """Load a snapshot JSON file."""
    try:
        return json.loads(snap_path.read_text())
    except Exception as e:
        print(f"ERROR loading {snap_path}: {e}", file=sys.stderr)
        return {}


def get_metrics(snap: dict) -> dict:
    """Extract metrics summary from a snapshot."""
    summary = snap.get("summary", {})
    buckets = summary.get("buckets", {})
    return {
        "ts": snap.get("ts", "?"),
        "sha": snap.get("git_sha", "?"),
        "total_files": summary.get("total_files", 0),
        "real_clean": buckets.get("real-clean", 0),
        "real_partial": buckets.get("real-partial", 0),
        "split_failed": buckets.get("split-failed", 0),
        "static_only": buckets.get("static-only", 0),
        "sum_defun": summary.get("sum_defun", 0),
        "sum_defmethod": summary.get("sum_defmethod", 0),
        "sum_error_markers": summary.get("sum_error_markers", 0),
        "sum_warn_markers": summary.get("sum_warn_markers", 0),
    }


def get_commit_subject(sha: str) -> str:
    """Get commit subject line via git show."""
    try:
        result = subprocess.run(
            ["git", "show", "--format=%s", "-s", sha],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"WARNING: git show {sha} failed: {e}", file=sys.stderr)
    return "(unknown)"


def classify_commit(delta: dict) -> str:
    """Classify commit impact: WINNER, LOSER, or NEUTRAL.

    WINNER: Δerr ≤ -10 AND Δreal_clean ≥ 0 AND no bucket went negative
    LOSER: Δerr ≥ +100 OR Δreal_clean ≤ -5
    NEUTRAL: otherwise
    """
    d_err = delta["d_error_markers"]
    d_clean = delta["d_real_clean"]
    d_partial = delta["d_real_partial"]
    d_split = delta["d_split_failed"]
    d_static = delta["d_static_only"]

    # Check for negative buckets (rare but significant)
    went_negative = d_clean < 0 or d_partial < 0 or d_split < 0 or d_static < 0

    if d_err <= -10 and d_clean >= 0 and not went_negative:
        return "✅"
    if d_err >= 100 or d_clean <= -5:
        return "❌"
    return "~"


def compute_delta(prev_metrics: dict, curr_metrics: dict) -> dict:
    """Compute delta between two metric snapshots."""
    return {
        "d_error_markers": curr_metrics["sum_error_markers"] - prev_metrics["sum_error_markers"],
        "d_warn_markers": curr_metrics["sum_warn_markers"] - prev_metrics["sum_warn_markers"],
        "d_real_clean": curr_metrics["real_clean"] - prev_metrics["real_clean"],
        "d_real_partial": curr_metrics["real_partial"] - prev_metrics["real_partial"],
        "d_split_failed": curr_metrics["split_failed"] - prev_metrics["split_failed"],
        "d_static_only": curr_metrics["static_only"] - prev_metrics["static_only"],
        "d_defun": curr_metrics["sum_defun"] - prev_metrics["sum_defun"],
        "d_defmethod": curr_metrics["sum_defmethod"] - prev_metrics["sum_defmethod"],
    }


def main():
    """Analyze commit impacts from snapshots."""
    # Glob all snap-*.json files
    snap_files = sorted(HISTORY_DIR.glob("snap-*.json"))
    if not snap_files:
        print(f"WARNING: no snapshot files found in {HISTORY_DIR}", file=sys.stderr)
        return

    # Parse and sort by timestamp, load snapshots to get the actual SHA
    snaps_by_ts: list[tuple[str, Path, dict]] = []
    for snap_path in snap_files:
        ts = parse_snap_filename(snap_path.name)
        if ts:
            snap = load_snapshot(snap_path)
            if snap:
                snaps_by_ts.append((ts, snap_path, snap))

    snaps_by_ts.sort(key=lambda x: x[0])
    print(f"Loaded {len(snaps_by_ts)} snapshots")

    # Load metrics for each snapshot
    metrics_list: list[tuple[str, str, dict]] = []
    for ts, snap_path, snap in snaps_by_ts:
        sha = snap.get("git_sha", "?")
        if snap:
            metrics = get_metrics(snap)
            metrics_list.append((ts, sha, metrics))

    # Compute deltas for each consecutive pair
    impacts: list[dict] = []
    for i in range(len(metrics_list) - 1):
        ts_prev, sha_prev, metrics_prev = metrics_list[i]
        ts_curr, sha_curr, metrics_curr = metrics_list[i + 1]

        delta = compute_delta(metrics_prev, metrics_curr)
        delta["commit"] = sha_curr
        delta["subject"] = get_commit_subject(sha_curr)
        delta["verdict"] = classify_commit(delta)
        delta["timestamp"] = ts_curr

        impacts.append(delta)

    # Sort by Δerr ascending (biggest error reducers first)
    impacts.sort(key=lambda x: x["d_error_markers"])

    print(f"Computed {len(impacts)} commit impact records")
    print(
        f"  Winners: {sum(1 for x in impacts if x['verdict'] == '✅')}"
    )
    print(
        f"  Losers: {sum(1 for x in impacts if x['verdict'] == '❌')}"
    )
    print(
        f"  Neutral: {sum(1 for x in impacts if x['verdict'] == '~')}"
    )

    # Emit markdown
    now = datetime.now().isoformat()
    md_lines = [
        "# Commit impact log",
        "",
        f"_source: scripts/jakx_watch/commit_impact_log.py · generated: {now}_",
        "",
        "| commit | subject | Δerr | Δwarn | Δreal-clean | Δreal-partial | Δsplit-failed | verdict |",
        "|--------|---------|-----:|------:|------------:|--------------:|:-------------:|:-------:|",
    ]

    for impact in impacts:
        subject = impact["subject"][:60].replace("|", "\\|")
        row = (
            f"| `{impact['commit'][:8]}` "
            f"| {subject} "
            f"| {impact['d_error_markers']:+d} "
            f"| {impact['d_warn_markers']:+d} "
            f"| {impact['d_real_clean']:+d} "
            f"| {impact['d_real_partial']:+d} "
            f"| {impact['d_split_failed']:+d} "
            f"| {impact['verdict']} |"
        )
        md_lines.append(row)

    # Top winners
    winners = [x for x in impacts if x["verdict"] == "✅"]
    if winners:
        md_lines.extend(
            [
                "",
                "## Top winners",
                "",
                "| commit | subject | Δerr | Δwarn | Δreal-clean | Δreal-partial | Δsplit-failed |",
                "|--------|---------|-----:|------:|------------:|--------------:|:-------------:|",
            ]
        )
        for impact in winners[:10]:
            subject = impact["subject"][:60].replace("|", "\\|")
            row = (
                f"| `{impact['commit'][:8]}` "
                f"| {subject} "
                f"| {impact['d_error_markers']:+d} "
                f"| {impact['d_warn_markers']:+d} "
                f"| {impact['d_real_clean']:+d} "
                f"| {impact['d_real_partial']:+d} "
                f"| {impact['d_split_failed']:+d} |"
            )
            md_lines.append(row)

    # Top losers
    losers = [x for x in impacts if x["verdict"] == "❌"]
    if losers:
        md_lines.extend(
            [
                "",
                "## Top losers",
                "",
                "| commit | subject | Δerr | Δwarn | Δreal-clean | Δreal-partial | Δsplit-failed |",
                "|--------|---------|-----:|------:|------------:|--------------:|:-------------:|",
            ]
        )
        for impact in losers[-10:]:  # Show worst 10 (end of sorted list)
            subject = impact["subject"][:60].replace("|", "\\|")
            row = (
                f"| `{impact['commit'][:8]}` "
                f"| {subject} "
                f"| {impact['d_error_markers']:+d} "
                f"| {impact['d_warn_markers']:+d} "
                f"| {impact['d_real_clean']:+d} "
                f"| {impact['d_real_partial']:+d} "
                f"| {impact['d_split_failed']:+d} |"
            )
            md_lines.append(row)

    OUTPUT_MD.write_text("\n".join(md_lines) + "\n")
    print(f"Wrote {OUTPUT_MD}")

    # Emit JSON
    json_data = [
        {
            "commit": x["commit"],
            "subject": x["subject"],
            "timestamp": x["timestamp"],
            "d_error_markers": x["d_error_markers"],
            "d_warn_markers": x["d_warn_markers"],
            "d_real_clean": x["d_real_clean"],
            "d_real_partial": x["d_real_partial"],
            "d_split_failed": x["d_split_failed"],
            "d_static_only": x["d_static_only"],
            "d_defun": x["d_defun"],
            "d_defmethod": x["d_defmethod"],
            "verdict": x["verdict"],
        }
        for x in impacts
    ]
    OUTPUT_JSON.write_text(json.dumps(json_data, indent=2) + "\n")
    print(f"Wrote {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
