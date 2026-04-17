#!/usr/bin/env python3
"""Cluster "Return type mismatch DECLARED vs ACTUAL" WARN entries.

Every mismatch is a stance disagreement between the deftype `:methods`
declaration (in jakx all-types.gc) and what the decompiled body actually
returns. Most are fixable by editing the deftype's `:methods` entry — the body
is usually right (produced by the decompiler from real bytecode), and the
declaration is a guess (often copy-ported from jak3 for a method that jakx
handles differently).

Clusters by:
  * (declared, actual)  — mismatch pattern, useful for batch fixes
  * parent type         — which types' `:methods` blocks need the most edits
  * (type, declared→actual) — specific entry + direction for surgical fixes

Output:
  * Console summary
  * latest.json[return_mismatch_clusters] — persisted for measure.py
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"

RE_MISMATCH = re.compile(
    r"^;; WARN: Return type mismatch (\S+) vs ([\w<>!?:\-\+\*/=]+)\.",
    re.MULTILINE,
)
RE_DEF_METHOD = re.compile(
    r"^;; definition for method (\d+) of type ([\w<>!?:\-\+\*/=]+)",
    re.MULTILINE,
)
RE_DEF_FUNCTION = re.compile(
    r"^;; definition for function ([\w<>!?:\-\+\*/=]+)",
    re.MULTILINE,
)


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def classify_caller(text: str, err_pos: int) -> tuple[str, str]:
    """Return (caller_key, parent_type)."""
    window_start = max(0, err_pos - 4000)
    window = text[window_start:err_pos]
    last_method = None
    for m in RE_DEF_METHOD.finditer(window):
        last_method = (int(m.group(1)), m.group(2), m.start())
    last_function = None
    for m in RE_DEF_FUNCTION.finditer(window):
        last_function = (m.group(1), m.start())
    candidates = []
    if last_method:
        candidates.append(("method", last_method))
    if last_function:
        candidates.append(("function", last_function))
    if not candidates:
        return ("unknown", "")
    candidates.sort(key=lambda c: -c[1][-1])
    kind, payload = candidates[0]
    if kind == "method":
        mnum, tp, _ = payload
        return (f"{tp}::method-{mnum}", tp)
    return (f"fn:{payload[0]}", "")


def scan_file(path: Path) -> list[tuple[str, str, str, str]]:
    """Return list of (caller, parent_type, declared, actual)."""
    text = path.read_text(errors="replace")
    out = []
    for m in RE_MISMATCH.finditer(text):
        declared, actual = m.group(1), m.group(2)
        caller, parent = classify_caller(text, m.start())
        out.append((caller, parent, declared, actual))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decomp-out", help="Decomp output dir (default: auto)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"decomp dir missing: {decomp_dir}", file=sys.stderr)
        return 1

    pattern_counts: collections.Counter = collections.Counter()
    parent_counts: collections.Counter = collections.Counter()
    specific_counts: collections.Counter = collections.Counter()  # (type, decl, actual)
    file_counts: collections.Counter = collections.Counter()
    total = 0

    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        rows = scan_file(fp)
        if not rows:
            continue
        fname = fp.name[: -len("_disasm.gc")]
        file_counts[fname] = len(rows)
        for caller, parent, declared, actual in rows:
            total += 1
            pattern_counts[(declared, actual)] += 1
            if parent:
                parent_counts[parent] += 1
                specific_counts[(parent, declared, actual)] += 1

    print(f"return-mismatch WARNs: {total}")
    print()
    print("top 10 (declared, actual) patterns (cluster-fix candidates):")
    for (decl, actual), c in pattern_counts.most_common(10):
        print(f"  {c:>4}  declared={decl:<12} actual={actual}")
    print()
    print("top 15 parent types (batch-edit :methods block in all-types.gc):")
    for tp, c in parent_counts.most_common(15):
        print(f"  {c:>4}  {tp}")
    print()
    print("top 15 specific entries (type, declared→actual):")
    for (tp, decl, actual), c in specific_counts.most_common(15):
        print(f"  {c:>4}  {tp}  ({decl} → {actual})")
    print()
    print("top 10 offender files:")
    for name, c in file_counts.most_common(10):
        print(f"  {c:>4}  {name}")

    if not args.no_write and LATEST.exists():
        try:
            snap = json.loads(LATEST.read_text())
        except Exception as exc:
            print(f"warn: could not parse latest.json: {exc}", file=sys.stderr)
            return 0
        snap["return_mismatch_clusters"] = {
            "total": total,
            "top_patterns": [
                {"declared": d, "actual": a, "count": c}
                for (d, a), c in pattern_counts.most_common(10)
            ],
            "top_parent_types": parent_counts.most_common(15),
            "top_specific": [
                {"type": t, "declared": d, "actual": a, "count": c}
                for (t, d, a), c in specific_counts.most_common(15)
            ],
            "top_files": file_counts.most_common(10),
        }
        LATEST.write_text(json.dumps(snap, indent=2))
        print(f"\npersisted into {LATEST.relative_to(ROOT)}[return_mismatch_clusters]",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
