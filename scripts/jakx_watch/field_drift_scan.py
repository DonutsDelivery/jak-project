#!/usr/bin/env python3
"""Field-drift prioritizer — rank the 933 drifted deftypes by actionability.

types_drift.py reports "933 types have different bodies in regen vs current"
but gives no per-type detail. This scanner fills the gap:

For each drifted type it computes:
  - WHAT changed: size-assert / method-count-assert / field count / methods block
  - WHO references it: failing-file count (split-failed + real-partial w/ errors)
  - HOW HARD to fix: complexity tier
    clean-methods — only :methods return types differ (Agent 1's sweep target)
    size-change   — :size-assert or :method-count-assert differ (struct layout change)
    field-change  — field definitions differ (surgical)
    multi         — two or more of the above

Scoring (higher = higher priority for Agent 1 to update):
  score = 4·failing_refs + 1·all_refs − complexity_penalty

Output:
  .jakx_watch/field_drift_queue.md   — human-readable top-30
  latest.json["field_drift_queue"]   — compact for measure.py status section
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
QUEUE_MD = ROOT / ".jakx_watch" / "field_drift_queue.md"

RE_SIZE_ASSERT = re.compile(r":size-assert\s+(-?\d+)")
RE_METHOD_COUNT = re.compile(r":method-count-assert\s+(\d+)")
RE_METHODS_BLOCK = re.compile(r"\(:methods\b(.*?)\n\s*\)", re.DOTALL)
RE_METHOD_ENTRY = re.compile(r"\(\s*(\S+)\s+\(")
# Field lines have :offset-assert; method lines don't.
RE_FIELD_COUNT = re.compile(r":offset-assert")
RE_PARENT_SIZE = re.compile(r"\(deftype\s+\S+\s+\((\S+)\)")

# Reuse the block-aware deftype parser from types_drift.py.
RE_DEFTYPE_START = re.compile(
    r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)\s*"
)


def parse_deftypes(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    lines = text.splitlines()
    in_block = [False] * len(lines)
    block = False
    for idx, line in enumerate(lines):
        if "#|" in line and not block:
            block = True
            in_block[idx] = True
        elif block:
            in_block[idx] = True
            if "|#" in line:
                block = False
        if "#|" in line and "|#" in line.split("#|", 1)[1]:
            block = False

    i = 0
    while i < len(lines):
        line = lines[i]
        m = RE_DEFTYPE_START.match(line)
        if not m:
            i += 1
            continue
        name = m.group(1)
        commented = ";;" in line[: line.find("(deftype")]
        block_commented = in_block[i]
        depth = 0
        start_i = i
        body_lines = []
        while i < len(lines):
            raw = lines[i]
            s = re.sub(r"^\s*;;\s?", "", raw) if commented else raw
            body_lines.append(raw)
            for ch in s:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            if depth <= 0:
                i += 1
                break
            i += 1
        body = "\n".join(body_lines)
        prev = out.get(name)
        this_active = not commented and not block_commented
        prev_active = prev and not prev["commented"] and not prev.get("block_commented", False)
        if prev is None or (this_active and not prev_active):
            out[name] = {
                "commented": commented,
                "block_commented": block_commented,
                "body": body,
                "first_line": start_i + 1,
            }
    return out


def extract_struct_info(body: str) -> dict:
    size_m = RE_SIZE_ASSERT.search(body)
    mc_m = RE_METHOD_COUNT.search(body)
    methods_m = RE_METHODS_BLOCK.search(body)
    method_entries = []
    if methods_m:
        mblock = methods_m.group(1)
        method_entries = RE_METHOD_ENTRY.findall(mblock)
    field_count = len(RE_FIELD_COUNT.findall(body))
    parent_m = RE_PARENT_SIZE.search(body)
    return {
        "size": int(size_m.group(1)) if size_m else None,
        "method_count": int(mc_m.group(1)) if mc_m else None,
        "method_names": method_entries,
        "field_count": field_count,
        "parent": parent_m.group(1) if parent_m else None,
    }


def classify_drift(cur_info: dict, reg_info: dict) -> tuple[str, list[str]]:
    changes = []
    if cur_info["size"] != reg_info["size"] and reg_info["size"] is not None:
        changes.append(f"size {cur_info['size']}→{reg_info['size']}")
    if cur_info["method_count"] != reg_info["method_count"] and reg_info["method_count"] is not None:
        changes.append(f"method-count {cur_info['method_count']}→{reg_info['method_count']}")
    if cur_info["field_count"] != reg_info["field_count"]:
        changes.append(f"fields {cur_info['field_count']}→{reg_info['field_count']}")

    cur_names = cur_info["method_names"]
    reg_names = reg_info["method_names"]
    if set(cur_names) != set(reg_names):
        new_m = set(reg_names) - set(cur_names)
        rem_m = set(cur_names) - set(reg_names)
        changes.append(f"methods +{len(new_m)}/-{len(rem_m)}")
    elif cur_names == reg_names and not changes:
        # Same method names, same structure — body-only diff (return/arg types)
        changes.append("methods-return-types-only")

    if not changes:
        changes.append("other")

    has_layout = any("size" in c or "fields" in c or "method-count" in c for c in changes)
    has_methods = any("method" in c for c in changes)
    n_change_types = sum([has_layout, has_methods, len(changes) > 2])

    if n_change_types > 1:
        tier = "multi"
    elif has_layout:
        tier = "size-change"
    elif has_methods and "methods-return-types-only" in changes:
        tier = "clean-methods"
    elif has_methods:
        tier = "methods-restructure"
    else:
        tier = "other"

    return tier, changes


COMPLEXITY_PENALTY = {
    "clean-methods": 0,
    "methods-restructure": 4,
    "size-change": 8,
    "multi": 12,
    "other": 3,
}


def build_type_ref_index(decomp_dir: Path) -> dict[str, list[str]]:
    """Scan decomp output and return {type_name: [file_stems_that_reference_it]}.

    Uses a broad match: any word-boundary occurrence of the name. This slightly
    over-counts but is fast (single pass per file).
    """
    # Collect all names from the current all-types to build a target set.
    # We only index the ones that appear in the drift list.
    if not decomp_dir.exists():
        return {}

    # Build inverted index: type → files
    ref_index: dict[str, list[str]] = collections.defaultdict(list)
    LISP_WORD = r"(?<![A-Za-z0-9_\-!?<>*+=/])(?!-)"  # negative lookbehind

    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        stem = fp.name[: -len("_disasm.gc")]
        text = fp.read_text(errors="replace")
        # Collect all identifiers that look like type names (hyphenated lowercase words)
        # and add them to a set per file. We'll intersect with drift_names later.
        mentioned: set[str] = set(
            re.findall(r"[a-z][a-z0-9\-!?<>*/]*(?:-[a-z0-9!?<>*/]+)+", text)
        )
        mentioned |= set(re.findall(r"[a-z][a-z0-9!?<>*/]{2,}", text))
        for name in mentioned:
            ref_index[name].append(stem)
    return ref_index


def pick_decomp_dir() -> Path:
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists() and any(p.glob("*_disasm.gc")):
            return p
    return DECOMP_PRIMARY


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", default=str(CURRENT_TYPES))
    ap.add_argument("--regen", default=None, help="path to new-all-types.gc (default: auto)")
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    current_path = Path(args.current)
    if args.regen:
        regen_path = Path(args.regen)
    else:
        decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
        regen_path = decomp_dir / "new-all-types.gc"
    if not regen_path.exists():
        print(f"regen not found: {regen_path}", file=sys.stderr)
        print("Run decomp with generate_all_types:true first (run.sh does this).")
        return 1

    print(f"parsing {current_path.name}...")
    cur = parse_deftypes(current_path.read_text(errors="replace"))
    print(f"parsing {regen_path.name}...")
    reg = parse_deftypes(regen_path.read_text(errors="replace"))

    cur_active = {n: v for n, v in cur.items()
                  if not v["commented"] and not v.get("block_commented", False)}
    # Use all regen types (matching types_drift.py's drift computation).
    reg_all = reg  # includes commented types in regen

    import hashlib
    def digest(body: str) -> str:
        return hashlib.sha1(re.sub(r"\s+", " ", body).encode()).hexdigest()[:10]

    drift_names = [
        n for n in sorted(cur_active.keys() & reg_all.keys())
        if digest(cur_active[n]["body"]) != digest(reg_all[n]["body"])
    ]
    print(f"field-drift types: {len(drift_names)}")

    # Build reference index from decomp output
    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    print(f"scanning decomp output: {decomp_dir}...")
    ref_index = build_type_ref_index(decomp_dir)

    # Pull per_file from latest.json for bucket classification
    per_file: dict = {}
    if LATEST.exists():
        try:
            snap = json.loads(LATEST.read_text())
            per_file = snap.get("per_file", {})
        except Exception:
            pass
    failing_files = {
        name for name, info in per_file.items()
        if info.get("category") in ("split-failed", "real-partial")
        and (info.get("failed", 0) + info.get("error", 0)) > 0
    }

    # Score each drifted type
    results = []
    for name in drift_names:
        cur_info = extract_struct_info(cur_active[name]["body"])
        reg_info = extract_struct_info(reg_all[name]["body"])
        tier, changes = classify_drift(cur_info, reg_info)

        all_refs = ref_index.get(name, [])
        failing_refs = [f for f in all_refs if f in failing_files]

        score = (
            4 * len(failing_refs)
            + 1 * len(all_refs)
            - COMPLEXITY_PENALTY[tier]
        )

        results.append({
            "name": name,
            "tier": tier,
            "changes": changes,
            "failing_refs": len(failing_refs),
            "all_refs": len(all_refs),
            "score": round(score, 1),
            "cur_size": cur_info["size"],
            "reg_size": reg_info["size"],
            "cur_mc": cur_info["method_count"],
            "reg_mc": reg_info["method_count"],
            "cur_fields": cur_info["field_count"],
            "reg_fields": reg_info["field_count"],
            "parent": cur_info["parent"] or reg_info["parent"],
            "cur_line": cur_active[name]["first_line"],
        })

    results.sort(key=lambda r: -r["score"])

    # Tally by tier
    tier_counts = collections.Counter(r["tier"] for r in results)
    print(f"\ntier breakdown: {dict(tier_counts)}")
    print(f"top {min(args.top, len(results))} by score:")
    for r in results[:15]:
        changes_str = "; ".join(r['changes'][:2])
        print(
            f"  {r['score']:>6.1f}  {r['tier']:<20}  {r['name']:<35}  "
            f"fref={r['failing_refs']}  aref={r['all_refs']}  {changes_str}"
        )

    if args.no_write:
        return 0

    # Write markdown
    QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# jakx field-drift queue",
        "",
        f"_source: scripts/jakx_watch/field_drift_scan.py  ·  "
        f"drifted: {len(drift_names)}  ·  "
        f"tiers: {dict(tier_counts)}_",
        "",
        "933 deftypes are **active in both** current `all-types.gc` and the decompiler regen, "
        "but their **bodies differ**. Updating these lets the decompiler emit better output "
        "for the real-partial files that reference them.",
        "",
        "Complexity tiers:",
        "- **clean-methods** — only `:methods` return/arg types differ (Agent 1's sweep target; lowest effort)",
        "- **field-change** — field definitions differ (requires deftype surgery)",
        "- **size-change** — `:size-assert` or `:method-count-assert` changed (C++ struct layout change)",
        "- **multi** — two or more of the above",
        "",
        "Score = 4·failing_refs + 1·all_refs − complexity_penalty",
        "",
        "| # | score | tier | type | fref | aref | parent | changes |",
        "|---|------:|------|------|-----:|-----:|--------|---------|",
    ]
    for i, r in enumerate(results[:args.top], 1):
        changes_str = "; ".join(r["changes"][:2])
        lines.append(
            f"| {i} | {r['score']} | {r['tier']} | `{r['name']}` | "
            f"{r['failing_refs']} | {r['all_refs']} | "
            f"`{r['parent'] or '?'}` | {changes_str} |"
        )
    lines.append("")
    lines.append("## detail")
    for r in results[:15]:
        lines.append("")
        lines.append(
            f"### `{r['name']}` (score={r['score']}, tier={r['tier']}, "
            f"line={r['cur_line']})"
        )
        lines.append("")
        lines.append(f"- parent: `{r['parent'] or '?'}`")
        lines.append(f"- size: `{r['cur_size']}` → `{r['reg_size']}`")
        lines.append(f"- method-count: `{r['cur_mc']}` → `{r['reg_mc']}`")
        lines.append(f"- fields: `{r['cur_fields']}` → `{r['reg_fields']}`")
        lines.append(f"- changes: {'; '.join(r['changes'])}")
        lines.append(f"- failing refs: {r['failing_refs']}  all refs: {r['all_refs']}")
    lines.append("")
    lines.append("## How to use")
    lines.append("")
    lines.append("1. Pick the highest-score **clean-methods** row.")
    lines.append("2. Open `all-types.gc` at the line shown.")
    lines.append("3. Compare the `:methods` block against the regen (`new-all-types.gc`) and align return types.")
    lines.append("4. For **size-change** or **field-change** rows: use `emit_stub.py NAME` to get the regen body.")
    lines.append("5. Re-run `bash scripts/jakx_watch/run.sh`; watch failing_refs drop.")

    QUEUE_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {QUEUE_MD.relative_to(ROOT)}", file=sys.stderr)

    # Persist compact summary into latest.json
    if LATEST.exists():
        try:
            snap = json.loads(LATEST.read_text())
            def compact(r: dict) -> dict:
                return {
                    "name": r["name"],
                    "tier": r["tier"],
                    "score": r["score"],
                    "failing_refs": r["failing_refs"],
                    "all_refs": r["all_refs"],
                    "changes": r["changes"][:2],
                }
            top_clean = [r for r in results if r["tier"] == "clean-methods"][:8]
            top_heavy = [r for r in results if r["tier"] in ("multi", "size-change")][:8]
            snap["field_drift_queue"] = {
                "total": len(drift_names),
                "tiers": dict(tier_counts),
                "top": [compact(r) for r in results[:10]],
                "top_clean_methods": [compact(r) for r in top_clean],
                "top_heavy": [compact(r) for r in top_heavy],
            }
            LATEST.write_text(json.dumps(snap, indent=2))
        except Exception as exc:
            print(f"(couldn't persist field_drift_queue: {exc})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
