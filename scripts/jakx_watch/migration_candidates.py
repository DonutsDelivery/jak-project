#!/usr/bin/env python3
"""Migration-readiness audit for hand-port debt deletion.

Walks goal_src/jakx/engine/**/*.gc (hand-port transition debt per
project_jakx_release_model.md) and cross-references each against the current
decomp output + offline-test state from the most recent jakx_watch snapshot.

A hand-port is a "deletion candidate" when the corresponding decomp output
exists and the decompile looks good enough to replace the hand-port:
  * decomp is real-clean (ideal)         — preferred
  * decomp is real-partial with few errs — acceptable with review
  * offline-test green                   — readiness++
  * SCAFFOLDING / hand-port markers      — confirms debt status

We do NOT delete anything. This only produces a prioritized list for Agents
1/2 to consume when between cluster-activation batches.

Also flags update-from-decomp APPEND RISK per
reference_jakx_migration_tooling.md: if the hand-port defines named methods
(evaluate!, update!, etc.) and the corresponding deftype in jakx/all-types.gc
doesn't declare those method names in its :methods block, the migration tool
will APPEND the decomp's generic method-N forms to the hand-port rather than
merge them — producing duplicates. Fix before migrating: name the methods in
all-types.gc.

Outputs:
  * .jakx_watch/migration_candidates.md      — human-readable ranked list
  * latest.json[migration_candidates]        — persisted for measure.py
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HAND_PORT_ROOT = ROOT / "goal_src" / "jakx" / "engine"
JAKX_ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
OUTPUT_MD = ROOT / ".jakx_watch" / "migration_candidates.md"

RE_DEFMETHOD = re.compile(
    r"^\(defmethod\s+([\w<>!?:\-\+\*/=]+)\s+([\w<>!?:\-\+\*/=]+)",
    re.MULTILINE,
)
RE_METHOD_N = re.compile(r"^method-\d+$")

# Canonical GOAL methods inherited from structure/basic. Overriding them in a
# subtype does NOT require re-declaring them in that subtype's :methods block,
# so a hand-port (defmethod new FOO ...) is not an append-bug signal just
# because FOO's :methods doesn't list new.
INHERITED_BASE_METHODS = frozenset({
    "new", "delete",                              # structure (0, 1)
    "print", "inspect", "length", "asize-of",     # basic (2–5)
    "copy", "relocate", "mem-usage",              # basic (6–8)
})
# Scaffolding / hand-port debt tags the memory flags as audit signals.
RE_SCAFFOLD = re.compile(
    r"(SCAFFOLDING|hand.?port|hand.?written|Ported from jak[23]|Stub\.)",
    re.IGNORECASE,
)


def pick_decomp_dir() -> Path:
    """Prefer the private jakx_watch decomp_out; fall back to the shared dir."""
    p = DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK
    return p


def load_latest_snap() -> dict | None:
    if not LATEST.exists():
        return None
    try:
        return json.loads(LATEST.read_text())
    except Exception as exc:
        print(f"warn: could not parse {LATEST.relative_to(ROOT)}: {exc}", file=sys.stderr)
        return None


def extract_deftype_method_names(all_types_text: str) -> dict[str, set[str]]:
    """Parse jakx all-types.gc deftype :methods lists.

    Returns {type_name: {method_name, ...}}. Only picks up ACTIVE deftypes
    (ignores line-commented / block-commented). Method-N slot names are
    excluded — those are the ones that trigger the append bug.
    """
    # Coarse block-comment strip so we don't index commented-out deftypes.
    # jakx uses #| ... |# blocks around speculative types. Strip them first.
    stripped = re.sub(r"#\|.*?\|#", "", all_types_text, flags=re.DOTALL)
    # Also strip line comments so we don't match commented ;; (deftype ...)
    # Note: leaves the code structure intact for our regex.
    lines = []
    for raw in stripped.splitlines():
        s = raw.lstrip()
        if s.startswith(";;") or s.startswith(";"):
            continue
        lines.append(raw)
    text = "\n".join(lines)

    out: dict[str, set[str]] = {}
    # Find (deftype NAME (PARENT) ... :methods ( ... ) ...) by scanning with a
    # depth-counting tokenizer because nested parens inside :methods defeat a
    # naive regex.
    i = 0
    n = len(text)
    while True:
        m = re.search(r"\(deftype\s+([\w<>!?:\-\+\*/=]+)\s+\(", text[i:])
        if not m:
            break
        type_name = m.group(1)
        start = i + m.end() - 1  # points at the '(' after the parent list opens
        # Walk to the end of the whole deftype s-exp via paren depth.
        # First skip past the parent list.
        depth = 1
        j = start + 1
        while j < n and depth > 0:
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            j += 1
        # parent-list end is now at j. Walk onward to end of deftype:
        # the deftype itself was opened before `m.start()` — find that '('.
        # Simpler: just search for :methods (...) within a bounded window.
        # Deftypes rarely exceed ~4 KB; scan 6 KB to be safe.
        window_end = min(n, j + 6000)
        window = text[j:window_end]
        mm = re.search(r":methods\s*\(", window)
        if mm:
            mstart = j + mm.end() - 1  # at the '('
            depth = 1
            k = mstart + 1
            while k < n and depth > 0:
                c = text[k]
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                k += 1
            methods_body = text[mstart + 1 : k - 1]
            # Each entry is `(NAME (args) ret N)` or similar. Pull names.
            names = set()
            for mn in re.finditer(
                r"\(\s*([\w<>!?:\-\+\*/=]+)\s+\(",
                methods_body,
            ):
                name = mn.group(1)
                if RE_METHOD_N.match(name):
                    continue
                names.add(name)
            out.setdefault(type_name, set()).update(names)
        # Advance past this deftype's open paren to avoid re-matching it.
        i = i + m.end()
    return out


def hand_port_files() -> list[Path]:
    if not HAND_PORT_ROOT.exists():
        return []
    return sorted(HAND_PORT_ROOT.rglob("*.gc"))


def scan_hand_port(path: Path) -> dict:
    text = path.read_text(errors="replace")
    head = "\n".join(text.splitlines()[:80])
    scaffold_markers = RE_SCAFFOLD.findall(head) + RE_SCAFFOLD.findall(
        "\n".join(text.splitlines()[80:200])
    )
    # Collect (defmethod NAME TYPE ...) pairs where NAME is not method-N.
    named_methods: list[tuple[str, str]] = []
    for m in RE_DEFMETHOD.finditer(text):
        name, tp = m.group(1), m.group(2)
        if RE_METHOD_N.match(name):
            continue
        named_methods.append((name, tp))
    return {
        "scaffold_marker_count": len(scaffold_markers),
        "scaffold_samples": scaffold_markers[:3],
        "named_methods": named_methods,
        "lines": text.count("\n") + 1,
    }


def append_bug_risk(
    named_methods: list[tuple[str, str]],
    deftype_methods: dict[str, set[str]],
) -> list[tuple[str, str]]:
    """Return list of (method, type) pairs that will trigger the append bug.

    A pair triggers the bug when the hand-port defines a named method for a
    type whose jakx all-types.gc deftype either (a) doesn't exist at all or
    (b) exists but doesn't declare that method name in its :methods block.
    The user must name the method in all-types.gc before running
    update-from-decomp, or the tool will append the decomp's method-N form.
    """
    risky: list[tuple[str, str]] = []
    for method, tp in named_methods:
        if method in INHERITED_BASE_METHODS:
            continue  # inherited from structure/basic; no :methods entry needed
        declared = deftype_methods.get(tp)
        if declared is None:
            risky.append((method, tp))
            continue
        if method not in declared:
            risky.append((method, tp))
    return risky


def score_candidate(
    category: str,
    failed: int,
    error: int,
    offline_green: bool,
    offline_amber: bool,
    scaffold: int,
    append_risks: int,
) -> float:
    """Higher = more ready to migrate.

    Rationale:
      +50 for real-clean  / +20 for real-partial
      +30 for offline-test green
      -10 for offline-test amber (decompiles but fails goalc — not ready)
      -0.25 per decomp marker (stub or inline error)
      +5   if hand-port has scaffolding markers (confirms debt)
      -2   per append-bug risk pair (soft penalty; fixable upstream)
    """
    s = 0.0
    if category == "real-clean":
        s += 50.0
    elif category == "real-partial":
        s += 20.0
    if offline_green:
        s += 30.0
    if offline_amber:
        s -= 10.0
    s -= 0.25 * (failed + error)
    if scaffold:
        s += 5.0
    s -= 2.0 * append_risks
    return round(s, 2)


def build_candidates(
    decomp_dir: Path,
    snap: dict | None,
    deftype_methods: dict[str, set[str]],
) -> list[dict]:
    per_file = (snap or {}).get("per_file", {}) if snap else {}
    ot = (snap or {}).get("offline_test") or {}
    green = set(ot.get("green") or [])
    amber = set(ot.get("amber") or [])

    hp_files = hand_port_files()
    out: list[dict] = []
    for hp in hp_files:
        name = hp.stem
        # Skip obvious _h.gc hand-ports only if no matching decomp — we still
        # want them listed if a decomp exists.
        disasm = decomp_dir / f"{name}_disasm.gc"
        if not disasm.exists():
            continue
        pf = per_file.get(name) or {}
        cat = pf.get("category", "unknown")
        if cat not in ("real-clean", "real-partial"):
            # Decomp exists but is split-failed / static-only — not migratable.
            continue
        failed = int(pf.get("failed", 0))
        error = int(pf.get("error", 0))
        hp_scan = scan_hand_port(hp)
        risky = append_bug_risk(hp_scan["named_methods"], deftype_methods)
        is_green = name in green
        is_amber = name in amber
        score = score_candidate(
            cat,
            failed,
            error,
            offline_green=is_green,
            offline_amber=is_amber,
            scaffold=hp_scan["scaffold_marker_count"],
            append_risks=len(risky),
        )
        out.append(
            {
                "name": name,
                "hand_port": str(hp.relative_to(ROOT)),
                "decomp_out": str(disasm.relative_to(ROOT)),
                "category": cat,
                "failed": failed,
                "error": error,
                "lines_handport": hp_scan["lines"],
                "scaffold_markers": hp_scan["scaffold_marker_count"],
                "offline_test": "green"
                if is_green
                else ("amber" if is_amber else "untested"),
                "named_methods": hp_scan["named_methods"][:12],
                "named_method_count": len(hp_scan["named_methods"]),
                "append_bug_risks": risky[:12],
                "append_bug_risk_count": len(risky),
                "score": score,
            }
        )
    out.sort(key=lambda c: -c["score"])
    return out


def format_md(candidates: list[dict], decomp_dir: Path) -> str:
    lines: list[str] = []
    lines.append("# jakx_watch · migration candidates (delete-ready hand-ports)")
    lines.append("")
    lines.append(
        f"Scanned {len(hand_port_files())} hand-port files under "
        f"`goal_src/jakx/engine/**` against decomp output `{decomp_dir.relative_to(ROOT)}`."
    )
    lines.append("")
    if not candidates:
        lines.append("No delete-ready candidates found. (Either no hand-ports have "
                     "matching decomp output, or matches are still split-failed.)")
        return "\n".join(lines)

    by_cat = collections.Counter(c["category"] for c in candidates)
    by_ot = collections.Counter(c["offline_test"] for c in candidates)
    lines.append(f"Candidates: **{len(candidates)}**")
    lines.append("")
    lines.append(f"- by decomp category: " + ", ".join(f"{k}={v}" for k, v in by_cat.items()))
    lines.append(f"- by offline-test:   " + ", ".join(f"{k}={v}" for k, v in by_ot.items()))
    append_risk_cands = sum(1 for c in candidates if c["append_bug_risk_count"])
    lines.append(f"- append-bug risk candidates: **{append_risk_cands}** "
                 f"(need method-name hoist into all-types.gc before migration)")
    lines.append("")

    lines.append("## top 10 by readiness score")
    lines.append("")
    lines.append("| # | score | cat | OT | name | hand-port | decomp | markers | append-risk |")
    lines.append("|---|-------|-----|----|------|-----------|--------|---------|-------------|")
    for i, c in enumerate(candidates[:10], 1):
        lines.append(
            f"| {i} | {c['score']} | {c['category']} | {c['offline_test']} | "
            f"`{c['name']}` | `{c['hand_port']}` | `{c['decomp_out']}` | "
            f"{c['failed'] + c['error']} | {c['append_bug_risk_count']} |"
        )
    lines.append("")

    # Call out the green candidates (highest confidence — offline-test passing).
    greens = [c for c in candidates if c["offline_test"] == "green"]
    if greens:
        lines.append("## GREEN candidates (offline-test passing — safest to migrate)")
        lines.append("")
        for c in greens:
            risk_note = ""
            if c["append_bug_risk_count"]:
                risk_note = (
                    f"  ⚠ append-bug risk ({c['append_bug_risk_count']} methods): "
                    + ", ".join(f"{m}→{t}" for m, t in c["append_bug_risks"][:6])
                )
            lines.append(f"- **{c['name']}**  (score={c['score']}, cat={c['category']})")
            lines.append(f"    hand-port: `{c['hand_port']}`")
            lines.append(f"    decomp:    `{c['decomp_out']}`")
            if risk_note:
                lines.append(risk_note)
        lines.append("")

    # Append-bug warning block: anything with risk gets listed explicitly so
    # Agents 1/2 can fix all-types.gc before running update-from-decomp.
    risky_all = [c for c in candidates if c["append_bug_risk_count"]]
    if risky_all:
        lines.append("## append-bug risk detail")
        lines.append("")
        lines.append(
            "Hand-ports below define named methods whose jakx all-types.gc deftype "
            "doesn't declare them. `update-from-decomp.py` will APPEND (duplicate) "
            "the decomp's method-N forms rather than merge. Before migrating any of "
            "these: add the method names to the deftype's `:methods` block in "
            "`decompiler/config/jakx/all-types.gc`."
        )
        lines.append("")
        for c in risky_all[:25]:
            pairs = ", ".join(f"{m}→{t}" for m, t in c["append_bug_risks"][:8])
            extra = f" +{c['append_bug_risk_count'] - 8} more" if c["append_bug_risk_count"] > 8 else ""
            lines.append(f"- `{c['name']}` ({c['append_bug_risk_count']} methods): {pairs}{extra}")
        if len(risky_all) > 25:
            lines.append(f"- ... +{len(risky_all) - 25} more")
        lines.append("")

    lines.append("## all candidates")
    lines.append("")
    lines.append("| # | score | cat | OT | name | hand-port | decomp-markers | append-risk |")
    lines.append("|---|-------|-----|----|------|-----------|-----------------|-------------|")
    for i, c in enumerate(candidates, 1):
        lines.append(
            f"| {i} | {c['score']} | {c['category']} | {c['offline_test']} | "
            f"`{c['name']}` | `{c['hand_port']}` | {c['failed'] + c['error']} | "
            f"{c['append_bug_risk_count']} |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "Generated by `scripts/jakx_watch/migration_candidates.py`. Agents 1/2: "
        "consume this when between cluster-activation batches. Delete the hand-port "
        "only AFTER confirming (a) the decomp builds cleanly via goalc and (b) the "
        "smoke test hasn't regressed."
    )
    return "\n".join(lines)


def persist_into_snap(candidates: list[dict]) -> bool:
    if not LATEST.exists():
        return False
    try:
        snap = json.loads(LATEST.read_text())
    except Exception:
        return False
    # Trim the per-candidate payload for latest.json; top-20 + counts are plenty.
    compact = []
    for c in candidates[:20]:
        compact.append(
            {
                "name": c["name"],
                "hand_port": c["hand_port"],
                "decomp_out": c["decomp_out"],
                "category": c["category"],
                "offline_test": c["offline_test"],
                "failed": c["failed"],
                "error": c["error"],
                "score": c["score"],
                "append_bug_risk_count": c["append_bug_risk_count"],
                "scaffold_markers": c["scaffold_markers"],
            }
        )
    snap["migration_candidates"] = {
        "count": len(candidates),
        "by_category": dict(collections.Counter(c["category"] for c in candidates)),
        "by_offline_test": dict(collections.Counter(c["offline_test"] for c in candidates)),
        "append_bug_risk_count": sum(1 for c in candidates if c["append_bug_risk_count"]),
        "top": compact,
    }
    LATEST.write_text(json.dumps(snap, indent=2))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--decomp-out",
        help=f"Decompiler output dir (default picks {DECOMP_OUT_PRIMARY.relative_to(ROOT)} "
             f"if present, else {DECOMP_OUT_FALLBACK.relative_to(ROOT)})",
    )
    ap.add_argument("--no-write", action="store_true",
                    help="Don't write migration_candidates.md or update latest.json")
    args = ap.parse_args()

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"decomp dir missing: {decomp_dir}", file=sys.stderr)
        return 1
    if not HAND_PORT_ROOT.exists():
        print(f"hand-port root missing: {HAND_PORT_ROOT}", file=sys.stderr)
        return 1

    snap = load_latest_snap()
    if snap is None:
        print("warn: no latest snapshot — scoring will omit offline-test signals",
              file=sys.stderr)

    deftype_methods: dict[str, set[str]] = {}
    if JAKX_ALL_TYPES.exists():
        deftype_methods = extract_deftype_method_names(JAKX_ALL_TYPES.read_text())

    candidates = build_candidates(decomp_dir, snap, deftype_methods)

    # Console summary (short; the .md file has the detail).
    print(f"migration candidates: {len(candidates)}")
    if candidates:
        by_cat = collections.Counter(c["category"] for c in candidates)
        by_ot = collections.Counter(c["offline_test"] for c in candidates)
        print(f"  by category:    {dict(by_cat)}")
        print(f"  by offline-test:{dict(by_ot)}")
        risky = sum(1 for c in candidates if c["append_bug_risk_count"])
        print(f"  append-bug risk candidates: {risky}")
        print()
        print(f"  top 10 (higher score = more ready):")
        for i, c in enumerate(candidates[:10], 1):
            risk_flag = f" ⚠{c['append_bug_risk_count']}" if c["append_bug_risk_count"] else ""
            print(
                f"    {i:>2}. {c['score']:>6.2f}  [{c['category']:>12}]  "
                f"[{c['offline_test']:>7}]  {c['name']}{risk_flag}"
            )

    if not args.no_write:
        md = format_md(candidates, decomp_dir)
        OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_MD.write_text(md)
        print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
        if persist_into_snap(candidates):
            print(f"persisted into {LATEST.relative_to(ROOT)}[migration_candidates]",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
