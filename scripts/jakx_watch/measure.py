#!/usr/bin/env python3
"""Bucket jakx decomp output into per-file health categories.

Scans decompiler_out/jakx/*_disasm.gc, classifies each file, tallies error
markers, and writes a JSON snapshot under .jakx_watch/history/.

Usage:
    python3 scripts/jakx_watch/measure.py                 # snapshot + console summary
    python3 scripts/jakx_watch/measure.py --no-write      # summary only, don't save
    python3 scripts/jakx_watch/measure.py --log LOGFILE   # also parse a decomp log

Categories (per file):
  real-clean   : has defun/defmethod, no ERROR/"failed to figure out" markers
  real-partial : has defun/defmethod AND some error markers
  split-failed : 0 defuns + 0 defmethods + has "failed to figure out" markers
                 or starts with top-level (local-vars — top-level splitting
                 never ran; symptom of types_succeeded=false.
  static-only  : 0 defuns + 0 defmethods + 0 failure markers
                 (headers, data-only files — legitimately empty of code)
  unknown      : doesn't fit any bucket (should not happen)
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DECOMP_OUT = ROOT / "decompiler_out" / "jakx"
HISTORY_DIR = ROOT / ".jakx_watch" / "history"

RE_DEFUN = re.compile(r"^\(defun[\s*]", re.MULTILINE)
RE_DEFMETHOD = re.compile(r"^\(defmethod[\s*]", re.MULTILINE)
RE_LOCAL_VARS = re.compile(r"^\(local-vars[\s\n]", re.MULTILINE)
RE_FAILED = re.compile(r"^;; failed to figure out what this is:", re.MULTILINE)
RE_ERROR = re.compile(r"^;; ERROR: (.+)$", re.MULTILINE)
RE_WARN = re.compile(r"^;; WARN: (.+)$", re.MULTILINE)
RE_INFO = re.compile(r"^;; INFO: (.+)$", re.MULTILINE)
# comment markers that indicate decomp concluded a type/fn is unknown
RE_TYPE_UNKNOWN = re.compile(r"^;; type .+ is defined here, but it is unknown to the decompiler", re.MULTILINE)

# Canonicalize error messages that have variable values so we can bucket them.
def canonicalize_error(msg: str) -> str:
    m = msg.strip()
    # Strip specific register/addr/offset/symbol bits
    m = re.sub(r"\b(a|t|s|v|gp|fp|sp|ra)\d+\b", "REG", m)
    m = re.sub(r"\b-?\d+\b", "N", m)
    m = re.sub(r"\b0x[0-9a-fA-F]+\b", "H", m)
    m = re.sub(r"\s+", " ", m)
    return m


def classify(text: str) -> tuple[str, dict]:
    defun_ct = len(RE_DEFUN.findall(text))
    defmethod_ct = len(RE_DEFMETHOD.findall(text))
    failed_ct = len(RE_FAILED.findall(text))
    error_ct = len(RE_ERROR.findall(text))
    warn_ct = len(RE_WARN.findall(text))
    local_vars_top = bool(RE_LOCAL_VARS.search(text))

    fn_total = defun_ct + defmethod_ct

    if fn_total == 0:
        if failed_ct > 0 or local_vars_top:
            cat = "split-failed"
        elif error_ct > 0:
            # no defuns, has errors (e.g. "ERROR: function has no type analysis")
            cat = "split-failed"
        else:
            cat = "static-only"
    else:
        if failed_ct + error_ct == 0:
            cat = "real-clean"
        else:
            cat = "real-partial"

    return cat, {
        "defun": defun_ct,
        "defmethod": defmethod_ct,
        "failed": failed_ct,
        "error": error_ct,
        "warn": warn_ct,
        "has_toplevel_local_vars": local_vars_top,
        "lines": text.count("\n") + 1,
    }


def scan_decomp_output(decomp_out: Path) -> dict:
    per_file = {}
    error_hist = collections.Counter()
    warn_hist = collections.Counter()
    info_hist = collections.Counter()
    bucket_counts = collections.Counter()

    if not decomp_out.exists():
        raise SystemExit(f"decompiler output dir not found: {decomp_out}")

    files = sorted(decomp_out.glob("*_disasm.gc"))
    for fp in files:
        text = fp.read_text(errors="replace")
        cat, stats = classify(text)
        bucket_counts[cat] += 1
        name = fp.name[: -len("_disasm.gc")]
        per_file[name] = {"category": cat, **stats}
        for m in RE_ERROR.findall(text):
            error_hist[canonicalize_error(m)] += 1
        for m in RE_WARN.findall(text):
            warn_hist[canonicalize_error(m)] += 1
        for m in RE_INFO.findall(text):
            info_hist[canonicalize_error(m)] += 1

    return {
        "total_files": len(files),
        "buckets": dict(bucket_counts),
        "errors": dict(error_hist.most_common()),
        "warns": dict(warn_hist.most_common()),
        "infos": dict(info_hist.most_common()),
        "per_file": per_file,
    }


RE_LOG_TYPE_LOAD_ERROR = re.compile(r"\[error\] Type (\S+) has ", re.MULTILINE)
RE_LOG_FATAL_TYPE_ERROR = re.compile(r"-- Type Error! --\s*\n\S*(?:Type )?(\S+) is unknown", re.MULTILINE)
RE_LOG_FN_FAILED = re.compile(r"\[error\] Function \((.+?)\) failed type prop", re.MULTILINE)
RE_LOG_DONE_FILE = re.compile(r"\[(\d+)/(\d+)\]------ (\S+)")
RE_LOG_UNKNOWN_SYMBOL = re.compile(r"Unknown symbol: (\S+)", re.MULTILINE)
RE_LOG_UNKNOWN_TYPE = re.compile(r"Type (\S+) is unknown", re.MULTILINE)
RE_LOG_UNKNOWN_FN_TYPE = re.compile(r"Function (\S+) didn't know its type", re.MULTILINE)
# "Called a function, but we do not know its type" — log at which file?
RE_LOG_FILE_HEADER = re.compile(r"\[(\d+)/(\d+)\]------ (\S+)")
# C++ assertion death — cannot be fixed via all-types.gc, needs decompiler C++ work.
RE_LOG_DIE = re.compile(r"\[die\] (.+)", re.MULTILINE)
RE_LOG_MIPS2C_ON = re.compile(r"\[info\] MIPS2C on (\S+)", re.MULTILINE)
RE_LOG_MIPS2C_UNKNOWN = re.compile(r"mips2c unknown: (.+)", re.MULTILINE)


def parse_decomp_log(path: Path) -> dict:
    if not path.exists():
        return {"log_parsed": False, "reason": f"log file not found: {path}"}
    text = path.read_text(errors="replace")
    type_load_errors = RE_LOG_TYPE_LOAD_ERROR.findall(text)
    fn_type_prop_failures = RE_LOG_FN_FAILED.findall(text)
    file_progress = RE_LOG_DONE_FILE.findall(text)
    last_file = None
    last_idx = None
    total_files = None
    for idx, tot, name in file_progress:
        last_idx = int(idx)
        total_files = int(tot)
        last_file = name
    # crash / fatal
    fatal = RE_LOG_FATAL_TYPE_ERROR.findall(text)

    unk_sym = collections.Counter(RE_LOG_UNKNOWN_SYMBOL.findall(text))
    unk_type = collections.Counter(RE_LOG_UNKNOWN_TYPE.findall(text))
    unk_fn = collections.Counter(RE_LOG_UNKNOWN_FN_TYPE.findall(text))

    # C++ assertion ("die") — find the last occurrence and the MIPS2C function
    # that was in flight (useful context: the function is the crash site).
    die_msgs = RE_LOG_DIE.findall(text)
    mips2c_fns = RE_LOG_MIPS2C_ON.findall(text)
    last_mips2c_fn = mips2c_fns[-1] if mips2c_fns else None
    mips2c_unknown = collections.Counter(RE_LOG_MIPS2C_UNKNOWN.findall(text))

    return {
        "log_parsed": True,
        "log_path": str(path),
        "log_size_bytes": path.stat().st_size,
        "type_load_errors": type_load_errors,
        "fn_type_prop_failure_count": len(fn_type_prop_failures),
        "last_processed_index": last_idx,
        "total_index": total_files,
        "last_processed_file": last_file,
        "fatal_unknown_types": fatal,
        "top_unknown_symbols": dict(unk_sym.most_common(20)),
        "top_unknown_types": dict(unk_type.most_common(20)),
        "top_unknown_fn_types": dict(unk_fn.most_common(20)),
        "unknown_symbol_count": sum(unk_sym.values()),
        "unknown_symbol_distinct": len(unk_sym),
        "cpp_assertion_die": die_msgs[-3:] if die_msgs else [],
        "mips2c_last_in_flight": last_mips2c_fn,
        "mips2c_unknown_instrs": dict(mips2c_unknown.most_common(10)),
    }


def find_latest_log() -> Path | None:
    """Pick the most recent fully-written large decompiler log.

    We skip logs whose mtime was updated within the last 2 seconds — those
    may still be being written by a concurrent decomp run in another session.
    """
    log_dir = ROOT / "log"
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob("decompiler.*.log"), key=lambda p: p.stat().st_mtime)
    now = datetime.datetime.now().timestamp()
    for p in reversed(logs):
        stt = p.stat()
        if stt.st_size < 50_000:
            continue
        if now - stt.st_mtime < 2:
            continue
        return p
    return logs[-1] if logs else None


def short_digest(obj) -> str:
    s = json.dumps(obj, sort_keys=True)
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def hash_config_state() -> dict:
    """Hash of files sessions 1/2 own, so we can detect edits vs last measurement."""
    paths = [
        ROOT / "decompiler" / "config" / "jakx" / "all-types.gc",
        ROOT / "decompiler" / "config" / "jakx" / "jakx_config.jsonc",
    ]
    # plus all jsonc under ntsc_v1 and potentially_useful
    for p in (ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1").glob("*.jsonc"):
        paths.append(p)
    for p in (ROOT / "decompiler" / "config" / "jakx" / "potentially_useful").glob("*.jsonc"):
        paths.append(p)
    out = {}
    for p in paths:
        if p.exists():
            h = hashlib.sha1(p.read_bytes()).hexdigest()[:12]
            out[str(p.relative_to(ROOT))] = h
    return out


def build_snapshot(log_path: Path | None, decomp_out: Path) -> dict:
    out = scan_decomp_output(decomp_out)
    log = parse_decomp_log(log_path) if log_path else {"log_parsed": False}
    snapshot = {
        "schema": 1,
        "ts": datetime.datetime.now().isoformat(),
        "git_sha": git_sha(),
        "decomp_out": str(decomp_out.relative_to(ROOT) if decomp_out.is_relative_to(ROOT) else decomp_out),
        "config_hashes": hash_config_state(),
        "decomp_log": log,
        "summary": {
            "total_files": out["total_files"],
            "buckets": out["buckets"],
            "sum_defun": sum(v["defun"] for v in out["per_file"].values()),
            "sum_defmethod": sum(v["defmethod"] for v in out["per_file"].values()),
            "sum_failed_markers": sum(v["failed"] for v in out["per_file"].values()),
            "sum_error_markers": sum(v["error"] for v in out["per_file"].values()),
            "sum_warn_markers": sum(v["warn"] for v in out["per_file"].values()),
        },
        "error_histogram": out["errors"],
        "warn_histogram": out["warns"],
        "info_histogram": out["infos"],
        "per_file": out["per_file"],
    }
    snapshot["digest"] = short_digest(snapshot["summary"])
    return snapshot


def git_sha() -> str | None:
    try:
        import subprocess

        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


def format_summary_block(snap: dict, prev: dict | None = None) -> str:
    s = snap["summary"]
    lines = []
    ts = snap["ts"]
    sha = snap.get("git_sha") or "unknown"
    # Canonical header — agents grep this.
    lines.append(f"# jakx_watch status")
    lines.append(f"last updated @ git {sha[:12]}  ·  ts {ts}")
    cfg_dirty = False
    for p, h in (snap.get("config_hashes") or {}).items():
        # If any config file's hash doesn't match what git has at HEAD, the
        # snapshot reflects uncommitted edits — mark it.
        pass  # (keep simple; the ts + sha is enough signal for now)
    lines.append("")

    log = snap.get("decomp_log") or {}
    # ===== canonical section 1: FATAL crashes =====
    lines.append("## FATAL crashes")
    if log.get("log_parsed"):
        fatal = log.get("fatal_unknown_types") or []
        die = log.get("cpp_assertion_die") or []
        tli = log.get("last_processed_index")
        ttot = log.get("total_index")
        if tli is not None:
            blocked = (ttot or 0) - tli
            lines.append(
                f"decomp progress: {tli}/{ttot} processed "
                f"({blocked} files blocked by crash; last: {log.get('last_processed_file')})"
            )
        if fatal:
            lines.append(f"unknown type(s) that crashed decomp: {fatal[:5]}")
        if die:
            lines.append(f"C++ ASSERTION crash (decompiler bug — NOT fixable via all-types.gc):")
            for msg in die[-2:]:
                lines.append(f"  {msg[:140]}")
            lift = log.get("mips2c_last_in_flight")
            if lift:
                lines.append(f"  crash happened during mips2c on: {lift}")
                lines.append(f"  → this is a decompiler C++ bug. Report to Claude orchestrator;")
                lines.append(f"    config/type edits won't fix it.")
            mui = log.get("mips2c_unknown_instrs") or {}
            if mui:
                lines.append(f"  unknown MIPS instructions mips2c hit ({len(mui)} kinds):")
                for k, v in list(mui.items())[:6]:
                    lines.append(f"    {v:3d}  {k}")
        if not fatal and not die:
            lines.append("no fatal crashes in last run")
        tl = log.get("type_load_errors") or []
        if tl:
            lines.append(f"type-load errors: {tl[:5]}{' ...' if len(tl) > 5 else ''}")
        lines.append(f"fn type-prop failures: {log.get('fn_type_prop_failure_count')}")
    else:
        lines.append("(no log parsed)")
    lines.append("")

    # ===== canonical section 2: top unknown symbols =====
    lines.append("## top unknown symbols (fix these in all-types.gc → biggest unblock)")
    if log.get("log_parsed"):
        lines.append(
            f"unknown-symbol events: {log.get('unknown_symbol_count', 0)} across "
            f"{log.get('unknown_symbol_distinct', 0)} names"
        )
        tus = log.get("top_unknown_symbols") or {}
        if tus:
            for k, v in list(tus.items())[:12]:
                lines.append(f"  {v:4d}  {k}")
        else:
            lines.append("(none)")
        tut = log.get("top_unknown_types") or {}
        if tut:
            lines.append("unknown types (fatal blockers — uncomment in all-types.gc to uncrash decomp):")
            for k, v in list(tut.items())[:8]:
                lines.append(f"  {v:4d}  {k}")
    else:
        lines.append("(no log parsed)")
    lines.append("")

    lines.append(f"files total:            {s['total_files']}")
    b = s["buckets"]
    keys = ["real-clean", "real-partial", "split-failed", "static-only", "unknown"]
    for k in keys:
        if k in b:
            lines.append(f"  {k:13s}: {b[k]:4d}")
    lines.append(f"defun total:            {s['sum_defun']}")
    lines.append(f"defmethod total:        {s['sum_defmethod']}")
    lines.append(f"stub markers (failed):  {s['sum_failed_markers']}")
    lines.append(f"inline ERROR markers:   {s['sum_error_markers']}")
    lines.append(f"inline WARN  markers:   {s['sum_warn_markers']}")

    if prev is not None:
        p = prev["summary"]
        lines.append("")
        lines.append("delta vs previous:")

        def d(a, b):
            x = a - b
            return f"{x:+d}" if x != 0 else "  0"

        lines.append(f"  files:       {d(s['total_files'], p['total_files'])}")
        for k in keys:
            a = s["buckets"].get(k, 0)
            b_ = p["buckets"].get(k, 0)
            if a != b_:
                lines.append(f"  {k:13s}: {d(a, b_)}  ({b_} → {a})")
        for key in ("sum_defun", "sum_defmethod", "sum_failed_markers", "sum_error_markers", "sum_warn_markers"):
            dd = s[key] - p[key]
            if dd != 0:
                lines.append(f"  {key:20s}: {dd:+d}  ({p[key]} → {s[key]})")

        # Error category disappearance: strongest signal that a fix worked.
        prev_errs = prev.get("error_histogram", {})
        cur_errs = snap.get("error_histogram", {})
        vanished = [(k, v) for k, v in prev_errs.items() if k not in cur_errs]
        new_errs = [(k, v) for k, v in cur_errs.items() if k not in prev_errs]
        shrunk = [
            (k, prev_errs[k], cur_errs[k])
            for k in cur_errs
            if k in prev_errs and cur_errs[k] < prev_errs[k]
        ]
        grew = [
            (k, prev_errs[k], cur_errs[k])
            for k in cur_errs
            if k in prev_errs and cur_errs[k] > prev_errs[k]
        ]
        if vanished:
            lines.append("")
            lines.append(f"  ERROR categories VANISHED ({len(vanished)}):")
            for k, v in sorted(vanished, key=lambda kv: -kv[1])[:8]:
                lines.append(f"    -{v:4d}  {k[:100]}")
        if shrunk:
            lines.append("")
            shrunk.sort(key=lambda t: -(t[1] - t[2]))
            lines.append(f"  ERROR categories shrunk ({len(shrunk)}) — top 8:")
            for k, old, new in shrunk[:8]:
                lines.append(f"    {new-old:+5d}  ({old} → {new})  {k[:90]}")
        if new_errs:
            lines.append("")
            new_errs.sort(key=lambda kv: -kv[1])
            lines.append(f"  ERROR categories NEW ({len(new_errs)}) — top 5:")
            for k, v in new_errs[:5]:
                lines.append(f"    +{v:4d}  {k[:100]}")
        if grew:
            grew.sort(key=lambda t: -(t[2] - t[1]))
            # only show significant regressions
            grew_sig = [g for g in grew if g[2] - g[1] >= 5]
            if grew_sig:
                lines.append("")
                lines.append(f"  ERROR categories GREW (regression warning) — top 5:")
                for k, old, new in grew_sig[:5]:
                    lines.append(f"    {new-old:+5d}  ({old} → {new})  {k[:90]}")

        # Also track log-level unknown-symbol shifts (the true unblock signal).
        prev_unk = (prev.get("decomp_log") or {}).get("top_unknown_symbols", {}) or {}
        cur_unk = (log or {}).get("top_unknown_symbols", {}) or {}
        resolved = [(k, v) for k, v in prev_unk.items() if k not in cur_unk]
        if resolved:
            lines.append("")
            lines.append(f"  unknown symbols RESOLVED in log ({len(resolved)}):")
            for k, v in sorted(resolved, key=lambda kv: -kv[1])[:10]:
                lines.append(f"    -{v:3d}  {k}")
    lines.append("")
    lines.append("top 8 ERROR categories:")
    for i, (k, v) in enumerate(list(snap["error_histogram"].items())[:8]):
        lines.append(f"  {v:5d}  {k[:110]}")

    lines.append("")
    lines.append("top 8 WARN categories:")
    for i, (k, v) in enumerate(list(snap["warn_histogram"].items())[:8]):
        lines.append(f"  {v:5d}  {k[:110]}")

    if prev is not None:
        prev_pf = prev.get("per_file", {})
        transitions = collections.Counter()
        moved = []
        for name, st in snap["per_file"].items():
            old = prev_pf.get(name)
            if old is None:
                transitions[f"new:{st['category']}"] += 1
                continue
            if old["category"] != st["category"]:
                transitions[f"{old['category']} → {st['category']}"] += 1
                moved.append((name, old["category"], st["category"], old["failed"] + old["error"],
                              st["failed"] + st["error"]))
        for name in prev_pf:
            if name not in snap["per_file"]:
                transitions[f"gone:{prev_pf[name]['category']}"] += 1
        if transitions:
            lines.append("")
            lines.append("category transitions:")
            for k, v in sorted(transitions.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {v:4d}  {k}")
        # Show biggest movers (by absolute change in failed+error)
        if moved:
            moved.sort(key=lambda m: -abs(m[3] - m[4]))
            lines.append("")
            lines.append("top 15 movers (file, old → new, err-count delta):")
            for name, oc, nc, oeoe, neoe in moved[:15]:
                delta = neoe - oeoe
                arrow = "↓" if delta < 0 else ("↑" if delta > 0 else "=")
                lines.append(f"  {arrow} {name}: {oc} → {nc}  ({oeoe} → {neoe}, {delta:+d})")

    # ===== canonical section 3: top stub-density offenders =====
    lines.append("")
    lines.append("## top stub-density offender files")
    offenders = sorted(
        snap["per_file"].items(),
        key=lambda kv: -(kv[1]["failed"] + kv[1]["error"]),
    )[:10]
    if offenders:
        for name, st in offenders:
            lines.append(
                f"  {st['failed']+st['error']:5d}  [{st['category']:13s}] {name}  "
                f"(defun={st['defun']} defmethod={st['defmethod']} stubs={st['failed']} err={st['error']})"
            )
    else:
        lines.append("(none)")

    # ===== optional: types drift (when decomp produced new-all-types.gc) =====
    td = snap.get("types_drift")
    if td:
        lines.append("")
        lines.append("## types drift (generate_all_types regen vs current all-types.gc)")
        lines.append(f"  current: {td['current_active']} active + {td['current_commented']} commented")
        lines.append(f"  regen:   {td['regen_total']} types  ·  discovery: {td['discovery_count']}  ·  over-spec: {td['over_specified_count']}  ·  field-drift: {td['field_drift_count']}")
        if td.get("activation_candidates"):
            lines.append("  ACTIVATION CANDIDATES (uncomment in all-types.gc → immediate unblock):")
            for n in td["activation_candidates"][:20]:
                lines.append(f"    {n}")
            if len(td["activation_candidates"]) > 20:
                lines.append(f"    ... +{len(td['activation_candidates']) - 20} more")
        # RANKED activation queue (from rank_discovery.py).
        ranked = td.get("ranked_discovery", [])
        if ranked:
            lines.append("  RANKED ACTIVATION QUEUE (top 15 — full list: .jakx_watch/activation_queue.md):")
            lines.append(f"    {'#':>2}  {'T':>1}  {'name':<40}  {'parent':<22} refs  j3  par  score")
            for i, r in enumerate(ranked[:15], 1):
                j3 = "✓" if r.get("in_jak3") else " "
                par = "✓" if r.get("parent_ok") else " "
                lines.append(
                    f"    {i:>2}  {r.get('tier','?'):>1}  {r['name']:<40}  "
                    f"{r.get('parent',''):<22} {r.get('refs',0):>3}  {j3:>2}  {par:>3}  {r.get('score',0):>5}"
                )
            lines.append(f"    (generate stubs: python3 scripts/jakx_watch/emit_stub.py --top 30 > stubs.gc)")
        if td.get("discovery_sample"):
            lines.append("  DISCOVERY SAMPLE (regen found, not in current — add deftype):")
            for n in td["discovery_sample"][:10]:
                lines.append(f"    {n}")
            lines.append(f"    ... (see types_drift output for full list of {td['discovery_count']})")

    # ===== optional: static-data decomp bug (when scanner ran) =====
    sdb = snap.get("static_data_bug")
    if sdb:
        lines.append("")
        lines.append("## static-data decomp bug — (define *X* <static-data LN>) fails goalc")
        lines.append(f"  occurrences: {sdb['total']} across {sdb['files']} files")
        lines.append(f"  top offenders:")
        for name, c in sdb.get("top_files", [])[:10]:
            lines.append(f"    {c:>4}  {name}")
        lines.append("  → decompiler C++ patch target: emit `(define *X* ...)` with 2 args, not 3")

    # ===== optional: load-offset clusters =====
    lo = snap.get("load_offset_clusters")
    if lo:
        lines.append("")
        lines.append("## load-offset clusters (\"Could not figure out load\")")
        lines.append(f"  total: {lo.get('total', 0)}  ·  shapes: {lo.get('shapes', {})}")
        tso = lo.get("top_struct_offsets") or []
        if tso:
            lines.append("  top 10 struct offsets (field @OFFS — type_casts.jsonc candidate):")
            for offs, c in tso[:10]:
                lines.append(f"    {c:>4}  offs={offs}")
        tgo = lo.get("top_global_offsets") or []
        if tgo:
            lines.append("  top 8 global offsets (gp+OFFS — unresolved *symbol*/global-var ref):")
            for offs, c in tgo[:8]:
                lines.append(f"    {c:>4}  offs={offs}")
        tf = lo.get("top_files") or []
        if tf:
            lines.append("  top 8 offender files:")
            for name, c in tf[:8]:
                lines.append(f"    {c:>4}  {name}")

    # ===== optional: unknown-call clusters =====
    uc = snap.get("unknown_call_clusters")
    if uc:
        lines.append("")
        lines.append("## unknown-call clusters (methods w/ unknown callees)")
        lines.append(
            f"  total: {uc.get('total', 0)} across {uc.get('files', 0)} files  ·  "
            f"fix signatures in all-types.gc :methods to unblock clusters"
        )
        top_parents = uc.get("top_parent_types") or []
        if top_parents:
            lines.append("  top 10 parent types (fix deftype :methods → clears N errors):")
            for k, v in top_parents[:10]:
                lines.append(f"    {v:>4}  {k}")
        top_files = uc.get("top_files") or []
        if top_files:
            lines.append("  top 10 offender files:")
            for k, v in top_files[:10]:
                lines.append(f"    {v:>4}  {k}")

    # ===== optional: migration candidates (delete-ready hand-ports) =====
    mc = snap.get("migration_candidates")
    if mc:
        lines.append("")
        lines.append("## migration candidates (delete-ready hand-ports)")
        lines.append(
            f"  count: {mc.get('count', 0)}  ·  "
            f"by-cat: {mc.get('by_category', {})}  ·  "
            f"by-offline-test: {mc.get('by_offline_test', {})}"
        )
        risky = mc.get("append_bug_risk_count", 0)
        if risky:
            lines.append(
                f"  append-bug risk: {risky} candidates need method-name hoist "
                f"into all-types.gc before migration"
            )
        top = mc.get("top", [])
        if top:
            lines.append("  top 10 by readiness score (higher = more ready):")
            for i, c in enumerate(top[:10], 1):
                risk = f" ⚠{c['append_bug_risk_count']}" if c.get("append_bug_risk_count") else ""
                lines.append(
                    f"    {i:>2}. {c.get('score', 0):>6.2f}  "
                    f"[{c.get('category', '?'):>12}]  "
                    f"[{c.get('offline_test', '?'):>7}]  {c['name']}{risk}"
                )
            lines.append(
                f"    (full list: .jakx_watch/migration_candidates.md — "
                f"Agents 1/2 consume when between activation batches)"
            )

    # ===== optional: offline-test split (when jakx corpus exists) =====
    ot = snap.get("offline_test")
    if ot:
        lines.append("")
        lines.append("## offline-test pass (real-clean split)")
        if ot.get("blocked"):
            lines.append(f"  BLOCKED: {ot.get('blocker', 'unknown reason')}")
            lines.append(f"  candidates: {ot.get('candidates')}")
        else:
            greens = ot.get('green', [])
            ambers = ot.get('amber', [])
            lines.append(f"  green (passing):   {len(greens)}")
            lines.append(f"  amber (mismatch):  {len(ambers)}")
            lines.append(f"  candidates:        {ot.get('candidates')}")
            if greens:
                lines.append("  GREEN (shippable — offline-test passes):")
                for n in greens[:20]:
                    lines.append(f"    ✓ {n}")
                if len(greens) > 20:
                    lines.append(f"    ... +{len(greens) - 20} more")
            if ambers:
                lines.append("  AMBER (decomp ok, goalc-compile fails):")
                reasons = ot.get("amber_reasons", {})
                for n in ambers[:10]:
                    r = reasons.get(n, {})
                    reason = r.get("reason", "unknown")
                    form = r.get("form", "")
                    lines.append(f"    ~ {n}: {reason}")
                    if form:
                        lines.append(f"        form: {form}")
                if len(ambers) > 10:
                    lines.append(f"    ... +{len(ambers) - 10} more")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", help="Path to a decompiler log file (default: auto-detect latest large log)")
    ap.add_argument("--no-write", action="store_true", help="Don't write snapshot to history")
    ap.add_argument("--compare", help="Path to a previous snapshot JSON to diff against")
    ap.add_argument("--decomp-out", help=f"Path to decompiler output dir (default: {DEFAULT_DECOMP_OUT})",
                    default=str(DEFAULT_DECOMP_OUT))
    ap.add_argument("--restatus-only", action="store_true",
                    help="Skip measurement; just re-render status.md from latest.json "
                    "(use after offline_test_pass.py / types_drift.py augment the snapshot).")
    args = ap.parse_args()

    if args.restatus_only:
        latest = HISTORY_DIR / "latest.json"
        if not latest.exists():
            print("no latest.json — run measure.py first", file=sys.stderr)
            sys.exit(1)
        snap = json.loads(latest.read_text())
        # Find prev snap for the delta block
        prev = None
        if HISTORY_DIR.exists():
            candidates = sorted(HISTORY_DIR.glob("snap-*.json"), key=lambda p: p.stat().st_mtime)
            want_out = snap.get("decomp_out")
            for c in reversed(candidates):
                try:
                    cand = json.loads(c.read_text())
                except Exception:
                    continue
                if cand.get("digest") == snap.get("digest"):
                    continue
                if cand.get("decomp_out") == want_out:
                    prev = cand
                    break
        status = ROOT / ".jakx_watch" / "status.md"
        body = format_summary_block(snap, prev)
        status.write_text("```\n" + body + "\n```\n")
        print(f"status file re-rendered: {status.relative_to(ROOT)}", file=sys.stderr)
        return

    log_path = Path(args.log).resolve() if args.log else find_latest_log()
    decomp_out = Path(args.decomp_out).resolve()
    snap = build_snapshot(log_path, decomp_out)

    prev = None
    if args.compare:
        prev = json.loads(Path(args.compare).read_text())
    else:
        # Auto-pick most recent snapshot with same decomp_out path, so we don't
        # compare clean-run numbers against accumulated-state numbers.
        if HISTORY_DIR.exists():
            candidates = sorted(HISTORY_DIR.glob("snap-*.json"), key=lambda p: p.stat().st_mtime)
            want_out = snap.get("decomp_out")
            for c in reversed(candidates):
                try:
                    cand = json.loads(c.read_text())
                except Exception:
                    continue
                if cand.get("digest") == snap.get("digest"):
                    continue  # don't compare to self
                if cand.get("decomp_out") == want_out:
                    prev = cand
                    break

    print(format_summary_block(snap, prev))

    if not args.no_write:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        out = HISTORY_DIR / f"snap-{stamp}-{snap['digest']}.json"
        out.write_text(json.dumps(snap, indent=2))
        latest = HISTORY_DIR / "latest.json"
        latest.write_text(json.dumps(snap, indent=2))
        # status.md is the agent-consumable status file. Other Claude sessions
        # cat it each cycle. Keep it structured and non-empty.
        status = ROOT / ".jakx_watch" / "status.md"
        body = format_summary_block(snap, prev)
        if not body.strip() or len(body) < 200:
            body = (
                "ERROR: measurement produced empty output.\n"
                "Fix scripts/jakx_watch/measure.py before relying on this file.\n"
                "---\n" + body
            )
        status.write_text("```\n" + body + "\n```\n")
        print(f"\nsnapshot saved: {out.relative_to(ROOT)}", file=sys.stderr)
        print(f"status file:    {status.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
