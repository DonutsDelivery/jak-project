#!/usr/bin/env python3
"""convergence_report.py — turn convergence.jsonl into per-applier yield report.

Per the user's framing: "are we compounding" requires seeing inter-applier
deltas. This script reads .compound_loop/convergence.jsonl and outputs:

  - Per-applier yield (Σ Δrc per tool label, tells you which tools produced)
  - Cross-pattern signal (when tool A's commit moves tool B's metric — that's
    compounding evidence)
  - Acceleration trend (recent commits' Δrc/hour vs older — is it speeding
    up, flat, or slowing?)
  - Position progress vs ceiling

Each row in convergence.jsonl is tagged with the applier label that
produced the commit (apply_guard sets it; manual commits get "manual").

Usage:
  python3 scripts/jakx_watch/convergence_report.py
  python3 scripts/jakx_watch/convergence_report.py --game jakx --last 20
  python3 scripts/jakx_watch/convergence_report.py --since 2026-04-26T00:00
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / ".compound_loop" / "convergence.jsonl"


def load_rows(game: str | None = None, since: str | None = None) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    rows = []
    cutoff = datetime.fromisoformat(since) if since else None
    for line in LOG_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if game and r.get("game") != game:
            continue
        if cutoff:
            try:
                ts = datetime.fromisoformat(r.get("ts", ""))
                if ts < cutoff:
                    continue
            except ValueError:
                continue
        rows.append(r)
    return rows


def label_of(row: dict) -> str:
    """Return the applier label, defaulting to 'manual' for hook-snapped rows."""
    return row.get("label") or "manual"


def per_applier_yield(rows: list[dict]) -> dict:
    """For each applier label, sum Δpass / Δrc / Δftp / Δrm vs prior STABLE row.

    Δpass (offline_test_pass) is the PRIMARY yield signal — real correctness
    via compile + bytematch transitivity. Δrc is the leading indicator only
    (text-scan proxy). When Δrc moves but Δpass doesn't, the applier is
    producing rc-shaped noise (suppress-not-fix pattern).
    """
    yields = defaultdict(lambda: {
        "n_commits": 0,
        "delta_pass_sum": 0,
        "n_pass_data_pairs": 0,  # how many transitions had pass data on BOTH sides
        "delta_rc_sum": 0,
        "delta_ftp_sum": 0,
        "delta_rm_sum": 0,
        "delta_rns_sum": 0,
    })
    prev_stable = None
    for r in rows:
        if r.get("unstable"):
            continue
        if prev_stable is not None:
            label = label_of(r)
            yields[label]["n_commits"] += 1
            # Δpass: only credit when BOTH rows have actual offline_test data.
            # Missing data → skip the delta (don't treat absent field as 0,
            # which would be a false regression when fields disappear).
            r_pass = r.get("offline_test_pass") if not r.get("offline_test_missing") else None
            p_pass = prev_stable.get("offline_test_pass") if not prev_stable.get("offline_test_missing") else None
            if r_pass is not None and p_pass is not None:
                yields[label]["delta_pass_sum"] += r_pass - p_pass
                yields[label]["n_pass_data_pairs"] += 1
            yields[label]["delta_rc_sum"] += (
                r.get("files_real_clean", 0) - prev_stable.get("files_real_clean", 0)
            )
            yields[label]["delta_ftp_sum"] += (
                r.get("failed_type_prop_errors", 0)
                - prev_stable.get("failed_type_prop_errors", 0)
            )
            yields[label]["delta_rm_sum"] += (
                r.get("return_mismatch_warns", 0)
                - prev_stable.get("return_mismatch_warns", 0)
            )
            yields[label]["delta_rns_sum"] += (
                r.get("reg_not_set_errors", 0)
                - prev_stable.get("reg_not_set_errors", 0)
            )
        prev_stable = r
    return dict(yields)


def cross_pattern_signal(rows: list[dict]) -> list[tuple[str, dict]]:
    """Find commits where the applier's PRIMARY metric moved AND a different
    metric also moved >= half as much. That's evidence of cross-pattern
    compounding: one applier's fix unlocked another applier's signal.

    Heuristic primary metric per label:
      return_mismatch  → return_mismatch_warns
      sig_passthrough  → reg_not_set_errors
      type_cast        → failed_type_prop_errors
      cross-port       → failed_type_prop_errors (ports type_casts)
      consensus        → return_mismatch_warns
    """
    primary = {
        "return-mismatch": "return_mismatch_warns",
        "return_mismatch": "return_mismatch_warns",
        "sig_passthrough": "reg_not_set_errors",
        "sig-passthrough": "reg_not_set_errors",
        "type_cast": "failed_type_prop_errors",
        "type-cast": "failed_type_prop_errors",
        "cross-port": "failed_type_prop_errors",
        "consensus": "return_mismatch_warns",
    }
    other_metrics = [
        "return_mismatch_warns",
        "failed_type_prop_errors",
        "reg_not_set_errors",
        "failed_static_ref_errors",
    ]

    findings: list[tuple[str, dict]] = []
    prev_stable = None
    for r in rows:
        if r.get("unstable"):
            continue
        if prev_stable is None:
            prev_stable = r
            continue
        label = label_of(r)
        # Match label substring against keys
        primary_metric = None
        for key, m in primary.items():
            if key in label:
                primary_metric = m
                break
        if primary_metric is None:
            prev_stable = r
            continue
        delta_primary = r.get(primary_metric, 0) - prev_stable.get(primary_metric, 0)
        if abs(delta_primary) < 5:
            prev_stable = r
            continue
        for metric in other_metrics:
            if metric == primary_metric:
                continue
            delta_other = r.get(metric, 0) - prev_stable.get(metric, 0)
            # Significant cross-effect = >=50% of primary magnitude AND
            # both moved in the SAME direction (both decreased = compounding)
            if (abs(delta_other) >= abs(delta_primary) * 0.5
                    and (delta_other < 0) == (delta_primary < 0)
                    and abs(delta_other) >= 5):
                findings.append((r.get("sha", "?"), {
                    "label": label,
                    "primary_metric": primary_metric,
                    "delta_primary": delta_primary,
                    "cross_metric": metric,
                    "delta_cross": delta_other,
                }))
        prev_stable = r
    return findings


def acceleration_trend(rows: list[dict], window_hours: float = 1.0) -> dict:
    """Recent yield rate vs older yield rate."""
    stable = [r for r in rows if not r.get("unstable")]
    if len(stable) < 4:
        return {"insufficient_data": True, "n_rows": len(stable)}

    # Split: last window_hours vs everything before
    try:
        latest_ts = datetime.fromisoformat(stable[-1]["ts"])
    except (ValueError, KeyError):
        return {"insufficient_data": True, "reason": "ts parse"}
    cutoff = latest_ts - timedelta(hours=window_hours)
    recent = [r for r in stable if datetime.fromisoformat(r["ts"]) >= cutoff]
    older = [r for r in stable if datetime.fromisoformat(r["ts"]) < cutoff]
    if not recent or not older:
        return {"insufficient_data": True, "reason": "no split"}

    def rate(window: list[dict]) -> float:
        if len(window) < 2:
            return 0.0
        rc_delta = window[-1]["files_real_clean"] - window[0]["files_real_clean"]
        try:
            t0 = datetime.fromisoformat(window[0]["ts"])
            t1 = datetime.fromisoformat(window[-1]["ts"])
            hours = max((t1 - t0).total_seconds() / 3600.0, 1 / 3600.0)
        except ValueError:
            return 0.0
        return rc_delta / hours

    recent_rate = rate(recent)
    older_rate = rate(older)
    return {
        "recent_window_hours": window_hours,
        "recent_n_rows": len(recent),
        "older_n_rows": len(older),
        "recent_rc_per_hour": round(recent_rate, 2),
        "older_rc_per_hour": round(older_rate, 2),
        "ratio": round(recent_rate / older_rate, 2) if older_rate else None,
    }


def position_summary(rows: list[dict]) -> dict:
    stable = [r for r in rows if not r.get("unstable")]
    if not stable:
        return {}
    latest = stable[-1]
    return {
        "ts": latest.get("ts"),
        "sha": latest.get("sha"),
        "ot_attempted": latest.get("offline_test_attempted", 0),
        "ot_pass": latest.get("offline_test_pass", 0),
        "ot_partial": latest.get("offline_test_partial", 0),
        "ot_pass_pct": latest.get("offline_test_pass_pct", 0.0),
        "ot_stale": latest.get("offline_test_stale", True),
        "ot_age_sec": latest.get("offline_test_age_sec", 0),
        "rc_position": f"{latest.get('files_real_clean', 0)}/{latest.get('files_total', 0)}"
                       f" ({latest.get('files_real_clean_pct', 0):.2f}%)",
        "sig_position": f"{latest.get('method_decls_complete', 0)}/{latest.get('method_decls_total', 0)}"
                        f" ({latest.get('method_decls_complete_pct', 0):.2f}%)",
        "ftp_remaining": latest.get("failed_type_prop_errors", 0),
        "rm_remaining": latest.get("return_mismatch_warns", 0),
        "rns_remaining": latest.get("reg_not_set_errors", 0),
        "fsr_remaining": latest.get("failed_static_ref_errors", 0),
    }


def render(rows: list[dict]) -> str:
    out = []
    pos = position_summary(rows)
    if pos:
        out.append(f"\n=== POSITION (latest stable, {pos['sha']} {pos['ts']}) ===")
        # PRIMARY: real correctness (compile + bytematch via _REF.gc transitivity)
        # Show BOTH denominators per G0.3:
        #   pass/attempted = pass-rate within test scope (selection-biased subset)
        #   pass/total     = pass-rate against all emitted files (true population)
        files_total = int(pos['rc_position'].split('/')[1].split(' ')[0]) if pos['rc_position'] else 0
        if pos["ot_attempted"] > 0:
            stale_marker = "  ⚠ STALE" if pos["ot_stale"] else ""
            scope_pct = pos['ot_pass_pct']
            broad_pct = (100.0 * pos["ot_pass"] / files_total) if files_total else 0.0
            out.append(f"  pass: {pos['ot_pass']}/{pos['ot_attempted']} "
                       f"({scope_pct:.2f}% of test scope) "
                       f"← PRIMARY (compile + _REF.gc match){stale_marker}")
            out.append(f"        {pos['ot_pass']}/{files_total} "
                       f"({broad_pct:.2f}% of all emitted) "
                       f"← BROADER denominator (per G0.3 — selection bias warning)")
            out.append(f"        test_scope: {pos['ot_attempted']} of {files_total} "
                       f"({100.0*pos['ot_attempted']/files_total:.1f}% _REF.gc coverage) "
                       f"← Δtest_scope is its own signal")
            out.append(f"        partial: {pos['ot_partial']} "
                       f"(amber: compile or compare failed)")
            out.append(f"        data age: {pos['ot_age_sec']}s")
        else:
            out.append(f"  pass: (no offline_test data — run offline_test_pass.py)"
                       f"  ← PRIMARY missing")
        # LEADING INDICATOR (text-scan proxy, NOT correctness)
        out.append(f"  rc:  {pos['rc_position']}   ← leading indicator only (text proxy)")
        out.append(f"  sig: {pos['sig_position']}   ← signature completeness")
        out.append(f"  ftp remaining:  {pos['ftp_remaining']}   ← largest unworked pile")
        out.append(f"  rns remaining:  {pos['rns_remaining']}")
        out.append(f"  rm  remaining:  {pos['rm_remaining']}")
        out.append(f"  fsr remaining:  {pos['fsr_remaining']}")

    out.append(f"\n=== PER-APPLIER YIELD (Σ deltas vs prior stable row) ===")
    out.append(f"  Δpass is the WHOLE test (per G0.1). Lane validity = Δpass > 0.")
    out.append(f"  Δrc has zero confirmation power — shown for context only.")
    out.append(f"  +rc/+0 pass commits are null OR suppress-not-fix; either way the")
    out.append(f"  lane gets killed, not 'monitored further.'")
    yld = per_applier_yield(rows)
    if not yld:
        out.append("  (no stable transitions yet — need 2+ stable rows)")
    else:
        out.append(f"  {'applier':<35} {'n':>3}  {'Δpass':>6} {'Δrc':>6} {'Δftp':>7} {'Δrm':>6} {'Δrns':>6}")
        for label, y in sorted(yld.items(), key=lambda x: -x[1]["delta_pass_sum"]):
            out.append(f"  {label:<35} {y['n_commits']:>3}  "
                       f"{y['delta_pass_sum']:>+6d} {y['delta_rc_sum']:>+6d} "
                       f"{y['delta_ftp_sum']:>+7d} "
                       f"{y['delta_rm_sum']:>+6d} {y['delta_rns_sum']:>+6d}")
        out.append("  (positive Δpass/Δrc = improvement; negative Δftp/Δrm/Δrns = improvement)")

    out.append(f"\n=== CROSS-PATTERN COMPOUNDING ===")
    out.append("  Commits where applier's primary moved AND a different metric")
    out.append("  also moved meaningfully in the same direction. Direct evidence")
    out.append("  of one lane unlocking another (or its absence).")
    out.append("")
    cross = cross_pattern_signal(rows)
    if not cross:
        out.append("  (no cross-pattern signals detected — lanes may be independent)")
    else:
        for sha, info in cross[-15:]:
            out.append(f"  {sha[:10]}  {info['label']}  "
                       f"{info['primary_metric']} Δ{info['delta_primary']:+d}  "
                       f"AND  {info['cross_metric']} Δ{info['delta_cross']:+d}")

    out.append(f"\n=== ACCELERATION TREND ===")
    accel = acceleration_trend(rows, window_hours=1.0)
    if accel.get("insufficient_data"):
        out.append(f"  (insufficient data: {accel.get('reason', 'too few rows')})")
    else:
        ratio = accel.get("ratio")
        ratio_label = (f"{ratio}x"
                       if ratio is not None
                       else "n/a (older window had 0 rate)")
        out.append(f"  recent {accel['recent_window_hours']}h "
                   f"({accel['recent_n_rows']} rows): "
                   f"{accel['recent_rc_per_hour']} rc/hour")
        out.append(f"  older  ({accel['older_n_rows']} rows): "
                   f"{accel['older_rc_per_hour']} rc/hour")
        out.append(f"  ratio:  {ratio_label}  (>1 = accelerating, <1 = decelerating)")

    return "\n".join(out)


def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="jakx",
                    choices=("jak1", "jak2", "jak3", "jakx"))
    ap.add_argument("--last", type=int, default=0,
                    help="Only consider last N rows (0 = all)")
    ap.add_argument("--since", default=None,
                    help="Only consider rows since ISO timestamp")
    args = ap.parse_args()

    rows = load_rows(game=args.game, since=args.since)
    if args.last > 0:
        rows = rows[-args.last:]

    if not rows:
        print("(no convergence data — run convergence_metric.py first)")
        return 1

    print(f"convergence_report — {len(rows)} rows for {args.game}")
    print(render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
