#!/usr/bin/env python3
"""Cluster impact simulator — rank commented-deftype activation clusters.

For Agent 2's activation work: groups all 1126 commented types into clusters
based on their nearest active ancestor, then ranks clusters by expected
unblock impact vs ordering cost.

For each cluster it computes:
  - size: how many commented types are in the cluster's subtree
  - file_refs: decomp files that reference ANY type in the cluster
  - depth: longest parent-first chain within the cluster (ordering cost)
  - ref_per_cost: file_refs / max(1, depth) — the prioritisation score
  - c_unlock: commented types OUTSIDE this cluster whose parent is one of this
    cluster's types. These become newly activatable when this cluster is
    activated. High c_unlock = cascade unblock (one cluster unlocks the next).

Ranking: higher ref_per_cost = more files unblocked per unit of activation work.

Output:
  .jakx_watch/cluster_impact.md    — ranked table + per-cluster type list
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
OUTPUT_MD = ROOT / ".jakx_watch" / "cluster_impact.md"

RE_DEFTYPE_START = re.compile(
    r"^\s*(?:#\|\s*)?(?:;;\s*)?\(deftype\s+([\w<>!?:\-\+\*/=]+)\s*"
)
RE_PARENT = re.compile(r"\(deftype\s+\S+\s+\((\S+)\)")


# ---------------------------------------------------------------------------
# Parser (reused from field_drift_scan / types_drift)
# ---------------------------------------------------------------------------

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
        p_m = RE_PARENT.search(body)
        prev = out.get(name)
        this_active = not commented and not block_commented
        prev_active = prev and not prev["commented"] and not prev.get("block_commented", False)
        if prev is None or (this_active and not prev_active):
            out[name] = {
                "commented": commented,
                "block_commented": block_commented,
                "body": body,
                "first_line": start_i + 1,
                "parent": p_m.group(1) if p_m else None,
            }
    return out


# ---------------------------------------------------------------------------
# Cluster building
# ---------------------------------------------------------------------------

def build_clusters(
    all_types: dict,
) -> dict[str, dict]:
    """Return {root_active_type: cluster_info} for each active type that has
    commented subtypes hanging from it.

    A 'cluster' here is the commented subtree rooted at an active type.
    If a commented type A has a commented parent B which has an active parent C,
    then A belongs to C's cluster (transitively).

    cluster_info keys:
      types      — list of commented type names in the cluster
      depths     — {type_name: min_hops_from_active_root}
      max_depth  — longest chain within the cluster
    """
    active = {n for n, v in all_types.items()
              if not v["commented"] and not v.get("block_commented")}
    commented = {n: v for n, v in all_types.items()
                 if v["commented"] or v.get("block_commented")}

    # For each commented type, find its nearest active ancestor.
    # Walk parent chain, counting hops through the commented graph.
    nearest_active: dict[str, tuple[str, int]] = {}  # name → (active_root, depth)
    parent_of: dict[str, str | None] = {n: v["parent"] for n, v in all_types.items()}

    def find_root(name: str, visiting: set[str]) -> tuple[str, int] | None:
        if name in nearest_active:
            return nearest_active[name]
        if name in visiting:
            return None
        if name in active:
            return (name, 0)
        parent = parent_of.get(name)
        if parent is None or parent not in all_types:
            return None
        visiting = visiting | {name}
        result = find_root(parent, visiting)
        if result is None:
            return None
        root, hops = result
        return (root, hops + 1)

    for name in commented:
        r = find_root(name, set())
        if r is not None:
            nearest_active[name] = r

    # Group commented types by active root
    clusters: dict[str, dict] = collections.defaultdict(
        lambda: {"types": [], "depths": {}}
    )
    for name, (root, depth) in nearest_active.items():
        clusters[root]["types"].append(name)
        clusters[root]["depths"][name] = depth

    # Compute max_depth for each cluster
    result = {}
    for root, info in clusters.items():
        result[root] = {
            "types": sorted(info["types"]),
            "depths": info["depths"],
            "max_depth": max(info["depths"].values()) if info["depths"] else 0,
        }
    return result


# ---------------------------------------------------------------------------
# Reference counting
# ---------------------------------------------------------------------------

def build_ref_index(decomp_dir: Path, type_names: set[str]) -> dict[str, set[str]]:
    """Return {type_name: {file_stems}} for each name in type_names.

    Single-pass: scan each file once and collect all type-like tokens, then
    intersect with type_names. Much faster than per-name regex per file.
    """
    ref: dict[str, set[str]] = collections.defaultdict(set)
    if not decomp_dir.exists():
        return ref
    # Pre-compile one big alternation for the target names sorted longest-first.
    sorted_names = sorted(type_names, key=len, reverse=True)
    # Chunk into batches to avoid regex limits
    BATCH = 200
    batches = [sorted_names[i: i + BATCH] for i in range(0, len(sorted_names), BATCH)]
    compiled_batches = [
        re.compile(r"(?<![a-z0-9\-])(" + "|".join(re.escape(n) for n in batch) + r")(?![a-z0-9\-])")
        for batch in batches
    ]

    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        stem = fp.name[: -len("_disasm.gc")]
        try:
            text = fp.read_text(errors="replace")
        except OSError:
            continue
        for pat in compiled_batches:
            for m in pat.finditer(text):
                ref[m.group(1)].add(stem)
    return ref


def pick_decomp_dir() -> Path:
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists() and any(p.glob("*_disasm.gc")):
            return p
    return DECOMP_PRIMARY


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", default=str(CURRENT_TYPES))
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--detail", type=str, default=None,
                    help="Show full type list for a specific cluster root")
    args = ap.parse_args()

    types_path = Path(args.types)
    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()

    print(f"parsing {types_path.name}...")
    all_types = parse_deftypes(types_path.read_text(errors="replace"))
    active = {n for n, v in all_types.items()
              if not v["commented"] and not v.get("block_commented")}
    commented_names = {n for n in all_types if n not in active}
    print(f"active={len(active)}  commented={len(commented_names)}")

    print("building clusters...")
    clusters = build_clusters(all_types)
    # Only keep clusters that have at least 1 member
    clusters = {r: c for r, c in clusters.items() if c["types"]}
    print(f"clusters (active roots with commented subtypes): {len(clusters)}")

    print(f"building ref index for {len(commented_names)} commented types...")
    ref_index = build_ref_index(decomp_dir, commented_names)

    # Build a ref index for commented types: which OTHER commented types mention
    # each type name in their body? Used for c_unlock computation.
    # Single pass over all commented type bodies — build inverted index.
    commented_body_refs: dict[str, set[str]] = collections.defaultdict(set)
    # Build word-boundary pattern for all type names
    all_type_names = set(all_types.keys())
    for cname in commented_names:
        body = all_types[cname]["body"]
        # Find all word-boundary identifiers in body that are type names
        for m in re.finditer(r"[a-z][a-z0-9\-!?<>*/]*(?:-[a-z0-9!?<>*/]+)+|[a-z][a-z0-9!?<>*/]{2,}", body):
            tok = m.group(0)
            if tok in all_type_names and tok != cname:
                commented_body_refs[tok].add(cname)

    # Score each cluster
    ranked = []
    for root, info in clusters.items():
        cluster_types = set(info["types"])
        # Union of all files that reference any type in the cluster
        files_union: set[str] = set()
        for t in cluster_types:
            files_union |= ref_index.get(t, set())
        total_refs = sum(len(ref_index.get(t, set())) for t in cluster_types)
        max_depth = info["max_depth"]
        size = len(cluster_types)
        ref_per_cost = round(len(files_union) / max(1, max_depth), 2)

        # c_unlock: unique commented types OUTSIDE this cluster that reference
        # any type in this cluster in their body (field types, method args, etc.).
        # When this cluster is activated, these commented types have one fewer
        # unresolved dependency — a high count means cascading activation potential.
        c_unlock_set: set[str] = set()
        for t in cluster_types:
            for ref_by in commented_body_refs.get(t, set()):
                if ref_by not in cluster_types:
                    c_unlock_set.add(ref_by)
        c_unlock = len(c_unlock_set)

        ranked.append({
            "root": root,
            "size": size,
            "max_depth": max_depth,
            "file_refs": len(files_union),
            "total_refs": total_refs,
            "ref_per_cost": ref_per_cost,
            "c_unlock": c_unlock,
            "types": info["types"],
            "depths": info["depths"],
        })

    ranked.sort(key=lambda r: (-r["ref_per_cost"], -r["file_refs"]))

    # Console summary
    print(f"\nTop {min(args.top, len(ranked))} clusters by ref_per_cost:")
    print(f"  {'root':<30} {'size':>5} {'depth':>5} {'f_refs':>6} {'t_refs':>6} {'r/cost':>7} {'c_unlock':>8}")
    for r in ranked[: args.top]:
        print(
            f"  {r['root']:<30} {r['size']:>5} {r['max_depth']:>5} "
            f"{r['file_refs']:>6} {r['total_refs']:>6} {r['ref_per_cost']:>7.2f} {r['c_unlock']:>8}"
        )

    if args.detail:
        for r in ranked:
            if r["root"] == args.detail:
                print(f"\nCluster detail for '{args.detail}':")
                for t in sorted(r["types"], key=lambda t: r["depths"][t]):
                    d = r["depths"][t]
                    fr = len(ref_index.get(t, set()))
                    print(f"  depth={d}  {t:<40}  file_refs={fr}")
                break

    if args.no_write:
        return 0

    # Write markdown
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# jakx commented-deftype cluster impact",
        "",
        f"_source: scripts/jakx_watch/cluster_impact.py  ·  "
        f"total commented: {len(commented_names)}  ·  "
        f"clusters: {len(clusters)}_",
        "",
        "Each row is an **active type** that has one or more commented subtypes hanging "
        "from it. Activating a cluster means uncommenting (or porting) all types in the "
        "subtree rooted at that active type.",
        "",
        "Columns:",
        "- **size** — number of commented types in the subtree",
        "- **depth** — longest parent-first chain inside the cluster (ordering cost)",
        "- **f_refs** — decomp files that reference ≥1 type in the cluster (files potentially unblocked)",
        "- **t_refs** — total reference events across all types in the cluster",
        "- **r/cost** = f_refs / max(1, depth) — main rank signal: files-per-unit-of-ordering-work",
        "- **c_unlock** — unique commented types OUTSIDE this cluster that reference any type "
        "inside it (field types, method args, parent types). Activating this cluster resolves "
        "one dependency for each of these types — high c_unlock = cascade activation potential.",
        "",
        "| # | r/cost | root (active anchor) | size | depth | f_refs | t_refs | c_unlock |",
        "|---|-------:|---------------------|-----:|------:|-------:|-------:|---------:|",
    ]
    for i, r in enumerate(ranked[: args.top], 1):
        lines.append(
            f"| {i} | {r['ref_per_cost']:.2f} | `{r['root']}` | "
            f"{r['size']} | {r['max_depth']} | {r['file_refs']} | {r['total_refs']} | {r['c_unlock']} |"
        )

    lines += [
        "",
        "## Cluster detail (top 15)",
        "",
        "Types listed in parent-first order within each cluster. "
        "`depth` = hops from the active root. `fr` = decomp files referencing that type.",
        "",
    ]
    for r in ranked[:15]:
        lines.append(f"### `{r['root']}` (size={r['size']}, depth={r['max_depth']}, f_refs={r['file_refs']}, c_unlock={r['c_unlock']})")
        lines.append("")
        lines.append("| depth | type | file_refs |")
        lines.append("|------:|------|----------:|")
        for t in sorted(r["types"], key=lambda t: (r["depths"][t], t)):
            d = r["depths"][t]
            fr = len(ref_index.get(t, set()))
            lines.append(f"| {d} | `{t}` | {fr} |")
        lines.append("")

    lines += [
        "## How to use",
        "",
        "1. Pick the highest **r/cost** cluster whose **root** is an active base type.",
        "2. Work top-down by **depth** within the cluster: activate depth=1 types first,",
        "   then depth=2, etc. Each layer depends on the previous being active.",
        "3. Use `scripts/jakx_watch/emit_stub.py --name TYPE` to generate the activation body.",
        "4. Re-run `bash scripts/jakx_watch/run.sh` after each depth layer to measure unblock delta.",
        "5. Cross-reference with `activation_queue.md` for per-type readiness scores.",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
