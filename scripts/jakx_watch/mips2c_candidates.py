#!/usr/bin/env python3
"""Rank jak3 mips2c files by impact on jakx decomp.

For each jak3_functions/*.cpp, find all functions it installs, grep them in
jakx's _disasm.gc output, and score by (bucket of containing file, error
count of containing file).

Higher score = porting that .cpp could unblock more stubs.
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAK3_MIPS2C = ROOT / "game" / "mips2c" / "jak3_functions"
JAKX_MIPS2C = ROOT / "game" / "mips2c" / "jakx_functions"
JAKX_DECOMP = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"


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

    jak3_fns: dict[Path, list[str]] = {}
    all_jak3_fns: set[str] = set()
    for cpp in sorted(JAK3_MIPS2C.glob("*.cpp")):
        fns = functions_in_cpp(cpp)
        jak3_fns[cpp] = fns
        all_jak3_fns.update(fns)

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
            ["grep", "-l", "-F", "-e", fn, "-r", str(JAKX_DECOMP)],
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


if __name__ == "__main__":
    main()
