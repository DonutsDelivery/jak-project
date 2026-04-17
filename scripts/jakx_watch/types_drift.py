#!/usr/bin/env python3
"""Diff the decompiler-regenerated all-types against the current hand-edited one.

Run the decompiler with `generate_all_types: true` (see run.sh — already wired).
This produces <out>/jakx/new-all-types.gc reflecting what the decompiler
CAN infer from the current types+code state, using jak3/jak2 as seed.

Diff it against decompiler/config/jakx/all-types.gc to surface:
  - DISCOVERY candidates   — type in regen, not in current (or commented out).
                             Sessions 1/2 can copy the regen body into the
                             current file; decomp already knows it.
  - OVER-SPECIFIED         — type in current but NOT in regen. The current
                             deftype may be hand-written / speculative, or
                             the regen couldn't find evidence for it. Worth
                             reviewing whether it's justified.
  - FIELD DRIFT            — type in both but their deftype bodies differ
                             (size, method-count, fields). Sign that one
                             side is out of date.

Also flag: types the current file has COMMENTED OUT (i.e. in the ";; "
prefix form), that the regen DOES emit as active — those are the highest-ROI
cluster-activation candidates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"

# (deftype NAME ... )   — capture name + whole body up to balanced paren.
# Block-aware parser mirrors scripts/jakx_watch/rank_discovery.py so a type
# `#| (deftype X ...) |#`-commented in jakx is recognized as PRESENT (just
# inactive) rather than reported as DISCOVERY. Not fixing this was leading
# status.md to claim "459 discovery" when the real count is 0.
RE_DEFTYPE_START = re.compile(
    r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)\s*"
)


def parse_deftypes(text: str) -> dict[str, dict]:
    """Returns {name: {commented, block_commented, body, digest, first_line}}.

    Handles both line-comments (`;; (deftype ...)`) and block-comments
    (`#| (deftype ...) |#`). A type appearing in either form is considered
    PRESENT (distinct from DISCOVERY, which is "nowhere in the file").
    """
    out: dict[str, dict] = {}
    lines = text.splitlines()

    # First pass: mark every line that falls inside a `#| ... |#` block.
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

    # Second pass: extract each deftype body.
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
            if commented:
                s = re.sub(r"^\s*;;\s?", "", raw)
            else:
                s = raw
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
        digest = hashlib.sha1(re.sub(r"\s+", " ", body).encode()).hexdigest()[:10]
        prev = out.get(name)
        this_active = not commented and not block_commented
        prev_active = prev and not prev["commented"] and not prev["block_commented"]
        if prev is None or (this_active and not prev_active):
            out[name] = {
                "commented": commented,
                "block_commented": block_commented,
                "body": body,
                "digest": digest,
                "first_line": start_i + 1,
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--current", required=True, help="decompiler/config/jakx/all-types.gc")
    ap.add_argument("--regen", required=True, help="output/jakx/new-all-types.gc")
    ap.add_argument("--show-bodies", type=int, default=0,
                    help="print the first N drift bodies inline (default 0)")
    args = ap.parse_args()

    cur = parse_deftypes(Path(args.current).read_text(errors="replace"))
    reg = parse_deftypes(Path(args.regen).read_text(errors="replace"))

    # Active = neither line-commented nor block-commented. Block-commented
    # types (`#| ... |#`) are COMMENTED, not DISCOVERY.
    cur_active = {n for n, v in cur.items()
                  if not v["commented"] and not v.get("block_commented", False)}
    cur_commented = {n for n, v in cur.items()
                     if v["commented"] or v.get("block_commented", False)}
    reg_active = {n for n, v in reg.items() if not v.get("block_commented", False)}
    reg_names = set(reg.keys())

    # Activation candidates: commented (line OR block) in current, emitted
    # as ACTIVE in regen. These are the immediate uncomment wins.
    activation_candidates = sorted(cur_commented & reg_active)

    # Discovery: not in current at all (neither active nor commented),
    # present in regen. These require NEW deftypes (not just uncommenting).
    discovery = sorted(reg_names - set(cur.keys()))

    # Over-specified: active in current, not in regen at all.
    over_spec = sorted(cur_active - reg_names)

    # Field drift: active in both, but bodies differ (by digest).
    drift = []
    for n in sorted(cur_active & reg_names):
        if cur[n]["digest"] != reg[n]["digest"]:
            drift.append(n)

    print(f"current all-types:   {len(cur_active)} active + {len(cur_commented)} commented = {len(cur)} total")
    print(f"regenerated types:   {len(reg_names)}")
    print()
    print(f"  activation candidates (commented in current, emitted active in regen): {len(activation_candidates)}")
    print(f"  discovery (in regen, missing from current):                            {len(discovery)}")
    print(f"  over-specified (active in current, missing from regen):                {len(over_spec)}")
    print(f"  field drift (different bodies):                                        {len(drift)}")
    print()

    def show_list(label: str, names: list[str], limit: int = 30):
        if not names:
            return
        print(f"== {label} ({len(names)}) ==")
        for n in names[:limit]:
            print(f"  {n}")
        if len(names) > limit:
            print(f"  ... +{len(names) - limit} more")
        print()

    show_list("ACTIVATION CANDIDATES — uncomment these in all-types.gc (decomp already knows them)",
              activation_candidates)
    show_list("DISCOVERY — not yet in all-types.gc at all", discovery)
    show_list("OVER-SPECIFIED — active in current but regen found no evidence", over_spec, limit=20)
    show_list("FIELD DRIFT — active in both but body differs", drift, limit=20)

    # Persist a summary into latest.json so measure.py --restatus-only can surface
    # the headline numbers + top activation candidates in status.md.
    if LATEST.exists():
        try:
            snap = json.loads(LATEST.read_text())
            snap["types_drift"] = {
                "current_active": len(cur_active),
                "current_commented": len(cur_commented),
                "regen_total": len(reg_names),
                "activation_candidates": activation_candidates,
                "discovery_count": len(discovery),
                "discovery_sample": discovery[:30],
                "over_specified_count": len(over_spec),
                "field_drift_count": len(drift),
            }
            LATEST.write_text(json.dumps(snap, indent=2))
        except Exception as e:
            print(f"(couldn't persist types_drift into latest.json: {e})")


if __name__ == "__main__":
    main()
