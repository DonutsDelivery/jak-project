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
RE_DEFINE_EXTERN = re.compile(r"^\s*\(define-extern\s+([\w<>!?:\-\+\*/=]+)\s+\S+\s*\)")
CLOBBER_THRESHOLD = 59000


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


def find_pending_clobbers(text: str, active_types: set[str]) -> set[str]:
    """Return the set of type names that have an active (define-extern FOO ...)
    at line > CLOBBER_THRESHOLD AND an active deftype earlier in the file.

    An 'active' define-extern is one that is not line-commented (;;) and not
    inside a block comment (#| ... |#).
    """
    lines = text.splitlines()

    # Build block-comment map
    in_block = [False] * len(lines)
    block = False
    for idx, raw in enumerate(lines):
        if "#|" in raw:
            after_open = raw.split("#|", 1)[1]
            if "|#" in after_open:
                in_block[idx] = True
                continue
            block = True
        if block:
            in_block[idx] = True
            if "|#" in raw:
                block = False

    clobbered: set[str] = set()
    for idx, raw in enumerate(lines):
        lineno = idx + 1
        if lineno <= CLOBBER_THRESHOLD:
            continue
        if in_block[idx]:
            continue
        if re.match(r"^\s*;;", raw):
            continue
        m = RE_DEFINE_EXTERN.match(raw)
        if m and m.group(1) in active_types:
            clobbered.add(m.group(1))
    return clobbered


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
    types_text = types_path.read_text(errors="replace")
    all_types = parse_deftypes(types_text)
    active = {n for n, v in all_types.items()
              if not v["commented"] and not v.get("block_commented")}
    commented_names = {n for n in all_types if n not in active}
    print(f"active={len(active)}  commented={len(commented_names)}")

    # Find active types that are clobbered by a late define-extern
    pending_clobbers = find_pending_clobbers(types_text, active)
    print(f"pending-clobbers (active define-extern >L{CLOBBER_THRESHOLD}): {len(pending_clobbers)}")

    print("building clusters...")
    clusters = build_clusters(all_types)
    # Only keep clusters that have at least 1 member
    clusters = {r: c for r, c in clusters.items() if c["types"]}
    print(f"clusters (active roots with commented subtypes): {len(clusters)}")

    # Load split-failed set from latest.json (authoritative per-file categories)
    split_failed_stems: set[str] = set()
    latest_json = ROOT / ".jakx_watch" / "history" / "latest.json"
    try:
        import json as _json
        _data = _json.loads(latest_json.read_text())
        per_file = _data.get("per_file", {})
        split_failed_stems = {s for s, v in per_file.items()
                              if v.get("category") == "split-failed"}
    except Exception:
        pass
    print(f"split-failed files (from latest.json): {len(split_failed_stems)}")

    print(f"building ref index for {len(commented_names)} commented types...")
    ref_index = build_ref_index(decomp_dir, commented_names)

    # Build a split-failed-only ref index: {type_name: {split_failed_file_stems}}
    sf_ref_index: dict[str, set[str]] = {
        t: refs & split_failed_stems for t, refs in ref_index.items()
    }

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

    # Build type → cluster_root reverse map for cascade analysis
    type_to_cluster: dict[str, str] = {}
    for root, info in clusters.items():
        for t in info["types"]:
            type_to_cluster[t] = root

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

        # Cascade analysis: group c_unlock_set members by their cluster root.
        # cascades_to = {other_cluster_root: count_of_types_unlocked_in_that_cluster}
        # This answers: "activating THIS cluster unblocks N types in cluster Z."
        cascades_to: dict[str, int] = collections.Counter()
        for t in c_unlock_set:
            other_root = type_to_cluster.get(t)
            if other_root and other_root != root:
                cascades_to[other_root] += 1
        # Sort by count descending for display
        cascades_to_sorted = sorted(cascades_to.items(), key=lambda x: -x[1])

        # Net split-failed files unblocked: union of SF files that reference
        # any type in THIS cluster + any type in cascade target clusters.
        # This is the upper-bound count of split-failed files that could
        # unblock if this cluster (and its immediate cascades) are activated.
        sf_direct: set[str] = set()
        for t in cluster_types:
            sf_direct |= sf_ref_index.get(t, set())

        sf_cascade: set[str] = set()
        for other_root, _ in cascades_to_sorted:
            other_cluster = clusters.get(other_root, {})
            for t in other_cluster.get("types", []):
                sf_cascade |= sf_ref_index.get(t, set())

        net_sf_files = sf_direct | sf_cascade

        # Count how many types in this cluster (including root) have pending clobbers
        clobber_count = sum(
            1 for t in cluster_types if t in pending_clobbers
        ) + (1 if root in pending_clobbers else 0)

        ranked.append({
            "root": root,
            "size": size,
            "max_depth": max_depth,
            "file_refs": len(files_union),
            "total_refs": total_refs,
            "ref_per_cost": ref_per_cost,
            "c_unlock": c_unlock,
            "cascades_to": cascades_to_sorted,
            "sf_direct": len(sf_direct),
            "sf_cascade": len(sf_cascade),
            "net_sf": len(net_sf_files),
            "pending_clobber": clobber_count,
            "root_clobbered": root in pending_clobbers,
            "types": info["types"],
            "depths": info["depths"],
        })

    # Primary: net_sf (split-failed files directly unblocked — A2's actionable metric)
    # Secondary: ref_per_cost (efficiency of activation work)
    # Tertiary: file_refs (total file coverage including non-SF files)
    ranked.sort(key=lambda r: (-r["net_sf"], -r["ref_per_cost"], -r["file_refs"]))

    # Console summary
    print(f"\nTop {min(args.top, len(ranked))} clusters by ref_per_cost:")
    print(f"  {'root':<30} {'size':>5} {'depth':>5} {'f_refs':>6} {'net_sf':>6} {'r/cost':>7} {'c_unlock':>8} {'clobber':>7}  cascades_to (top 2)")
    for r in ranked[: args.top]:
        clob_flag = f"*{r['pending_clobber']}" if r["pending_clobber"] else "-"
        top_cascades = ", ".join(f"{root}(+{n})" for root, n in r["cascades_to"][:2])
        print(
            f"  {r['root']:<30} {r['size']:>5} {r['max_depth']:>5} "
            f"{r['file_refs']:>6} {r['net_sf']:>6} {r['ref_per_cost']:>7.2f} "
            f"{r['c_unlock']:>8} {clob_flag:>7}  {top_cascades or '-'}"
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
        "- **clobber** — number of types in this cluster (including root) that have an active "
        "`(define-extern FOO object)` at line >59000. These will be re-clobbered at runtime "
        "even after deftype activation — the clobber line must be commented out first. "
        "`*N` = N types in cluster need clobber fix; `-` = clean.",
        "- **cascades_to** — top cluster(s) that become partially unblocked when this cluster "
        "is activated (format: `cluster-root(+N)` where N = types in that cluster that "
        "reference types from this cluster). Activating high-cascade clusters chains into the "
        "next cluster for free.",
        "- **net_sf** — **the key ranking signal for A2**: union of split-failed files that "
        "reference any type in this cluster OR in any cascade target cluster. This is the "
        "upper-bound count of split-failed files that could unblock if this cluster "
        "(and immediate cascades) are activated. `sf_d+c` = direct + cascade breakdown.",
        "",
        "| # | r/cost | root (active anchor) | size | depth | f_refs | net_sf | sf_d+c | c_unlock | clobber | cascades_to |",
        "|---|-------:|---------------------|-----:|------:|-------:|-------:|-------:|---------:|--------:|-------------|",
    ]
    for i, r in enumerate(ranked[: args.top], 1):
        clob_cell = f"\\*{r['pending_clobber']}" if r["pending_clobber"] else "-"
        cascade_cell = ", ".join(f"`{root}`(+{n})" for root, n in r["cascades_to"][:2]) or "-"
        sf_breakdown = f"{r['sf_direct']}+{r['sf_cascade']}"
        lines.append(
            f"| {i} | {r['ref_per_cost']:.2f} | `{r['root']}` | "
            f"{r['size']} | {r['max_depth']} | {r['file_refs']} | {r['net_sf']} | {sf_breakdown} | "
            f"{r['c_unlock']} | {clob_cell} | {cascade_cell} |"
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
        root_clob = " ⚠ root-clobbered" if r["root_clobbered"] else ""
        lines.append(f"### `{r['root']}` (size={r['size']}, depth={r['max_depth']}, f_refs={r['file_refs']}, c_unlock={r['c_unlock']}, clobber={r['pending_clobber']}){root_clob}")
        lines.append("")
        lines.append("| depth | type | file_refs | clobber |")
        lines.append("|------:|------|----------:|---------|")
        for t in sorted(r["types"], key=lambda t: (r["depths"][t], t)):
            d = r["depths"][t]
            fr = len(ref_index.get(t, set()))
            clob = "⚠" if t in pending_clobbers else ""
            lines.append(f"| {d} | `{t}` | {fr} | {clob} |")
        lines.append("")

    # Cascade chain section: show top 20 clusters with their best cascade target
    # Only include clusters that cascade into at least one other
    cascade_entries = [(r["root"], r["cascades_to"]) for r in ranked if r["cascades_to"]]
    cascade_entries.sort(key=lambda x: -(x[1][0][1] if x[1] else 0))
    lines += [
        "## Cross-cluster cascade graph",
        "",
        "Activating cluster **A** puts these types in cluster **B** one dependency closer "
        "to activation. Use this to plan cluster chains: pick A first if it has a high-scoring "
        "B that follows naturally.",
        "",
        "Format: `cluster-A → cluster-B (+N types in B reference types in A)`",
        "",
    ]
    for root, cascades in cascade_entries[:20]:
        top = cascades[:3]
        targets = " → ".join(f"`{cr}`(+{n})" for cr, n in top)
        lines.append(f"- `{root}` → {targets}")
    lines.append("")

    lines += [
        "## How to use",
        "",
        "1. Pick the cluster with the highest **net_sf** (split-failed files that could unblock). "
        "   Use **r/cost** as tiebreaker.",
        "2. Work top-down by **depth** within the cluster: activate depth=1 types first,",
        "   then depth=2, etc. Each layer depends on the previous being active.",
        "3. Use `scripts/jakx_watch/emit_stub.py --name TYPE` to generate the activation body.",
        "4. Re-run `bash scripts/jakx_watch/run.sh` after each depth layer to measure unblock delta.",
        "5. Cross-reference with `activation_queue.md` for per-type readiness scores.",
        "6. Use the **cascade graph** above to plan multi-cluster chains: if cluster A cascades",
        "   into B(+10), activate A then immediately proceed to B.",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
