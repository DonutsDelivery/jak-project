#!/usr/bin/env python3
"""Cluster "Called a function, but we do not know its type" errors by caller.

Scans decompiler_out/jakx (or the private jakx_watch decomp_out) and for each
`;; ERROR: failed type prop at N: Called a function, but we do not know its type`
occurrence, walks BACKWARD to the nearest `;; definition for ...` comment to
determine the containing function. Clusters the errors by:

  * CALLER KEY — `fn:<name>` or `<type>::method-<N>`
  * PARENT TYPE (for method callers) — groups all methods of one type together

If one type accounts for many errors, its method declarations in
`decompiler/config/jakx/all-types.gc` `:methods` block probably need signature
fixes (return type / argument types) so type propagation can resolve the jr-t9
callee.

Output:
  * Console summary (top clusters)
  * latest.json[unknown_call_clusters] — persisted for measure.py to surface
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

RE_UNKNOWN_CALL = re.compile(
    r"^;; ERROR: failed type prop at (\d+): Called a function, but we do not know its type",
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
RE_DEF_SYMBOL = re.compile(
    r"^;; definition for symbol ([\w<>!?:\-\+\*/=\*]+)",
    re.MULTILINE,
)


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def classify_caller(text: str, err_pos: int) -> tuple[str, str]:
    """Walk backward from err_pos to find enclosing definition marker.

    Returns (caller_key, parent_type). caller_key is what we cluster on:
      * f"{TYPE}::method-{N}" when the caller is a method
      * f"fn:{NAME}"          when the caller is a top-level function
      * f"sym:{NAME}"         when only a symbol definition precedes (rare)
    parent_type is the type name when known, or "" otherwise.
    """
    window_start = max(0, err_pos - 4000)
    window = text[window_start:err_pos]
    # Find ALL definition markers in this window, take the last one.
    last_method = None
    for m in RE_DEF_METHOD.finditer(window):
        last_method = (int(m.group(1)), m.group(2), m.start())
    last_function = None
    for m in RE_DEF_FUNCTION.finditer(window):
        last_function = (m.group(1), m.start())
    last_symbol = None
    for m in RE_DEF_SYMBOL.finditer(window):
        last_symbol = (m.group(1), m.start())

    # Pick whichever marker is latest in the window (closest before error).
    candidates = []
    if last_method:
        candidates.append(("method", last_method))
    if last_function:
        candidates.append(("function", last_function))
    if last_symbol:
        candidates.append(("symbol", last_symbol))
    if not candidates:
        return ("unknown", "")
    candidates.sort(key=lambda c: -c[1][-1])  # highest offset = most recent
    kind, payload = candidates[0]
    if kind == "method":
        mnum, tp, _ = payload
        return (f"{tp}::method-{mnum}", tp)
    if kind == "function":
        name, _ = payload
        return (f"fn:{name}", "")
    name, _ = payload
    return (f"sym:{name}", "")


def scan_file(path: Path) -> list[tuple[str, str, int]]:
    """Return list of (caller_key, parent_type, pos_in_file_errmsg_N) per error."""
    text = path.read_text(errors="replace")
    out = []
    for m in RE_UNKNOWN_CALL.finditer(text):
        caller, parent = classify_caller(text, m.start())
        err_n = int(m.group(1))
        out.append((caller, parent, err_n))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decomp-out", help="Decomp output dir (default: auto)")
    ap.add_argument("--no-write", action="store_true", help="Don't update latest.json")
    args = ap.parse_args()

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"decomp dir missing: {decomp_dir}", file=sys.stderr)
        return 1

    caller_counts: collections.Counter = collections.Counter()
    type_counts: collections.Counter = collections.Counter()
    file_counts: collections.Counter = collections.Counter()
    per_file_samples: dict[str, list[tuple[str, int]]] = {}

    total = 0
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        rows = scan_file(fp)
        if not rows:
            continue
        fname = fp.name[: -len("_disasm.gc")]
        file_counts[fname] = len(rows)
        samples: list[tuple[str, int]] = []
        for caller, parent, err_n in rows:
            caller_counts[caller] += 1
            if parent:
                type_counts[parent] += 1
            samples.append((caller, err_n))
            total += 1
        per_file_samples[fname] = samples[:8]

    print(f"unknown-call errors: {total} across {len(file_counts)} files")
    print()
    print("top 15 caller keys (most errors per caller — signature fix = cluster fix):")
    for k, v in caller_counts.most_common(15):
        print(f"  {v:>4}  {k}")
    print()
    print("top 15 parent types (method-level clustering):")
    for k, v in type_counts.most_common(15):
        print(f"  {v:>4}  {k}")
    print()
    print("top 15 offender files:")
    for name, c in file_counts.most_common(15):
        print(f"  {c:>4}  {name}")

    if not args.no_write and LATEST.exists():
        try:
            snap = json.loads(LATEST.read_text())
        except Exception as exc:
            print(f"warn: could not parse latest.json: {exc}", file=sys.stderr)
            return 0
        snap["unknown_call_clusters"] = {
            "total": total,
            "files": len(file_counts),
            "top_callers": caller_counts.most_common(20),
            "top_parent_types": type_counts.most_common(15),
            "top_files": file_counts.most_common(15),
        }
        LATEST.write_text(json.dumps(snap, indent=2))
        print(f"\npersisted into {LATEST.relative_to(ROOT)}[unknown_call_clusters]",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
