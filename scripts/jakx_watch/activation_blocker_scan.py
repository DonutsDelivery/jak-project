#!/usr/bin/env python3
"""Scan all-types.gc for block-commented deftypes and classify activation blockers.

Now that define-extern clobbers are eliminated (309 fixed), block-commented deftypes
are the primary activation bottleneck. This scanner classifies each of the 600+
block-commented deftypes by what's preventing activation.

Categories (mutually exclusive, priority-ordered):
  annotated       — has explicit note comments (reverted, needs investigation, blocker, etc.)
                    These need A1 investigation before touching.
  parent_blocked  — parent type is itself commented out. Must activate parent first.
  unknown_fields  — has UNKNOWN field type placeholders. Needs real types.
  old_regen       — name ends in -OLD-REGEN or similar. Stale regen artifact, likely safe to delete.
  ready           — parent active, no UNKNOWN fields, no explicit notes.
                    These are the lowest-hanging fruit for A2.

For each 'ready' type, we also report file_refs (split-failed files referencing it)
to help A2 prioritise.

Output:
  .jakx_watch/activation_blocker_queue.md  — ranked queue per category
  stdout                                   — summary counts

DO NOT edit all-types.gc from this script (A1/A2 lane).
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST_JSON = ROOT / ".jakx_watch" / "history" / "latest.json"
OUTPUT_MD = ROOT / ".jakx_watch" / "activation_blocker_queue.md"

# Patterns that flag a type as needing explicit investigation
NOTE_PATTERN = re.compile(
    r"(?:needs[\s\-]investigation|needs[\s\-]deeper|reverted|activation[\s\-]reverted"
    r"|do[\s\-]not[\s\-]activate|broken|assert[\s\-]mismatch|regression|wrong[\s\-]offset"
    r"|bad[\s\-]offset|pending[\s\-]investigation|TODO|FIXME|BLOCKED)",
    re.IGNORECASE,
)

RE_DEFTYPE = re.compile(r"\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(([\w<>!?:\-\+\*/=]+)\)")
RE_UNKNOWN_FIELD = re.compile(r"\bUNKNOWN\b")
OLD_REGEN_PAT = re.compile(r"-OLD-REGEN$", re.IGNORECASE)


def parse_all_block_deftypes(text: str) -> list[dict]:
    """Parse all block-commented deftypes from all-types.gc.

    Returns list of:
      name, parent, lineno, block_text, pre_comment_lines, unknown_count
    """
    lines = text.splitlines()
    results = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for start of a block comment containing a deftype
        if "#|" in line and "(deftype" in line:
            m = RE_DEFTYPE.search(line)
            if not m:
                i += 1
                continue
            name = m.group(1)
            parent = m.group(2)
            block_start_lineno = i + 1
            # Collect block body until |#
            j = i
            block_lines = [line]
            while j < len(lines):
                if "|#" in lines[j] and j > i:
                    block_lines.append(lines[j])
                    break
                j += 1
                if j < len(lines):
                    block_lines.append(lines[j])
            block_text = "\n".join(block_lines)

            # Collect ;; comment lines immediately preceding the #| line
            pre = []
            k = i - 1
            while k >= 0 and re.match(r"^\s*;;", lines[k]):
                pre.insert(0, lines[k].strip())
                k -= 1

            unknown_count = len(RE_UNKNOWN_FIELD.findall(block_text))

            results.append({
                "name": name,
                "parent": parent,
                "lineno": block_start_lineno,
                "block_text": block_text,
                "pre_comments": pre,
                "unknown_count": unknown_count,
            })
            i = j + 1
            continue
        i += 1
    return results


def build_active_set(text: str) -> set[str]:
    """Return set of type names that are active (not block-commented, not line-commented)."""
    lines = text.splitlines()
    active = set()
    in_block = [False] * len(lines)
    block = False
    for idx, line in enumerate(lines):
        if "#|" in line and not block:
            after = line.split("#|", 1)[1]
            if "|#" in after:
                in_block[idx] = True
                continue
            block = True
        if block:
            in_block[idx] = True
            if "|#" in line:
                block = False
            continue
        if re.match(r"^\s*;;", line):
            continue
        m = RE_DEFTYPE.search(line)
        if m:
            active.add(m.group(1))
    return active


def build_sf_ref_index(decomp_dir: Path, type_names: set[str], sf_stems: set[str]) -> dict[str, set[str]]:
    """Return {type_name: {split_failed_file_stems}} for types in type_names."""
    ref: dict[str, set[str]] = collections.defaultdict(set)
    if not decomp_dir.exists():
        return ref
    sorted_names = sorted(type_names, key=len, reverse=True)
    BATCH = 200
    batches = [sorted_names[i: i + BATCH] for i in range(0, len(sorted_names), BATCH)]
    compiled = [
        re.compile(r"(?<![a-z0-9\-])(" + "|".join(re.escape(n) for n in b) + r")(?![a-z0-9\-])")
        for b in batches
    ]
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        stem = fp.name[: -len("_disasm.gc")]
        if stem not in sf_stems:
            continue
        try:
            text = fp.read_text(errors="replace")
        except OSError:
            continue
        for pat in compiled:
            for m in pat.finditer(text):
                ref[m.group(1)].add(stem)
    return ref


def pick_decomp_dir() -> Path:
    best = (0, DECOMP_PRIMARY)
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists():
            count = sum(1 for _ in p.glob("*_disasm.gc"))
            if count > best[0]:
                best = (count, p)
    return best[1]


def classify(entry: dict, active_set: set[str]) -> str:
    """Return the activation category for a block-commented deftype."""
    name = entry["name"]
    parent = entry["parent"]
    pre = "\n".join(entry["pre_comments"])
    block = entry["block_text"]

    if OLD_REGEN_PAT.search(name):
        return "old_regen"

    # Annotated: has explicit human note about why it's commented
    if NOTE_PATTERN.search(pre) or NOTE_PATTERN.search(block):
        return "annotated"

    # Parent not active → must activate parent first
    if parent not in active_set:
        return "parent_blocked"

    # Has UNKNOWN field types
    if entry["unknown_count"] > 0:
        return "unknown_fields"

    return "ready"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--types", default=str(ALL_TYPES))
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--top", type=int, default=30,
                    help="Top N ready types to show (by split-failed refs)")
    args = ap.parse_args()

    types_path = Path(args.types)
    text = types_path.read_text(errors="replace")

    print("parsing block-commented deftypes...")
    entries = parse_all_block_deftypes(text)
    print(f"  found {len(entries)} block-commented deftypes")

    active_set = build_active_set(text)
    print(f"  active types: {len(active_set)}")

    # Load split-failed stems from latest.json
    sf_stems: set[str] = set()
    try:
        data = json.loads(LATEST_JSON.read_text())
        per_file = data.get("per_file", {})
        sf_stems = {s for s, v in per_file.items() if v.get("category") == "split-failed"}
    except Exception:
        pass
    print(f"  split-failed files: {len(sf_stems)}")

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()

    # Classify each entry
    by_cat: dict[str, list[dict]] = collections.defaultdict(list)
    for e in entries:
        cat = classify(e, active_set)
        by_cat[cat].append(e)

    # Build SF ref index for ready types
    ready_names = {e["name"] for e in by_cat.get("ready", [])}
    print(f"building SF ref index for {len(ready_names)} ready types...")
    sf_ref = build_sf_ref_index(decomp_dir, ready_names, sf_stems)
    for e in by_cat.get("ready", []):
        e["sf_refs"] = sf_ref.get(e["name"], set())
        e["sf_count"] = len(e["sf_refs"])
    # Sort ready by sf_count desc, then name
    by_cat["ready"].sort(key=lambda e: (-e["sf_count"], e["name"]))

    # Console summary
    print(f"\nActivation blocker summary:")
    print(f"  ready           : {len(by_cat.get('ready', []))}  ← lowest-hanging fruit for A2")
    print(f"  unknown_fields  : {len(by_cat.get('unknown_fields', []))}  ← needs UNKNOWN → real type")
    print(f"  parent_blocked  : {len(by_cat.get('parent_blocked', []))}  ← activate parent first")
    print(f"  annotated       : {len(by_cat.get('annotated', []))}  ← needs A1 investigation")
    print(f"  old_regen       : {len(by_cat.get('old_regen', []))}  ← stale artifacts, safe to delete")

    top_ready = by_cat.get("ready", [])[:args.top]
    if top_ready:
        print(f"\nTop {len(top_ready)} ready types (sorted by SF file refs):")
        print(f"  {'type':<40} {'L':>6} {'SF_refs':>7} {'parent':<25}")
        for e in top_ready:
            print(f"  {e['name']:<40} {e['lineno']:>6} {e['sf_count']:>7} {e['parent']:<25}")

    if args.no_write:
        return 0

    # Write markdown
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    md = [
        "# jakx activation blocker queue",
        "",
        f"_source: `scripts/jakx_watch/activation_blocker_scan.py`_",
        "",
        "Block-commented deftypes classified by activation difficulty. "
        "Now that all 309 define-extern clobbers are fixed, these are the "
        "primary remaining bottleneck for new type activations.",
        "",
        "| category | count | description |",
        "|----------|------:|-------------|",
        f"| ready | {len(by_cat.get('ready', []))} | parent active, no UNKNOWN fields — lowest-hanging fruit |",
        f"| unknown_fields | {len(by_cat.get('unknown_fields', []))} | has UNKNOWN field placeholders — needs real types |",
        f"| parent_blocked | {len(by_cat.get('parent_blocked', []))} | parent is also commented — activate parent first |",
        f"| annotated | {len(by_cat.get('annotated', []))} | has explicit note (reverted/needs investigation) — A1 only |",
        f"| old_regen | {len(by_cat.get('old_regen', []))} | -OLD-REGEN stale artifacts — safe to delete |",
        "",
        "---",
        "",
        "## Ready — activate now (no blockers)",
        "",
        "These types have an active parent and no UNKNOWN fields. "
        "Sorted by split-failed file references (activating high-SF types unblocks the most files). "
        "Use `scripts/jakx_watch/emit_stub.py --name TYPE` to generate the activation body.",
        "",
        f"| # | type | L | SF_refs | parent |",
        f"|---|------|---|--------:|--------|",
    ]
    for i, e in enumerate(by_cat.get("ready", [])[:args.top], 1):
        md.append(
            f"| {i} | `{e['name']}` | {e['lineno']} | {e['sf_count']} | `{e['parent']}` |"
        )
    md.append("")

    if by_cat.get("annotated"):
        md += [
            "## Annotated — needs A1 investigation",
            "",
            "These types have explicit note comments explaining why they were commented out. "
            "Do NOT activate without understanding the note.",
            "",
        ]
        for e in by_cat["annotated"]:
            md.append(f"### `{e['name']}` (L{e['lineno']}, parent=`{e['parent']}`)")
            md.append("")
            if e["pre_comments"]:
                md.append("**Notes:**")
                md.append("```")
                for c in e["pre_comments"]:
                    md.append(c)
                md.append("```")
            md.append("")

    if by_cat.get("unknown_fields"):
        md += [
            "## Unknown fields — needs type resolution",
            "",
            "These types have `UNKNOWN` field placeholders. "
            "Common fix: look up the field type in jak3 source or use `emit_stub.py`.",
            "",
            "| type | L | unknown_count | parent |",
            "|------|---|-------------:|--------|",
        ]
        for e in sorted(by_cat["unknown_fields"], key=lambda e: -e["unknown_count"]):
            md.append(
                f"| `{e['name']}` | {e['lineno']} | {e['unknown_count']} | `{e['parent']}` |"
            )
        md.append("")

    if by_cat.get("parent_blocked"):
        # Group by parent for cleaner output
        by_parent: dict[str, list[dict]] = collections.defaultdict(list)
        for e in by_cat["parent_blocked"]:
            by_parent[e["parent"]].append(e)

        md += [
            "## Parent-blocked — activate parent first",
            "",
            f"These {len(by_cat['parent_blocked'])} types cannot be activated until their "
            "parent type is activated. Grouped by blocked parent.",
            "",
            "| blocked_parent | count | child types (sample) |",
            "|----------------|------:|----------------------|",
        ]
        for parent, children in sorted(by_parent.items(), key=lambda x: -len(x[1])):
            sample = ", ".join(f"`{c['name']}`" for c in children[:3])
            if len(children) > 3:
                sample += f", …+{len(children) - 3}"
            md.append(f"| `{parent}` | {len(children)} | {sample} |")
        md.append("")

    if by_cat.get("old_regen"):
        md += [
            "## Old-regen artifacts — safe to delete",
            "",
            "These types have names ending in `-OLD-REGEN` and are stale decompiler artifacts. "
            "They can be deleted from all-types.gc without affecting decomp.",
            "",
        ]
        for e in by_cat["old_regen"]:
            md.append(f"- `{e['name']}` (L{e['lineno']})")
        md.append("")

    md += [
        "---",
        "",
        "## How to activate a 'ready' type",
        "",
        "1. Run `python3 scripts/jakx_watch/emit_stub.py --name TYPE` to get the jak3 body.",
        "2. Replace the `#|...|#` block in `all-types.gc` with the active deftype.",
        "3. Re-run `bash scripts/jakx_watch/run.sh` to measure impact.",
        "4. Check `ref_drift_scan.py` output — if an existing REF regresses, investigate before committing.",
        "",
        "For `unknown_fields` types: replace `UNKNOWN` with the correct field type from jak3 source.",
        "For `parent_blocked` types: first activate the parent, then come back to the child.",
        "For `annotated` types: read the note carefully. These were reverted for a reason.",
    ]

    OUTPUT_MD.write_text("\n".join(md) + "\n")
    print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
