#!/usr/bin/env python3
"""Scan jak3 label_types.jsonc entries for direct copy-port candidates to jakx.

A 'copy-port candidate' is a jak3 label entry where:
  1. The file exists in jakx's decomp output (_ir2.asm present)
  2. The exact label name (e.g. 'L108') appears as a definition in jakx's _ir2.asm
  3. jakx does NOT already have an entry for that (file, label) pair in its
     label_types.jsonc

Label numbers are assigned by the disassembler per-file from the binary. If the
same label appears in both jak3 and jakx's asm for the same file, the static data
at that position is likely the same and the jak3 type annotation is directly
copy-portable.

Output:
  .jakx_watch/label_types_copy_queue.md   — candidates by file + confidence
  stdout                                  — summary counts

DO NOT modify label_types.jsonc directly — that is A1/A2's lane.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAK3_LABEL_TYPES = ROOT / "decompiler" / "config" / "jak3" / "ntsc_v1" / "label_types.jsonc"
JAKX_LABEL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "label_types.jsonc"
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
OUTPUT_MD = ROOT / ".jakx_watch" / "label_types_copy_queue.md"

# Label definition pattern in _ir2.asm: line starting with "LNNN:" optionally with spaces
RE_LABEL_DEF = re.compile(r"^(L\d+)\s*:", re.MULTILINE)


def load_jsonc(path: Path) -> dict:
    text = path.read_text(errors="replace")
    # Strip // line comments and /* */ block comments
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return json.loads(text)


def pick_decomp_dir() -> Path | None:
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists() and any(p.glob("*_ir2.asm")):
            return p
    return None


def get_jakx_labels(decomp_dir: Path, filename: str) -> set[str]:
    """Return the set of label names defined in jakx's <filename>_ir2.asm."""
    asm = decomp_dir / f"{filename}_ir2.asm"
    if not asm.exists():
        return set()
    content = asm.read_text(errors="replace")
    return set(RE_LABEL_DEF.findall(content))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--min-confidence", choices=["confirmed", "all"], default="all",
                    help="'confirmed' = only show labels confirmed in jakx asm; "
                         "'all' = also show labels not yet verified (file exists but label absent)")
    args = ap.parse_args()

    jak3 = load_jsonc(JAK3_LABEL_TYPES)
    jakx = load_jsonc(JAKX_LABEL_TYPES)

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if decomp_dir is None:
        print("ERROR: no decomp output dir with _ir2.asm files found", file=sys.stderr)
        return 1
    print(f"decomp dir: {decomp_dir.relative_to(ROOT)}")

    # Build set of already-covered (file, label) pairs in jakx
    jakx_covered: dict[str, set[str]] = {}
    for fname, entries in jakx.items():
        jakx_covered[fname] = {e[0] for e in entries}

    # Per-file candidate lists
    # Each entry: {label, jak3_type, jak3_extra, confirmed (label in jakx asm), in_jakx}
    file_candidates: dict[str, list[dict]] = {}
    file_no_asm: list[str] = []     # jak3 files without jakx asm
    file_fully_covered: list[str] = []  # all entries already in jakx

    stats = {"total_jak3_entries": 0, "confirmed": 0, "label_absent": 0,
             "already_covered": 0, "no_asm": 0, "files_with_candidates": 0}

    for fname, entries in sorted(jak3.items()):
        stats["total_jak3_entries"] += len(entries)

        jakx_labels_for_file = jakx_covered.get(fname, set())
        uncovered = [e for e in entries if e[0] not in jakx_labels_for_file]

        if not uncovered:
            # All jak3 entries already covered in jakx
            stats["already_covered"] += len(entries)
            file_fully_covered.append(fname)
            continue

        # Check if jakx has an ir2.asm for this file
        jakx_labels = get_jakx_labels(decomp_dir, fname)
        if not jakx_labels:
            # No asm — can't verify or port
            stats["no_asm"] += len(uncovered)
            file_no_asm.append(fname)
            continue

        candidates = []
        for entry in uncovered:
            label = entry[0]
            jak3_type = entry[1] if len(entry) > 1 else "unknown"
            jak3_extra = entry[2] if len(entry) > 2 else None
            confirmed = label in jakx_labels
            if confirmed:
                stats["confirmed"] += 1
            else:
                stats["label_absent"] += 1
            candidates.append({
                "label": label,
                "jak3_type": jak3_type,
                "jak3_extra": jak3_extra,
                "confirmed": confirmed,
            })

        if candidates:
            file_candidates[fname] = candidates
            stats["files_with_candidates"] += 1

    confirmed_total = sum(
        sum(1 for c in cands if c["confirmed"]) for cands in file_candidates.values()
    )
    confirmed_files = sum(
        1 for cands in file_candidates.values() if any(c["confirmed"] for c in cands)
    )

    print(f"\njak3 label_types summary:")
    print(f"  files in jak3:              {len(jak3)}")
    print(f"  files in jakx:              {len(jakx)}")
    print(f"  total jak3 entries:         {stats['total_jak3_entries']}")
    print(f"  already in jakx:            {stats['already_covered']}")
    print(f"  files with no jakx asm:     {len(file_no_asm)}")
    print(f"\ncopy-port candidates:")
    print(f"  files with candidates:      {stats['files_with_candidates']}")
    print(f"  confirmed (label in asm):   {confirmed_total}  ({confirmed_files} files)")
    print(f"  label absent in jakx asm:   {stats['label_absent']}  (binary likely differs)")

    if args.no_write:
        return 0

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# jakx label_types — jak3 copy-port candidate queue",
        "",
        f"_source: `scripts/jakx_watch/label_types_copy_scan.py`_",
        "",
        "A **confirmed** candidate has the exact same label name in jakx's `_ir2.asm` — "
        "the static data is present at that address and the jak3 type annotation is "
        "directly copy-portable. A **label-absent** entry means jak3 had that label "
        "but jakx's binary doesn't — the data may have moved, been renamed, or removed.",
        "",
        "**Lane: DO NOT edit `label_types.jsonc` directly — queue is for A1/A2 review.**",
        "",
        f"| stat | value |",
        f"|------|------:|",
        f"| jak3 files | {len(jak3)} |",
        f"| jakx files | {len(jakx)} |",
        f"| jak3 total entries | {stats['total_jak3_entries']} |",
        f"| already in jakx | {stats['already_covered']} |",
        f"| confirmed copy-port entries | {confirmed_total} |",
        f"| files with confirmed entries | {confirmed_files} |",
        f"| label absent (binary differs) | {stats['label_absent']} |",
        f"| no jakx asm (file not decompiled) | {stats['no_asm']} |",
        "",
        "---",
        "",
        "## Confirmed copy-port candidates",
        "",
        "These labels exist in both jak3's `label_types.jsonc` and jakx's `_ir2.asm`. "
        "Copy the entry verbatim (label + type + optional size) into "
        "`decompiler/config/jakx/ntsc_v1/label_types.jsonc` under the same filename key.",
        "",
    ]

    # Sort files: confirmed-first, then by count of confirmed entries desc
    def sort_key(fname):
        cands = file_candidates[fname]
        confirmed = sum(1 for c in cands if c["confirmed"])
        return (-confirmed, fname)

    for fname in sorted(file_candidates.keys(), key=sort_key):
        cands = file_candidates[fname]
        confirmed = [c for c in cands if c["confirmed"]]
        absent = [c for c in cands if not c["confirmed"]]

        if not confirmed and args.min_confidence == "confirmed":
            continue

        already_count = len(jakx_covered.get(fname, set()))
        lines.append(
            f"### `{fname}` — {len(confirmed)} confirmed, {len(absent)} absent "
            f"({already_count} already in jakx)"
        )
        lines.append("")

        if confirmed:
            lines.append("**Confirmed** (label exists in jakx asm — safe to copy):")
            lines.append("")
            lines.append("```json")
            lines.append(f'"{fname}": [')
            for c in sorted(confirmed, key=lambda x: x["label"]):
                extra = f", {json.dumps(c['jak3_extra'])}" if c["jak3_extra"] is not None else ""
                lines.append(f'  ["{c["label"]}", "{c["jak3_type"]}"{extra}],')
            lines.append("],")
            lines.append("```")
            lines.append("")

        if absent:
            lines.append(
                f"**Label-absent** ({len(absent)} entries — label not found in jakx asm, "
                f"binary likely differs):"
            )
            lines.append("")
            for c in sorted(absent, key=lambda x: x["label"]):
                extra = f", {json.dumps(c['jak3_extra'])}" if c["jak3_extra"] is not None else ""
                lines.append(f"- `[\"{c['label']}\", \"{c['jak3_type']}\"{extra}]`")
            lines.append("")

    lines += [
        "---",
        "",
        "## Files already fully covered in jakx label_types",
        "",
        f"All jak3 entries for these {len(file_fully_covered)} files are already present in jakx:",
        "",
        ", ".join(f"`{f}`" for f in sorted(file_fully_covered)),
        "",
        "---",
        "",
        "## Files with jak3 entries but no jakx asm (not yet decompiled)",
        "",
        f"{len(file_no_asm)} files — these need a successful decomp run first:",
        "",
        ", ".join(f"`{f}`" for f in sorted(file_no_asm)),
        "",
        "---",
        "",
        "## How to apply",
        "",
        "For each confirmed entry above, add to "
        "`decompiler/config/jakx/ntsc_v1/label_types.jsonc`:",
        "```json",
        '// In the file\'s key, add the entry:',
        '// ["L42", "matrix", false]',
        '// Use the same label, type, and optional-extra (size/bool) from jak3.',
        "```",
        "",
        "Re-run decomp after adding entries — new static data will be typed correctly.",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
