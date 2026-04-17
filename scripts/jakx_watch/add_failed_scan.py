#!/usr/bin/env python3
"""Cluster "add failed: LHS <integer N>" type-prop errors.

Two distinct failure modes surface as this error:

  1. `add failed: <uninitialized> <integer N>`
     — a register is used in an integer add before it's been typed. Nearly
     always means the enclosing method's arg signatures aren't declared in
     `all-types.gc` `:methods` (so a0..a3 arrive untyped). Fix the signature.

  2. `add failed: TYPE <integer N>`
     — TYPE is known but TYPE + N can't be resolved. Either TYPE's layout
     doesn't declare a field at offset N, or the decompiler doesn't know the
     result type of that pointer-arithmetic. Fix: declare the field in the
     deftype, or add a type_casts.jsonc entry.

Output:
  * Console summary: top uninit callers, top typed (TYPE, offset) pairs
  * latest.json[add_failed_clusters] — persisted for measure.py
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

RE_ADD_FAILED = re.compile(
    r"^;; ERROR: failed type prop at (\d+): add failed: (\S+|<uninitialized>) <integer (-?\d+)>",
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


def classify_caller(text: str, err_pos: int) -> str:
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
        return "unknown"
    candidates.sort(key=lambda c: -c[1][-1])
    kind, payload = candidates[0]
    if kind == "method":
        return f"{payload[1]}::method-{payload[0]}"
    return f"fn:{payload[0]}"


def scan_file(path: Path) -> list[tuple[str, str, int]]:
    """Return list of (caller, lhs_type_or_uninit, offs)."""
    text = path.read_text(errors="replace")
    out = []
    for m in RE_ADD_FAILED.finditer(text):
        lhs = m.group(2)
        offs = int(m.group(3))
        caller = classify_caller(text, m.start())
        out.append((caller, lhs, offs))
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

    uninit_callers: collections.Counter = collections.Counter()
    typed_pairs: collections.Counter = collections.Counter()  # (TYPE, offs) -> count
    typed_types: collections.Counter = collections.Counter()  # TYPE -> count
    file_counts: collections.Counter = collections.Counter()
    total = 0
    uninit_total = 0
    typed_total = 0

    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        rows = scan_file(fp)
        if not rows:
            continue
        fname = fp.name[: -len("_disasm.gc")]
        file_counts[fname] = len(rows)
        for caller, lhs, offs in rows:
            total += 1
            if lhs == "<uninitialized>":
                uninit_total += 1
                uninit_callers[caller] += 1
            else:
                typed_total += 1
                typed_pairs[(lhs, offs)] += 1
                typed_types[lhs] += 1

    print(f"add-failed errors: {total} (uninit={uninit_total}, typed={typed_total})")
    print()
    print("top 15 uninit callers (declare :methods arg types in all-types.gc):")
    for caller, c in uninit_callers.most_common(15):
        print(f"  {c:>4}  {caller}")
    print()
    print("top 15 typed (TYPE, offset) pairs (add field or add type_casts entry):")
    for (tp, offs), c in typed_pairs.most_common(15):
        print(f"  {c:>4}  {tp} + {offs}")
    print()
    print("top 10 typed LHS types (aggregate across offsets):")
    for tp, c in typed_types.most_common(10):
        print(f"  {c:>4}  {tp}")
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
        snap["add_failed_clusters"] = {
            "total": total,
            "uninit_total": uninit_total,
            "typed_total": typed_total,
            "top_uninit_callers": uninit_callers.most_common(15),
            "top_typed_pairs": [
                {"type": tp, "offs": offs, "count": c}
                for (tp, offs), c in typed_pairs.most_common(15)
            ],
            "top_typed_types": typed_types.most_common(10),
            "top_files": file_counts.most_common(10),
        }
        LATEST.write_text(json.dumps(snap, indent=2))
        print(f"\npersisted into {LATEST.relative_to(ROOT)}[add_failed_clusters]",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
