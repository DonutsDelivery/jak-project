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

Also writes `.jakx_watch/return_mismatch_queue.md` with exact method numbers
and all-types.gc line references for Agent 1's surgical sweep.

Output:
  * Console summary
  * latest.json[return_mismatch_clusters] — persisted for measure.py
  * .jakx_watch/return_mismatch_queue.md — actionable per-method fix list
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
CURRENT_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
QUEUE_MD = ROOT / ".jakx_watch" / "return_mismatch_queue.md"

RE_DEFTYPE = re.compile(r"^\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(")
RE_METHODS_OPEN = re.compile(r"^\s*\(:methods\b")
# Capture method name, return type, and the vtable index from the trailing ";; N" comment.
RE_METHOD_LINE = re.compile(
    r"^\s*\(([\w<>!?:\-\+\*/=]+)\s+\([^)]*\)\s+([\w<>!?:\-\+\*/=]+)\)"
    r".*?;;\s*(\d+)"  # trailing vtable index
)

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


def build_method_line_index(types_path: Path) -> dict[tuple[str, int], tuple[int, str]]:
    """Parse all-types.gc and return {(type_name, method_num): (line_no, line_text)}.

    Method numbers are 0-indexed from the FIRST entry in the :methods block
    (matching the decompiler's method-N numbering which starts after inherited
    methods — but here we use the sequential position in the block as a proxy).

    Actually the decompiler method number = position in (:methods ...) block
    starting from 0 for the first entry in that specific type's :methods block.
    For inherited methods the parent's method-N stays the same, so we only
    track methods defined in this specific deftype.
    """
    index: dict[tuple[str, int], tuple[int, str]] = {}
    if not types_path.exists():
        return index

    lines = types_path.read_text(errors="replace").splitlines()
    current_type: str | None = None
    in_methods = False
    method_idx = 0
    paren_depth = 0

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith(";;") or stripped.startswith(";"):
            continue

        # Detect deftype start (not commented)
        dm = RE_DEFTYPE.match(stripped)
        if dm and "deftype" in stripped and not stripped.startswith(";;"):
            current_type = dm.group(1)
            in_methods = False
            method_idx = 0
            paren_depth = 0

        if current_type is None:
            continue

        # Detect :methods block open
        if RE_METHODS_OPEN.match(line):
            in_methods = True
            method_idx = 0
            continue

        if in_methods:
            # Track nesting so we know when :methods block ends
            for ch in stripped:
                if ch == "(":
                    paren_depth += 1
                elif ch == ")":
                    paren_depth -= 1

            if paren_depth < 0:
                in_methods = False
                paren_depth = 0
                continue

            # Method entry line: (method-name (args) return-type) ;; N
            mm = RE_METHOD_LINE.match(line)
            if mm:
                vtable_idx = int(mm.group(3))
                index[(current_type, vtable_idx)] = (lineno, line.rstrip())
                method_idx += 1

    return index


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def classify_caller(text: str, err_pos: int) -> tuple[str, str, int | None]:
    """Return (caller_key, parent_type, method_num_or_None)."""
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
        return ("unknown", "", None)
    candidates.sort(key=lambda c: -c[1][-1])
    kind, payload = candidates[0]
    if kind == "method":
        mnum, tp, _ = payload
        return (f"{tp}::method-{mnum}", tp, mnum)
    return (f"fn:{payload[0]}", "", None)


def scan_file(path: Path) -> list[tuple[str, str, str, str, int | None]]:
    """Return list of (caller, parent_type, declared, actual, method_num).

    Decompiler WARN format (decompiler/types2/types2.cpp:705) is:
        "Return type mismatch {last_type} vs {declared}"
    i.e. group 1 = actual (what body returns), group 2 = declared (:methods).
    """
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    out = []
    for m in RE_MISMATCH.finditer(text):
        actual, declared = m.group(1), m.group(2)
        caller, parent, mnum = classify_caller(text, m.start())
        out.append((caller, parent, declared, actual, mnum))
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
    # method-level: {type: {method_num: [(declared, actual)]}}
    method_entries: dict[str, dict[int, list[tuple[str, str]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    total = 0

    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        rows = scan_file(fp)
        if not rows:
            continue
        fname = fp.name[: -len("_disasm.gc")]
        file_counts[fname] = len(rows)
        for caller, parent, declared, actual, mnum in rows:
            total += 1
            pattern_counts[(declared, actual)] += 1
            if parent:
                parent_counts[parent] += 1
                specific_counts[(parent, declared, actual)] += 1
                if mnum is not None:
                    method_entries[parent][mnum].append((declared, actual))

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

    # Write return_mismatch_queue.md with per-method detail
    if not args.no_write:
        method_line_index = build_method_line_index(CURRENT_TYPES)
        _write_queue_md(
            total, pattern_counts, parent_counts, specific_counts,
            method_entries, method_line_index
        )

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


def _write_queue_md(
    total: int,
    pattern_counts: collections.Counter,
    parent_counts: collections.Counter,
    specific_counts: collections.Counter,
    method_entries: dict,
    method_line_index: dict,
) -> None:
    lines = [
        "# jakx return-mismatch queue",
        "",
        f"_source: scripts/jakx_watch/return_mismatch_scan.py  ·  total WARNs: {total}_",
        "",
        "Each entry is a `:methods` declaration in `all-types.gc` that disagrees "
        "with what the decompiled body actually returns. Fix by editing the return "
        "type in the `:methods` block.",
        "",
        "## Top patterns (batch-fix targets)",
        "",
        "| declared | actual | count | action |",
        "|----------|--------|------:|--------|",
    ]
    for (decl, actual), c in pattern_counts.most_common(15):
        action = f"change `{decl}` → `{actual}` in `:methods`"
        lines.append(f"| `{decl}` | `{actual}` | {c} | {action} |")

    lines += [
        "",
        "## Per-type method detail (top 20 types by count)",
        "",
        "For each type: the specific method-N entries that need fixing, "
        "with the exact all-types.gc line shown.",
        "",
    ]

    for tp, count in parent_counts.most_common(20):
        lines.append(f"### `{tp}` ({count} WARNs)")
        lines.append("")
        lines.append("| method-N | declared | actual | all-types.gc line | fix |")
        lines.append("|----------|----------|--------|-------------------|-----|")
        method_map = method_entries.get(tp, {})
        for mnum in sorted(method_map.keys()):
            pairs = method_map[mnum]
            # Most common (declared, actual) for this method
            pair_counter = collections.Counter(pairs)
            (decl, actual), _ = pair_counter.most_common(1)[0]
            line_info = method_line_index.get((tp, mnum))
            if line_info:
                lineno, line_text = line_info
                # Extract the part we'd change
                line_display = line_text.strip()[:80]
                lines.append(
                    f"| method-{mnum} | `{decl}` | `{actual}` | "
                    f"L{lineno}: `{line_display}` | `{decl}`→`{actual}` |"
                )
            else:
                lines.append(
                    f"| method-{mnum} | `{decl}` | `{actual}` | _(not found)_ | "
                    f"`{decl}`→`{actual}` |"
                )
        lines.append("")

    lines += [
        "## How to use",
        "",
        "1. Pick the highest-count type from the list above.",
        "2. Open `decompiler/config/jakx/all-types.gc` at the line shown.",
        "3. Change the return type in the method entry from declared → actual.",
        "4. Re-run `bash scripts/jakx_watch/run.sh` to check for regressions.",
        "5. Watch `return_mismatch WARNs` in status.md drop.",
        "",
        "**Note**: Before flipping method-9 (asize-of) or child overrides, check "
        "that parent and all children are consistent — a parent flip propagates "
        "a constraint that child overrides must also satisfy.",
    ]

    QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {QUEUE_MD.relative_to(ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
