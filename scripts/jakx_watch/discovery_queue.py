#!/usr/bin/env python3
"""Produce a ranked top-20 DISCOVERY queue for self-serve batched deftype work.

Complements `rank_discovery.py` (which produces `.jakx_watch/activation_queue.md`
for commented-in-jakx types). This tool focuses on the types_drift DISCOVERY
set — names that the decompiler's regenerated all-types emits but jakx's
current all-types.gc lacks entirely (not active, not line-commented, not
block-commented).

Each queue entry gets:
  * name + parent
  * dependent-count       — how many currently-failing (split-failed /
                            real-partial) files mention the type
  * copy-port complexity  — "clean copy" (jak3 body digest matches regen) vs
                            "needs surgery" (jak3 has a different body) vs
                            "no jak3 source"
  * parent-first prereqs  — parents up the chain that are ALSO not active in
                            jakx. Adding the discovery type without first
                            handling these will fail.
  * jak3 location         — line number of jak3's deftype for quick paste

Output:
  * .jakx_watch/discovery_queue.md     — human-readable markdown
  * latest.json[discovery_queue]        — compact top-20 for measure.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAKX_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
JAK3_TYPES = ROOT / "decompiler" / "config" / "jak3" / "all-types.gc"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
REGEN_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx" / "new-all-types.gc"
REGEN_FALLBACK = ROOT / "decompiler_out" / "jakx" / "new-all-types.gc"
DISASM_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DISASM_FALLBACK = ROOT / "decompiler_out" / "jakx"
QUEUE_MD = ROOT / ".jakx_watch" / "discovery_queue.md"

RE_DEFTYPE_START = re.compile(
    r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(([\w<>!?:\-\+\*/=]+)"
)
RE_DEFTYPE_ANY = re.compile(
    r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)"
)
TYPE_TOKEN_RE = re.compile(r"[\w<>!?:\-\+\*/=]+")


def parse_deftypes_with_parent(path: Path) -> dict[str, dict]:
    """Block-aware deftype parser. Returns {name: {parent, body, commented,
    block_commented, first_line, digest}}."""
    if not path.exists():
        return {}
    text = path.read_text(errors="replace")
    out: dict[str, dict] = {}
    lines = text.splitlines()

    # First pass: determine which lines are inside #| ... |# block comments.
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

    # Second pass: extract deftypes with paren-depth tracking.
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
        body = "\n".join(body_lines)
        digest = hashlib.sha1(re.sub(r"\s+", " ", body).encode()).hexdigest()[:10]
        prev = out.get(name)
        this_active = not line_commented and not block_commented
        prev_active = prev and not prev["commented"] and not prev["block_commented"]
        if prev is None or (this_active and not prev_active):
            out[name] = {
                "parent": parent,
                "body": body,
                "commented": line_commented,
                "block_commented": block_commented,
                "first_line": i + 1,
                "digest": digest,
            }
        i = j + 1
    return out


def pick_decomp_dir() -> Path:
    """Prefer populated primary; fall back to shared decompiler_out."""
    for p in (DISASM_PRIMARY, DISASM_FALLBACK):
        if p.exists() and any(p.glob("*_disasm.gc")):
            return p
    return DISASM_PRIMARY


def pick_regen() -> Path | None:
    for p in (REGEN_PRIMARY, REGEN_FALLBACK):
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def collect_reference_counts(names: set[str], disasm_dir: Path) -> Counter:
    counts: Counter = Counter()
    if not disasm_dir.exists():
        return counts
    for path in disasm_dir.glob("*_disasm.gc"):
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        tokens = set(TYPE_TOKEN_RE.findall(text))
        for n in names & tokens:
            counts[n] += 1
    return counts


def collect_failing_file_refs(
    names: set[str], disasm_dir: Path, per_file: dict
) -> dict[str, int]:
    """Per-name: count of REFs coming from split-failed + real-partial files."""
    if not disasm_dir.exists():
        return {n: 0 for n in names}
    out: Counter = Counter()
    for path in disasm_dir.glob("*_disasm.gc"):
        stem = path.name[: -len("_disasm.gc")]
        cat = (per_file.get(stem) or {}).get("category")
        if cat not in ("split-failed", "real-partial"):
            continue
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        tokens = set(TYPE_TOKEN_RE.findall(text))
        for n in names & tokens:
            out[n] += 1
    return dict(out)


def walk_parent_prereqs(
    name: str,
    regen_deftypes: dict,
    jakx_deftypes: dict,
    max_depth: int = 8,
) -> list[str]:
    """Walk up the parent chain; return intermediate parents that are NOT
    active in jakx. Stops when an active parent is found or the chain dead-ends.
    """
    jakx_active = {n for n, v in jakx_deftypes.items()
                   if not v["commented"] and not v["block_commented"]}
    prereqs: list[str] = []
    cur_parent = (regen_deftypes.get(name) or {}).get("parent")
    depth = 0
    seen = {name}
    while cur_parent and depth < max_depth and cur_parent not in seen:
        seen.add(cur_parent)
        if cur_parent in jakx_active:
            break
        prereqs.append(cur_parent)
        next_src = regen_deftypes.get(cur_parent) or jakx_deftypes.get(cur_parent)
        cur_parent = (next_src or {}).get("parent")
        depth += 1
    return prereqs


def classify_complexity(
    regen_body: str,
    jak3_body: str | None,
    regen_digest: str | None,
    jak3_digest: str | None,
) -> str:
    """Return 'clean-copy' / 'minor-surgery' / 'major-surgery' / 'no-jak3-source'."""
    if not jak3_body:
        return "no-jak3-source"
    if regen_digest and jak3_digest and regen_digest == jak3_digest:
        return "clean-copy"
    # Digest differs — estimate surgery size by comparing :size-assert and
    # :method-count-assert values between regen and jak3.
    def extract_asserts(body: str) -> tuple[int | None, int | None]:
        mc = re.search(r":method-count-assert\s+(\d+)", body)
        sz = re.search(r":size-assert\s+(#x[0-9a-fA-F]+|\d+)", body)
        mcv = int(mc.group(1)) if mc else None
        szv = None
        if sz:
            s = sz.group(1)
            szv = int(s, 16) if s.startswith("#x") else int(s)
        return mcv, szv
    r_mc, r_sz = extract_asserts(regen_body)
    j_mc, j_sz = extract_asserts(jak3_body)
    if (r_mc, r_sz) == (j_mc, j_sz):
        return "minor-surgery"
    return "major-surgery"


def score_entry(
    refs: int,
    failing_refs: int,
    complexity: str,
    prereqs: int,
    parent_ok: bool,
) -> float:
    """Higher = more ready to tackle.

    Weights:
      * log2(1 + failing_refs) * 3    — unblock impact on broken files
      * log2(1 + refs)                — breadth of downstream use
      * -2 * prereqs                  — each missing parent delays work
      * +10 if parent_ok              — immediate activation possible
      * complexity bonuses            — clean-copy easier than surgery
    """
    s = 0.0
    s += 3.0 * math.log2(1 + failing_refs)
    s += math.log2(1 + refs)
    s -= 2.0 * prereqs
    if parent_ok:
        s += 10.0
    s += {
        "clean-copy": 5.0,
        "minor-surgery": 2.0,
        "major-surgery": 0.0,
        "no-jak3-source": -3.0,
    }.get(complexity, 0.0)
    return round(s, 2)


def compose_queue(
    jakx_deftypes: dict,
    regen_deftypes: dict,
    jak3_deftypes: dict,
    disasm_dir: Path,
    per_file: dict,
) -> list[dict]:
    # Pure discovery: in regen, not in jakx in any form.
    discovery = sorted(set(regen_deftypes.keys()) - set(jakx_deftypes.keys()))
    if not discovery:
        return []

    disc_set = set(discovery)
    refs = collect_reference_counts(disc_set, disasm_dir)
    failing_refs = collect_failing_file_refs(disc_set, disasm_dir, per_file)
    jakx_active = {n for n, v in jakx_deftypes.items()
                   if not v["commented"] and not v["block_commented"]}

    entries: list[dict] = []
    for n in discovery:
        reg = regen_deftypes[n]
        parent = reg.get("parent") or ""
        jak3_entry = jak3_deftypes.get(n)
        jak3_body = (jak3_entry or {}).get("body")
        jak3_digest = (jak3_entry or {}).get("digest")
        jak3_line = (jak3_entry or {}).get("first_line")
        complexity = classify_complexity(
            reg["body"], jak3_body, reg.get("digest"), jak3_digest
        )
        prereqs = walk_parent_prereqs(n, regen_deftypes, jakx_deftypes)
        parent_ok = parent in jakx_active if parent else False
        r_count = refs.get(n, 0)
        f_count = failing_refs.get(n, 0)
        score = score_entry(r_count, f_count, complexity, len(prereqs), parent_ok)
        entries.append({
            "name": n,
            "parent": parent,
            "parent_ok": parent_ok,
            "refs": r_count,
            "failing_refs": f_count,
            "complexity": complexity,
            "prereqs": prereqs,
            "prereq_count": len(prereqs),
            "jak3_line": jak3_line,
            "score": score,
        })

    entries.sort(key=lambda e: (-e["score"], -e["failing_refs"], e["name"]))
    return entries


def format_md(entries: list[dict], regen_path: Path | None, discovery_count: int) -> str:
    lines = [
        "# jakx discovery priority queue",
        "",
        f"_source: scripts/jakx_watch/discovery_queue.py  ·  "
        f"pool: {discovery_count} pure-discovery types  ·  "
        f"regen: {regen_path.relative_to(ROOT) if regen_path else '(missing — run decomp)'}_",
        "",
        "DISCOVERY = type emitted by the regenerated all-types (`new-all-types.gc`) "
        "but absent from jakx/all-types.gc in any form (not active, not "
        "line-commented, not block-commented). These need a NEW deftype added — "
        "they aren't activation candidates.",
        "",
        "Ranked by: `3·log2(1+failing_refs) + log2(1+refs) − 2·prereqs + "
        "(parent_ok ? 10 : 0) + complexity_bonus`",
        "",
        "- **failing_refs** — # of split-failed/real-partial files mentioning the type",
        "- **refs** — # of all decomp files mentioning the type",
        "- **prereqs** — # of parents in the chain that ALSO need activation first",
        "- **complexity** — clean-copy (matches jak3) / minor-surgery / major-surgery / no-jak3-source",
        "",
    ]
    if not entries:
        lines.append("**Queue is empty — no pure-discovery types found.**")
        lines.append("")
        lines.append("This means every type the decomp wants is already present in "
                     "jakx all-types.gc (possibly block-commented — see "
                     "`.jakx_watch/activation_queue.md` for those).")
        return "\n".join(lines)

    lines.append(
        "| # | name | parent | parent-ok | failing-refs | refs | prereqs | complexity | jak3 | score |"
    )
    lines.append(
        "|---|------|--------|:---------:|-------------:|-----:|:-------:|------------|:----:|------:|"
    )
    for i, e in enumerate(entries[:20], 1):
        pflag = "✓" if e["parent_ok"] else ""
        prereq_str = str(e["prereq_count"])
        if e["prereq_count"] > 0:
            prereq_str += f" ({', '.join(e['prereqs'][:3])}" + (
                "…" if e["prereq_count"] > 3 else ""
            ) + ")"
        jak3_cell = f"L{e['jak3_line']}" if e["jak3_line"] else "—"
        lines.append(
            f"| {i} | `{e['name']}` | `{e['parent'] or '—'}` | {pflag} | "
            f"{e['failing_refs']} | {e['refs']} | {prereq_str} | "
            f"{e['complexity']} | {jak3_cell} | {e['score']} |"
        )
    lines.append("")
    lines.append("## How to use this queue")
    lines.append("")
    lines.append(
        "1. Start with entries where `parent-ok ✓` AND `prereqs=0` — they're "
        "self-contained."
    )
    lines.append(
        "2. `clean-copy` complexity: paste jak3's deftype body verbatim "
        "(`python3 scripts/jakx_watch/emit_stub.py --name NAME`)."
    )
    lines.append(
        "3. `minor-surgery` complexity: jak3 body has matching method-count/size "
        "but different fields. Use jak3 as skeleton, adjust fields."
    )
    lines.append(
        "4. `major-surgery` / `no-jak3-source`: write fresh deftype using "
        "regen's new-all-types.gc body as reference."
    )
    lines.append(
        "5. After adding a batch of 5–10 entries, re-run `bash "
        "scripts/jakx_watch/run.sh` to refresh rankings."
    )
    return "\n".join(lines)


def persist(entries: list[dict]) -> None:
    if not LATEST.exists():
        return
    try:
        snap = json.loads(LATEST.read_text())
    except Exception:
        return
    compact = []
    for e in entries[:20]:
        compact.append({
            "name": e["name"],
            "parent": e["parent"],
            "parent_ok": e["parent_ok"],
            "refs": e["refs"],
            "failing_refs": e["failing_refs"],
            "complexity": e["complexity"],
            "prereq_count": e["prereq_count"],
            "score": e["score"],
        })
    snap["discovery_queue"] = {"top": compact, "count": len(entries)}
    LATEST.write_text(json.dumps(snap, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regen", help="Path to new-all-types.gc (default: auto)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    regen_path = Path(args.regen) if args.regen else pick_regen()
    if regen_path is None:
        # Graceful degradation: without regen we can't produce the queue.
        # Still write a placeholder md so the file exists for agents.
        empty_md = (
            "# jakx discovery priority queue\n"
            "\n"
            "**No regenerated all-types.gc available.**\n"
            "\n"
            "Run `JAKX_WATCH_FORCE=1 bash scripts/jakx_watch/run.sh` to produce "
            "`.jakx_watch/decomp_out/jakx/new-all-types.gc`, then re-run this "
            "script.\n"
        )
        if not args.no_write:
            QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
            QUEUE_MD.write_text(empty_md)
        print("no regen file — wrote placeholder", file=sys.stderr)
        return 0

    jakx = parse_deftypes_with_parent(JAKX_TYPES)
    regen = parse_deftypes_with_parent(regen_path)
    jak3 = parse_deftypes_with_parent(JAK3_TYPES)

    per_file = {}
    if LATEST.exists():
        try:
            per_file = json.loads(LATEST.read_text()).get("per_file", {})
        except Exception:
            pass

    disasm_dir = pick_decomp_dir()
    entries = compose_queue(jakx, regen, jak3, disasm_dir, per_file)

    print(f"pure-discovery types: {len(entries)}")
    if entries:
        print(f"top 10:")
        for i, e in enumerate(entries[:10], 1):
            pflag = "P!" if e["parent_ok"] else "  "
            print(
                f"  {i:>2}. [{pflag}] {e['score']:>6.2f}  "
                f"{e['name']:<40}  {e['complexity']:<14}  "
                f"prereq={e['prereq_count']}  fref={e['failing_refs']}"
            )

    if not args.no_write:
        md = format_md(entries, regen_path, len(entries))
        QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_MD.write_text(md)
        persist(entries)
        print(f"\nwrote {QUEUE_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
