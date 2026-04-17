#!/usr/bin/env python3
"""Scan for the static-data decomp bug.

Pattern: `(define *FOO* <static-data-LN>)`. goalc rejects the angle-bracket
token in expression position. The decompiler currently emits the hyphen form
`<static-data-LN>` (not the older `<static-data LN>` space form).

Emits counts per file + per symbol, writes summary to latest.json, and
returns nonzero if the count has GROWN vs the previous snapshot (regression).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISASM_DIR = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"

# Matches both hyphen form <static-data-LN> (current emitter) and
# legacy space form <static-data LN> (now zero hits, kept for historical catch).
PAT = re.compile(r"^\(define\s+(\*[^*\s]+\*)\s+<static-data[-\s](L\d+)>\)", re.M)


def main() -> int:
    total = 0
    per_file: dict[str, int] = {}
    samples: list[dict] = []
    for path in sorted(DISASM_DIR.glob("*_disasm.gc")):
        text = path.read_text(errors="replace")
        hits = PAT.findall(text)
        if not hits:
            continue
        per_file[path.stem.replace("_disasm", "")] = len(hits)
        total += len(hits)
        if len(samples) < 20:
            sym, label = hits[0]
            samples.append({
                "file": path.stem.replace("_disasm", ""),
                "symbol": sym,
                "label": label,
                "count": len(hits),
            })

    print(f"static-data bug: {total} occurrences across {len(per_file)} files")
    print()
    print("top 15 offenders:")
    for name, c in sorted(per_file.items(), key=lambda x: -x[1])[:15]:
        print(f"  {c:>4}  {name}")

    # Persist into latest.json for status.md to surface.
    prev_total = None
    if LATEST.exists():
        try:
            snap = json.loads(LATEST.read_text())
            prev_total = snap.get("static_data_bug", {}).get("total")
            snap["static_data_bug"] = {
                "total": total,
                "files": len(per_file),
                "top_files": sorted(per_file.items(), key=lambda x: -x[1])[:20],
                "samples": samples,
            }
            LATEST.write_text(json.dumps(snap, indent=2))
        except Exception as e:
            print(f"(couldn't persist static_data_bug into latest.json: {e})")

    if prev_total is not None:
        delta = total - prev_total
        if delta:
            print()
            sign = "+" if delta > 0 else ""
            print(f"delta vs previous: {sign}{delta}  ({prev_total} → {total})")
            if delta > 0:
                return 2  # regression — more define-<static-data> errors than before
    return 0


if __name__ == "__main__":
    sys.exit(main())
