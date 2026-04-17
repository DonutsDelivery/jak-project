#!/usr/bin/env python3
"""Cluster "Could not figure out load" errors by load-shape + caller context.

Scans decompiler output for
  ;; ERROR: failed type prop at N: Could not figure out load: (set! DST (OP ...))
and groups them by LOAD SHAPE — a canonical representation of the load form:

  * (OP REG)            — zero-offset load from a pointer
  * (OP (+ REG OFFS))   — struct-field load at OFFS
  * (OP (+ gp OFFS))    — global-data load (usually a *symbol* reference)
  * (OP (+ REG -OFFS))  — negative-offset / below-struct-base load

For struct-field loads the scanner tries to identify the source register's
type from the nearest earlier `;; definition for method N of type TYPE` or
`;; definition for function FN` so we can hint which type's field needs
declaring in all-types.gc (or which type_casts.jsonc entry is missing).

Output:
  * Console summary (top shapes + per-caller clusters)
  * latest.json[load_offset_clusters] for measure.py to surface
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

# Matches any "Could not figure out load" line. Captures the inner form so we
# can shape-canonicalize it (offsets kept intact for cluster analysis).
RE_LOAD_ERR = re.compile(
    r"^;; ERROR: failed type prop at (\d+): "
    r"Could not figure out load: \(set! (\S+) (\([^\n]+\))\)$",
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

# Load-form canonicalizer:
#   (l.wu (+ s5 60))     -> shape="struct", reg="s5", op="l.wu", offs=60
#   (l.wu (+ gp 4))      -> shape="global", reg="gp", op="l.wu", offs=4
#   (l.wu (+ s5 -120))   -> shape="struct-neg", ...
#   (l.wu a0)            -> shape="deref",  reg="a0", op="l.wu", offs=0
#   (l.h (+ v1 8))       -> op="l.h" etc.
RE_LOAD_WITH_OFFS = re.compile(
    r"^\((l\.\w+)\s+\(\+\s+(\S+)\s+(-?\d+)\)\)$"
)
RE_LOAD_DEREF = re.compile(r"^\((l\.\w+)\s+(\S+)\)$")

# Registers we classify specially — everything else is a temp (likely holds a
# typed pointer that the decompiler failed to resolve).
GLOBAL_REGS = {"gp", "fp", "sp"}


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def canonicalize_load(inner: str) -> tuple[str, str, str, int]:
    """Return (shape, op, reg, offs). shape ∈ struct, struct-neg, global, deref."""
    m = RE_LOAD_WITH_OFFS.match(inner)
    if m:
        op, reg, offs_str = m.group(1), m.group(2), int(m.group(3))
        if reg in GLOBAL_REGS:
            return ("global", op, reg, offs_str)
        shape = "struct-neg" if offs_str < 0 else "struct"
        return (shape, op, reg, offs_str)
    m = RE_LOAD_DEREF.match(inner)
    if m:
        op, reg = m.group(1), m.group(2)
        return ("deref", op, reg, 0)
    return ("other", "?", "?", 0)


def classify_caller(text: str, err_pos: int) -> str:
    """Walk backward from err_pos to find enclosing defmethod/defun label."""
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


def scan_file(path: Path) -> list[tuple[str, str, str, str, int]]:
    """Return list of (caller, shape, op, reg, offs)."""
    text = path.read_text(errors="replace")
    out = []
    for m in RE_LOAD_ERR.finditer(text):
        inner = m.group(3)
        shape, op, reg, offs = canonicalize_load(inner)
        caller = classify_caller(text, m.start())
        out.append((caller, shape, op, reg, offs))
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

    shape_counts: collections.Counter = collections.Counter()
    offset_counts: collections.Counter = collections.Counter()
    caller_offset: collections.Counter = collections.Counter()
    caller_counts: collections.Counter = collections.Counter()
    file_counts: collections.Counter = collections.Counter()
    global_offset_counts: collections.Counter = collections.Counter()

    total = 0
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        rows = scan_file(fp)
        if not rows:
            continue
        fname = fp.name[: -len("_disasm.gc")]
        file_counts[fname] = len(rows)
        for caller, shape, op, reg, offs in rows:
            shape_counts[shape] += 1
            if shape in ("struct", "struct-neg"):
                offset_counts[offs] += 1
                caller_offset[(caller, offs)] += 1
                caller_counts[caller] += 1
            elif shape == "global":
                global_offset_counts[offs] += 1
                caller_counts[caller] += 1
            else:
                caller_counts[caller] += 1
            total += 1

    print(f"load-offset errors: {total}")
    print(f"shapes: {dict(shape_counts)}")
    print()
    print("top 15 struct offsets (positive+negative — fix field at offset → cluster clear):")
    for offs, c in offset_counts.most_common(15):
        print(f"  {c:>4}  offs={offs}")
    print()
    print("top 10 global offsets (gp+OFFS — unresolved *symbol* or global *var* references):")
    for offs, c in global_offset_counts.most_common(10):
        print(f"  {c:>4}  offs={offs}")
    print()
    print("top 15 (caller, offset) pairs (same field read from same function — single fix):")
    for (caller, offs), c in caller_offset.most_common(15):
        print(f"  {c:>4}  {caller}  @+{offs}")
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
        snap["load_offset_clusters"] = {
            "total": total,
            "shapes": dict(shape_counts),
            "top_struct_offsets": offset_counts.most_common(15),
            "top_global_offsets": global_offset_counts.most_common(10),
            "top_caller_offset_pairs": [
                {"caller": c, "offs": o, "count": n}
                for (c, o), n in caller_offset.most_common(15)
            ],
            "top_files": file_counts.most_common(10),
        }
        LATEST.write_text(json.dumps(snap, indent=2))
        print(f"\npersisted into {LATEST.relative_to(ROOT)}[load_offset_clusters]",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
