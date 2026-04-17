#!/usr/bin/env python3
"""Rank jak3 mips2c files + individual functions by impact on jakx decomp.

For each jak3_functions/*.cpp, find all functions it installs, grep them in
jakx's _disasm.gc output, and score by (bucket of containing file, error
count of containing file).

Higher score = porting that .cpp could unblock more stubs.

Also writes `.jakx_watch/mips2c_queue.md` with a ranked top-10 per-FUNCTION
port list for self-serve batched work.
"""
from __future__ import annotations

import collections
import json
import math
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAK3_MIPS2C = ROOT / "game" / "mips2c" / "jak3_functions"
JAKX_MIPS2C = ROOT / "game" / "mips2c" / "jakx_functions"
JAKX_DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
JAKX_DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
QUEUE_MD = ROOT / ".jakx_watch" / "mips2c_queue.md"


def pick_decomp_dir() -> Path:
    """Prefer populated primary; fall back to shared dir."""
    for p in (JAKX_DECOMP_PRIMARY, JAKX_DECOMP_FALLBACK):
        if p.exists() and any(p.glob("*_disasm.gc")):
            return p
    return JAKX_DECOMP_PRIMARY


def estimate_block_count(cpp: Path, fn_name: str) -> int:
    """Count basic-block labels (L\\d+:) within the function's namespace block.

    MIPS2C cpp output uses `namespace FN_NAME { u64 execute(...) { ... } }` and
    has `case LABEL:` or `// LN:` block markers. Approximate block count by
    counting `L\\d+:` lines between the namespace open and close brace.
    """
    if not cpp.exists():
        return 0
    text = cpp.read_text(errors="replace")
    # Locate `namespace FN_NAME {`. jak3_functions mips2c cpp names use these
    # rules: `-` → `_`, `!`/`?`/`<`/`>`/`*` are stripped. We try a few variants.
    clean1 = fn_name.replace("-", "_")
    clean2 = re.sub(r"[!?<>*]", "", clean1)
    clean3 = re.sub(r"[!?<>*=/+]", "_", clean1)
    idx = -1
    for ns_name in (clean2, clean1, clean3, fn_name):
        needle = f"namespace {ns_name} {{"
        idx = text.find(needle)
        if idx >= 0:
            break
    if idx < 0:
        # Fall back to a looser regex-based lookup.
        m = re.search(rf"^namespace\s+\w*{re.escape(clean2[:20])}\w*\s*\{{", text, re.MULTILINE)
        if m:
            idx = m.start()
    if idx < 0:
        return 0
    # From idx, find the matching close brace for the namespace (brace depth).
    depth = 0
    i = idx
    started = False
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
            started = True
        elif c == "}":
            depth -= 1
            if started and depth == 0:
                break
        i += 1
    body = text[idx:i]
    # Count block_<num>: labels — that's the mips2c cpp emission convention.
    blocks = 0
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^block_\d+:", stripped):
            blocks += 1
    return blocks


RE_REG = re.compile(r'gLinkedFunctionTable\.reg\("([^"]+)"', re.MULTILINE)


def functions_in_cpp(cpp: Path) -> list[str]:
    text = cpp.read_text(errors="replace")
    out = []
    for m in RE_REG.finditer(text):
        # skip commented-out regs (line-level; crude but good enough)
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_head = text[line_start:m.start()].lstrip()
        if line_head.startswith("//"):
            continue
        out.append(m.group(1))
    return out


def main():
    snap = json.loads(LATEST.read_text())
    per_file = snap["per_file"]
    decomp_dir = pick_decomp_dir()

    jak3_fns: dict[Path, list[str]] = {}
    all_jak3_fns: set[str] = set()
    fn_to_cpp: dict[str, Path] = {}
    for cpp in sorted(JAK3_MIPS2C.glob("*.cpp")):
        fns = functions_in_cpp(cpp)
        jak3_fns[cpp] = fns
        all_jak3_fns.update(fns)
        for fn in fns:
            fn_to_cpp[fn] = cpp

    jakx_fns: set[str] = set()
    for cpp in sorted(JAKX_MIPS2C.glob("*.cpp")):
        jakx_fns.update(functions_in_cpp(cpp))

    print(f"jak3_functions: {len(jak3_fns)} .cpp files, {len(all_jak3_fns)} fns")
    print(f"jakx_functions: already has {len(jakx_fns)} fns")
    print(f"gap (jak3 but not jakx): {len(all_jak3_fns - jakx_fns)} fns")
    print()

    # For each jak3 fn not yet in jakx, find which jakx decomp files reference it.
    refs: dict[str, list[str]] = collections.defaultdict(list)
    candidate_fns = sorted(all_jak3_fns - jakx_fns)
    for fn in candidate_fns:
        # Use fixed-string grep; ripgrep handles parens.
        r = subprocess.run(
            ["grep", "-l", "-F", "-e", fn, "-r", str(decomp_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        files = [
            Path(line).stem.replace("_disasm", "")
            for line in r.stdout.strip().split("\n")
            if line.strip()
        ]
        refs[fn] = files

    # Score each jak3 cpp by SUM over its functions of:
    #   per referencing jakx file, weight * (stubs + errors)
    # weights: split-failed=1.5, real-partial=1.0, real-clean=0.3, static=0.0
    W = {"split-failed": 1.5, "real-partial": 1.0, "real-clean": 0.3, "static-only": 0.0}
    cpp_score: dict[Path, float] = {}
    cpp_breakdown: dict[Path, list[tuple[str, str, str, int, float]]] = {}

    for cpp, fns in jak3_fns.items():
        score = 0.0
        breakdown = []
        for fn in fns:
            if fn in jakx_fns:
                continue
            for ref_file in refs.get(fn, []):
                pf = per_file.get(ref_file)
                if not pf:
                    continue
                cat = pf["category"]
                w = W.get(cat, 0.0)
                impact = pf["failed"] + pf["error"]
                contrib = w * impact
                score += contrib
                breakdown.append((fn, ref_file, cat, impact, contrib))
        cpp_score[cpp] = score
        cpp_breakdown[cpp] = breakdown

    ranked = sorted(cpp_score.items(), key=lambda kv: -kv[1])

    print("== jak3 mips2c .cpp files ranked by jakx unblock potential ==")
    print()
    print(f"{'score':>8}  {'file':30s}  notes")
    print("-" * 80)
    for cpp, score in ranked:
        note = ""
        files_hit = sorted({b[1] for b in cpp_breakdown[cpp]})
        if files_hit:
            note = f"{len(files_hit)} file(s) ref: {', '.join(files_hit[:4])}"
            if len(files_hit) > 4:
                note += f" +{len(files_hit)-4}"
        print(f"{score:8.1f}  {cpp.name:30s}  {note}")

    print()
    print("== top-3 cpp breakdown ==")
    for cpp, _score in ranked[:3]:
        bd = cpp_breakdown[cpp]
        if not bd:
            continue
        # collapse per (fn, ref_file)
        per_ref = collections.defaultdict(lambda: (0, "", 0.0))
        for fn, ref, cat, impact, contrib in bd:
            per_ref[(fn, ref)] = (impact, cat, contrib)
        print()
        print(f"--- {cpp.name} ---")
        print(f"  {'fn':40s}  {'ref file':28s}  {'bucket':14s}  impact  score")
        sorted_bd = sorted(per_ref.items(), key=lambda kv: -kv[1][2])
        for (fn, ref), (impact, cat, contrib) in sorted_bd[:15]:
            print(f"  {fn[:40]:40s}  {ref[:28]:28s}  {cat:14s}  {impact:5d}   {contrib:5.1f}")

    # --- per-function queue for self-serve batched porting ---
    write_function_queue(candidate_fns, refs, per_file, fn_to_cpp)


def write_function_queue(
    candidate_fns: list[str],
    refs: dict[str, list[str]],
    per_file: dict,
    fn_to_cpp: dict[str, Path],
) -> None:
    """Emit .jakx_watch/mips2c_queue.md top-10 ranked by jakx unblock.

    Each entry reports:
      * jak3 function name (what to port)
      * estimated block count (porting complexity proxy)
      * whether jak3_functions/<cpp> exists (source code availability)
      * whether any caller file is currently in split-failed state
      * top referencing files + their buckets
    """
    W_CAT = {"split-failed": 1.5, "real-partial": 1.0, "real-clean": 0.3, "static-only": 0.0}

    fn_entries = []
    for fn in candidate_fns:
        referencing = refs.get(fn, [])
        if not referencing:
            continue
        cpp = fn_to_cpp.get(fn)
        jak3_cpp_exists = cpp is not None and cpp.exists()
        blocks = estimate_block_count(cpp, fn) if jak3_cpp_exists else 0
        # Build per-caller impact list.
        caller_rows: list[tuple[str, str, int]] = []
        has_split_failed = False
        total_impact = 0.0
        for ref in referencing:
            pf = per_file.get(ref)
            if not pf:
                continue
            cat = pf.get("category", "unknown")
            impact = int(pf.get("failed", 0)) + int(pf.get("error", 0))
            caller_rows.append((ref, cat, impact))
            total_impact += W_CAT.get(cat, 0.0) * impact
            if cat == "split-failed":
                has_split_failed = True
        if not caller_rows:
            continue
        # Score prioritizes split-failed callers (biggest unblock) and
        # penalizes complexity (many blocks).
        score = (
            math.log2(1 + total_impact)
            + (5.0 if has_split_failed else 0.0)
            - 0.05 * blocks
        )
        fn_entries.append({
            "fn": fn,
            "cpp": cpp.name if cpp else "<missing>",
            "cpp_exists": jak3_cpp_exists,
            "blocks": blocks,
            "has_split_failed": has_split_failed,
            "caller_count": len(caller_rows),
            "callers": sorted(caller_rows, key=lambda r: -r[2])[:5],
            "total_impact": round(total_impact, 2),
            "score": round(score, 2),
        })
    fn_entries.sort(key=lambda e: (-e["score"], -e["total_impact"], e["fn"]))

    lines = [
        "# jakx mips2c porting queue",
        "",
        f"_source: scripts/jakx_watch/mips2c_candidates.py  ·  "
        f"candidates: {len(fn_entries)} functions_",
        "",
        "Per-function port targets from jak3's mips2c set that are still missing "
        "from `game/mips2c/jakx_functions/*.cpp`. Porting a function lets the "
        "jakx runtime invoke its real asm behavior instead of hitting a stub.",
        "",
        "Ranked by: `log2(1 + impact_sum) + (split_failed_caller ? 5 : 0) "
        "− 0.05·blocks` where impact_sum weights caller buckets "
        "(split-failed 1.5×, real-partial 1.0×).",
        "",
        "- **blocks** — basic-block count from the jak3 cpp (porting complexity proxy)",
        "- **SF** — at least one calling jakx file is currently split-failed",
        "- **ref** — jakx files that call this function",
        "",
    ]
    if not fn_entries:
        lines.append("_(queue empty — no porting candidates currently reference jakx files)_")
    else:
        lines.append(
            "| # | function | jak3 cpp | blocks | SF | refs | impact | score |"
        )
        lines.append(
            "|---|----------|----------|-------:|:--:|-----:|-------:|------:|"
        )
        for i, e in enumerate(fn_entries[:10], 1):
            sf = "✓" if e["has_split_failed"] else ""
            cpp_cell = f"`{e['cpp']}`" if e["cpp_exists"] else "_(missing)_"
            lines.append(
                f"| {i} | `{e['fn']}` | {cpp_cell} | {e['blocks']} | {sf} | "
                f"{e['caller_count']} | {e['total_impact']} | {e['score']} |"
            )
        lines.append("")
        lines.append("## top-3 caller detail")
        lines.append("")
        for e in fn_entries[:3]:
            lines.append(f"### `{e['fn']}` (from `{e['cpp']}`, {e['blocks']} blocks)")
            lines.append("")
            lines.append("| caller file | bucket | impact |")
            lines.append("|-------------|--------|-------:|")
            for name, cat, impact in e["callers"]:
                lines.append(f"| `{name}` | {cat} | {impact} |")
            lines.append("")
    lines.append("## How to use this queue")
    lines.append("")
    lines.append(
        "1. Pick the top row whose caller is split-failed (SF ✓) — biggest unblock."
    )
    lines.append(
        "2. Copy `game/mips2c/jak3_functions/<cpp>` as starting point; create "
        "`game/mips2c/jakx_functions/<same>.cpp` with same structure."
    )
    lines.append(
        "3. Update namespace from `Mips2C::jak3` to `Mips2C::jakx`, switch kernel "
        "header to `game/kernel/jakx/kscheme.h`."
    )
    lines.append(
        "4. Register in the mips2c install list for jakx (see existing "
        "`jakx_functions/` entries for the pattern)."
    )
    lines.append(
        "5. Re-decompile + re-measure; the caller file should drop markers or "
        "promote bucket."
    )

    QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_MD.write_text("\n".join(lines))
    print(f"\nwrote {QUEUE_MD.relative_to(ROOT)}  "
          f"(top {min(10, len(fn_entries))} of {len(fn_entries)})")

    # Persist compact copy into latest.json.
    if LATEST.exists():
        try:
            snap_json = json.loads(LATEST.read_text())
            snap_json["mips2c_queue"] = {
                "count": len(fn_entries),
                "top": [
                    {
                        "fn": e["fn"],
                        "cpp": e["cpp"],
                        "blocks": e["blocks"],
                        "has_split_failed": e["has_split_failed"],
                        "caller_count": e["caller_count"],
                        "score": e["score"],
                    }
                    for e in fn_entries[:10]
                ],
            }
            LATEST.write_text(json.dumps(snap_json, indent=2))
        except Exception as exc:
            print(f"(couldn't persist mips2c_queue into latest.json: {exc})")


if __name__ == "__main__":
    main()
