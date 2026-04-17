#!/usr/bin/env python3
"""Rank ACTIVATION CANDIDATES — types that are commented (line OR block) in jakx
all-types.gc but appear active in the decompiler's regenerated all-types.gc.

Truly-missing types (neither in jakx nor commented) are rare in practice —
nearly all regen types already have a (possibly commented) body in jakx.
We prioritize un-commenting them safely.

Priority = f(downstream unblock, jak3 similarity, dependency depth).

Outputs:
  - .jakx_watch/activation_queue.md  (top 30 priority list for Session 1)
  - persists into latest.json under ["types_drift"]["ranked_discovery"]

Scoring (higher = higher priority):
  references  : # of broken _disasm.gc files mentioning the type name as a token
  in_jak3     : 1 if jak3/all-types.gc has a deftype with the same name else 0
  parent_ok   : 1 if the regen parent is already active in current all-types.gc
                (leaf-ish — no cascading UNKNOWN-parent breakage when we add it)
  dep_unknown : # of referenced type names in the body that are neither
                active-in-current nor in the discovery set we'll add first

final = 10*parent_ok + 2*in_jak3 + log2(1+references) - 0.5*dep_unknown
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
REGEN = ROOT / ".jakx_watch" / "decomp_out" / "jakx" / "new-all-types.gc"
JAKX_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
JAK3_TYPES = ROOT / "decompiler" / "config" / "jak3" / "all-types.gc"
DISASM_DIR = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
QUEUE_MD = ROOT / ".jakx_watch" / "activation_queue.md"

RE_DEFTYPE_START = re.compile(r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(([\w<>!?:\-\+\*/=]+)")
RE_DEFTYPE_ANY   = re.compile(r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)")
TYPE_TOKEN_RE    = re.compile(r"[\w<>!?:\-\+\*/=]+")


def parse_deftypes_with_parent(path: Path) -> dict[str, dict]:
    """Returns {name: {parent, body, commented, block_commented}}.

    Handles `;; (deftype ...)` line-comments AND `#| (deftype ...) |#` block-comments.
    Block-comment state is tracked by scanning every line (including inside deftype
    bodies) so we don't get out of sync across commented blocks.
    """
    text = path.read_text(errors="replace")
    out: dict[str, dict] = {}
    lines = text.splitlines()

    # First pass: determine which lines are inside #|...|# block comments.
    in_block = [False] * len(lines)
    block = False
    for idx, line in enumerate(lines):
        # #| may appear mid-line — once we see it, the rest of THIS line and
        # everything until |# is in-block. Mark from this line on.
        if "#|" in line and not block:
            block = True
            in_block[idx] = True
        elif block:
            in_block[idx] = True
            if "|#" in line:
                block = False
        # Two-state: if #| and |# are on the SAME line, we end within this line.
        if "#|" in line and "|#" in line.split("#|", 1)[1]:
            block = False

    # Second pass: extract deftypes.
    i = 0
    while i < len(lines):
        line = lines[i]
        m = RE_DEFTYPE_ANY.match(line)
        if not m:
            i += 1
            continue
        name = m.group(1)
        line_commented = ";;" in line[: line.find("(deftype")]
        block_commented = in_block[i]
        mp = RE_DEFTYPE_START.match(line)
        parent = mp.group(2) if mp else None
        depth = 0
        body_lines: list[str] = []
        j = i
        while j < len(lines):
            raw = lines[j]
            s = re.sub(r"^\s*;;\s?", "", raw) if line_commented else raw
            body_lines.append(raw)
            for ch in s:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            if depth <= 0 and j > i:
                break
            j += 1
        # Aggregate across multiple occurrences: keep the active one if any.
        prev = out.get(name)
        this_active = not line_commented and not block_commented
        prev_active = prev and not prev["commented"] and not prev["block_commented"]
        if prev is None or (this_active and not prev_active):
            out[name] = {
                "parent": parent,
                "body": "\n".join(body_lines),
                "commented": line_commented,
                "block_commented": block_commented,
            }
        i = j + 1
    return out


def collect_reference_counts(names: set[str]) -> Counter:
    """Count how many _disasm.gc files mention each name at least once."""
    counts: Counter = Counter()
    for path in DISASM_DIR.glob("*_disasm.gc"):
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        tokens = set(TYPE_TOKEN_RE.findall(text))
        for n in names & tokens:
            counts[n] += 1
    return counts


def main() -> int:
    if not REGEN.exists():
        print(f"missing regen: {REGEN}")
        return 1
    cur = parse_deftypes_with_parent(JAKX_TYPES)
    reg = parse_deftypes_with_parent(REGEN)
    jak3 = parse_deftypes_with_parent(JAK3_TYPES)

    cur_active = {n for n, v in cur.items() if not v["commented"] and not v["block_commented"]}
    cur_inactive = {n for n, v in cur.items() if v["commented"] or v["block_commented"]}
    reg_active = {n for n, v in reg.items() if not v["block_commented"]}

    # Tier 1 — commented in jakx, actively emitted by regen (highest-confidence).
    tier1 = sorted(cur_inactive & reg_active)
    # Tier 2 — commented in jakx, regen has block-commented body (speculative).
    tier2 = sorted(cur_inactive - reg_active)
    # Tier 3 — not in jakx at all (true discovery — also rare).
    tier3 = sorted(reg_active - set(cur.keys()))

    discovery = tier1 + tier2 + tier3
    tier_of = {}
    for n in tier1: tier_of[n] = 1
    for n in tier2: tier_of[n] = 2
    for n in tier3: tier_of[n] = 3
    print(f"tier1 (regen-active): {len(tier1)}  "
          f"tier2 (regen-block-commented): {len(tier2)}  "
          f"tier3 (pure-discovery): {len(tier3)}  "
          f"(total={len(discovery)})")

    # Reference counts over all disasm output.
    refs = collect_reference_counts(set(discovery))

    # Score each discovery type.
    discovery_set = set(discovery)
    ranked = []
    for n in discovery:
        # Use regen body if present; else fall back to jakx's commented body.
        src = reg.get(n) or cur.get(n)
        body = src["body"] if src else ""
        parent = (src.get("parent") if src else None) or ""
        parent_ok = 1 if parent in cur_active else 0
        in_jak3 = 1 if n in jak3 else 0
        tier = tier_of.get(n, 3)
        # Count type-like tokens in body that reference other not-yet-active names.
        body_tokens = set(TYPE_TOKEN_RE.findall(body))
        # Exclude trivia / obviously-resolved things.
        trivia = {
            n, parent, "deftype", "define-extern", ":method-count-assert", ":size-assert",
            ":flag-assert", ":states", ":state-methods", ":methods", ":pack-me", ":packed",
            ":fields", "int", "uint", "float", "symbol", "string", "object", "pointer",
            "structure", "basic", "array", "inline-array", "function",
        }
        dep_unknown_names = [t for t in body_tokens
                             if t not in trivia
                             and t not in cur_active
                             and (t in discovery_set or t in jak3)
                             and not t.startswith(":")
                             and not t.startswith("#")]
        dep_unknown = len(set(dep_unknown_names) - {n, parent})
        refs_count = refs.get(n, 0)
        # Tier bonus: regen-active evidence > regen-speculative > pure-discovery.
        tier_bonus = {1: 4.0, 2: 0.0, 3: 1.0}[tier]
        score = (
            10.0 * parent_ok
            + 2.0 * in_jak3
            + math.log2(1 + refs_count)
            - 0.5 * dep_unknown
            + tier_bonus
        )
        ranked.append({
            "name": n,
            "parent": parent,
            "score": round(score, 2),
            "refs": refs_count,
            "in_jak3": in_jak3,
            "parent_ok": parent_ok,
            "dep_unknown": dep_unknown,
            "tier": tier,
        })

    ranked.sort(key=lambda r: (-r["score"], -r["refs"], r["name"]))
    top = ranked[:30]

    # Write markdown for humans.
    lines = [
        "# jakx activation priority queue",
        "",
        f"_source: scripts/jakx_watch/rank_discovery.py  ·  pool: {len(discovery)}  "
        f"(T1={len(tier1)} regen-active  ·  T2={len(tier2)} regen-speculative  ·  "
        f"T3={len(tier3)} pure-discovery)_",
        "",
        "Ranked by: (parent_ok × 10) + (in_jak3 × 2) + log2(1+refs) − (dep_unknown × 0.5) + tier_bonus",
        "",
        "- **T1** — decomp emitted an active deftype for this name. Highest confidence.",
        "- **T2** — decomp has a `#| ... |#`-commented body (speculative / incomplete).",
        "- **T3** — truly not in jakx at all.",
        "- **parent_ok** — regen parent is already active in current all-types.gc (leaf-ish, safe to add)",
        "- **in_jak3** — jak3/all-types.gc has a same-named deftype (direct port candidate)",
        "- **refs** — # of currently-decompiled files mentioning the type name",
        "- **dep_unknown** — # of type tokens in the body that aren't yet active",
        "",
        "| # | T | name | parent | refs | jak3 | parent-ok | deps | score |",
        "|---|:-:|------|--------|-----:|:----:|:---------:|-----:|------:|",
    ]
    for i, r in enumerate(top, 1):
        lines.append(
            f"| {i} | {r['tier']} | `{r['name']}` | `{r['parent']}` | {r['refs']} | "
            f"{'✓' if r['in_jak3'] else ''} | {'✓' if r['parent_ok'] else ''} | "
            f"{r['dep_unknown']} | {r['score']} |"
        )
    lines.append("")
    lines.append("## How to use this queue")
    lines.append("")
    lines.append("For each row (top-down):")
    lines.append("1. If `jak3 ✓`: copy the jak3 deftype body verbatim into jakx all-types.gc")
    lines.append("   (`scripts/jakx_watch/emit_stub.py --name NAME` gives you a ready block)")
    lines.append("2. If `jak3` empty: use the regen body from `.jakx_watch/decomp_out/jakx/new-all-types.gc`")
    lines.append("3. Re-run `bash scripts/jakx_watch/run.sh` to check for regressions")
    lines.append("")
    QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_MD.write_text("\n".join(lines))
    print(f"wrote {QUEUE_MD.relative_to(ROOT)}  (top {len(top)} of {len(ranked)})")

    # Persist into latest.json for measure.py --restatus-only to pick up.
    if LATEST.exists():
        try:
            snap = json.loads(LATEST.read_text())
            snap.setdefault("types_drift", {})
            snap["types_drift"]["ranked_discovery"] = top
            snap["types_drift"]["discovery_full"] = [r["name"] for r in ranked]
            LATEST.write_text(json.dumps(snap, indent=2))
        except Exception as e:
            print(f"(couldn't persist rank into latest.json: {e})")

    # Print top 10 to stdout for easy terminal review.
    print()
    print("top 10:")
    for i, r in enumerate(top[:10], 1):
        marker = "J3" if r["in_jak3"] else "  "
        parent_mark = "P!" if r["parent_ok"] else "  "
        print(f"  {i:>2}. [{marker}][{parent_mark}] {r['name']:<38} refs={r['refs']:>3}  score={r['score']:>5}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
