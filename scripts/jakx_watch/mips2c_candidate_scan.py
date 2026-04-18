#!/usr/bin/env python3
"""Surface mips2c port candidates for jakx from two signal sources.

Signal A — jak3-has-it:
  Scan jak3_functions/*.cpp for registered functions that jakx's disasm
  files reference but jakx_functions/*.cpp does not yet provide.
  Weight by how many split-failed files reference each function.

Signal B — asm-error markers:
  Parse the most recent decompiler log for functions that the decompiler
  flagged as asm-heavy or failed to decompile:
    • "flagging as asm" / "flagged as asm" (strange stack usage)
    • "failed to build control flow graph" (CFG build impossible)
    • "failed type prop" (type propagation blocked)
    • "Unsupported inline assembly instruction kind"
  Group by source file, cross-reference with jak3 mips2c.

Output:
  .jakx_watch/mips2c_candidates.md   — ranked queue for A1/A2
  stdout                             — summary counts
"""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAK3_MIPS2C = ROOT / "game" / "mips2c" / "jak3_functions"
JAKX_MIPS2C = ROOT / "game" / "mips2c" / "jakx_functions"
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
LOG_DIR = ROOT / "log"
OUTPUT_MD = ROOT / ".jakx_watch" / "mips2c_candidates.md"

RE_REG = re.compile(r'gLinkedFunctionTable\.reg\("([^"]+)"')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pick_decomp_dir() -> Path:
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists() and any(p.glob("*_disasm.gc")):
            return p
    return DECOMP_PRIMARY


def latest_decompiler_log() -> Path | None:
    logs = sorted(LOG_DIR.glob("decompiler.*.log"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


def functions_in_cpp(cpp: Path) -> list[str]:
    text = cpp.read_text(errors="replace")
    out = []
    for m in RE_REG.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if text[line_start:m.start()].lstrip().startswith("//"):
            continue
        out.append(m.group(1))
    return out


def count_blocks(cpp: Path, fn_name: str) -> int:
    """Count basic-blocks in jak3 mips2c cpp for this function (complexity proxy)."""
    text = cpp.read_text(errors="replace")
    clean = re.sub(r"[!?<>*=/+]", "_", fn_name.replace("-", "_"))
    clean2 = re.sub(r"[!?<>*=/+]", "", fn_name.replace("-", "_"))
    idx = -1
    for ns in (clean2, clean, fn_name):
        needle = f"namespace {ns} {{"
        idx = text.find(needle)
        if idx >= 0:
            break
    if idx < 0:
        m = re.search(rf"^namespace\s+\w*{re.escape(clean2[:20])}\w*\s*\{{", text, re.MULTILINE)
        if m:
            idx = m.start()
    if idx < 0:
        return 0
    depth = 0
    i = idx
    started = False
    end = idx
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
            started = True
        elif c == "}":
            depth -= 1
            if started and depth == 0:
                end = i
                break
        i += 1
    body = text[idx:end]
    return sum(1 for line in body.splitlines() if re.match(r"^\s+block_\d+:", line))


# ---------------------------------------------------------------------------
# Signal B: parse decompiler log for asm/decompile failures
# ---------------------------------------------------------------------------

# Patterns that indicate a function is asm-heavy
_ASM_PATTERNS = [
    re.compile(r"Function (.+?) (?:stores on the stack in a strange way|flagging as asm|was flagged as asm)"),
    re.compile(r"Function (.+?) failed to build control flow graph"),
    re.compile(r"Function (.+?) has a double return and is being flagged as asm"),
]
_TYPE_FAIL_PAT = re.compile(r"Function (.+?) failed type prop at \d+: (.+)")
_UNSUPPORTED_ASM_PAT = re.compile(r"Unsupported inline assembly instruction kind.*?in (.+)")
_FILE_SECTION_PAT = re.compile(r"\[info\]\s+\[\d+/\d+\]---+\s+(\S+)")
# Extract function name from "strange way (NAME), flagging"
_STRANGE_WAY_PAT = re.compile(r"strange way \((.+?)\)")


def parse_decompiler_log(
    log_path: Path,
) -> tuple[
    dict[str, list[tuple[str, str]]],   # file → [(fn_name, reason)]  (asm-flagged)
    dict[str, list[tuple[str, str]]],   # file → [(fn_name, reason)]  (type-prop failed)
    dict[str, list[str]],               # file → [instruction kind]   (unsupported asm instr)
]:
    """Parse a decompiler log and return asm failures grouped by source file."""
    asm_per_file: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    type_fail_per_file: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    unsupported_per_file: dict[str, list[str]] = collections.defaultdict(list)

    current_file = None
    try:
        lines = log_path.read_text(errors="replace").splitlines()
    except OSError:
        return asm_per_file, type_fail_per_file, unsupported_per_file

    for line in lines:
        m_sec = _FILE_SECTION_PAT.search(line)
        if m_sec:
            current_file = m_sec.group(1)
            continue

        if not current_file:
            continue

        # Check asm patterns
        matched_asm = False
        for pat in _ASM_PATTERNS:
            m = pat.search(line)
            if m:
                fn_raw = m.group(1).strip()
                # "strange way (NAME)" extracts the actual fn name
                sw = _STRANGE_WAY_PAT.search(line)
                fn = sw.group(1) if sw else fn_raw
                reason = "asm-flagged (strange stack usage)" if "strange" in line else \
                         "no CFG (control flow graph build failed)" if "control flow" in line else \
                         "double-return flagged as asm"
                asm_per_file[current_file].append((fn, reason))
                matched_asm = True
                break

        if matched_asm:
            continue

        # Type-prop failures
        m = _TYPE_FAIL_PAT.search(line)
        if m:
            fn, reason = m.group(1).strip(), m.group(2).strip()[:80]
            type_fail_per_file[current_file].append((fn, reason))
            continue

        # Unsupported inline asm instruction
        if "Unsupported inline assembly instruction kind" in line:
            instr = line.split("kind")[-1].strip(" -[]").strip()[:60]
            unsupported_per_file[current_file].append(instr)

    return asm_per_file, type_fail_per_file, unsupported_per_file


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    if not LATEST.exists():
        print("ERROR: no latest.json — run measure.py first", file=sys.stderr)
        return 1

    snap = json.loads(LATEST.read_text())
    per_file = snap["per_file"]

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()

    # -----------------------------------------------------------------------
    # Load jak3 and jakx mips2c registries
    # -----------------------------------------------------------------------
    jak3_fns: dict[str, Path] = {}   # fn_name → cpp path
    for cpp in sorted(JAK3_MIPS2C.glob("*.cpp")):
        for fn in functions_in_cpp(cpp):
            jak3_fns[fn] = cpp

    jakx_fns: set[str] = set()
    for cpp in sorted(JAKX_MIPS2C.glob("*.cpp")):
        jakx_fns.update(functions_in_cpp(cpp))

    gap = sorted(jak3_fns.keys() - jakx_fns)
    print(f"jak3 mips2c: {len(jak3_fns)} fns across {len(list(JAK3_MIPS2C.glob('*.cpp')))} .cpp files")
    print(f"jakx mips2c: {len(jakx_fns)} fns across {len(list(JAKX_MIPS2C.glob('*.cpp')))} .cpp files")
    print(f"gap (jak3 not in jakx): {len(gap)} fns")

    # -----------------------------------------------------------------------
    # Signal B: asm/type failures from decompiler log
    # -----------------------------------------------------------------------
    log_path = latest_decompiler_log()
    if log_path:
        print(f"\nparsing log: {log_path.name} ({log_path.stat().st_size // 1024} KB)...")
        asm_per_file, type_fail_per_file, unsupported_per_file = parse_decompiler_log(log_path)
        print(f"  files with asm-flagged functions: {len(asm_per_file)}")
        print(f"  files with type-prop failures:    {len(type_fail_per_file)}")
        print(f"  files with unsupported asm instr: {len(unsupported_per_file)}")
    else:
        print("\nno decompiler log found")
        asm_per_file, type_fail_per_file, unsupported_per_file = {}, {}, {}

    # Build per-jakx-file asm error counts (for ranking context)
    asm_fn_to_files: dict[str, set[str]] = collections.defaultdict(set)
    for fname, items in asm_per_file.items():
        for fn, _ in items:
            asm_fn_to_files[fn].add(fname)

    # -----------------------------------------------------------------------
    # Signal A: jak3 fns referenced in jakx disasm files, weighted by bucket
    # -----------------------------------------------------------------------
    W = {"split-failed": 1.5, "real-partial": 1.0, "real-clean": 0.3, "static-only": 0.0}

    print(f"\nscanning {decomp_dir.relative_to(ROOT)} for jak3 fn references...")

    # Batch grep all gap functions against disasm files
    fn_refs: dict[str, set[str]] = collections.defaultdict(set)
    for fn in gap:
        r = subprocess.run(
            ["grep", "-l", "-F", "-e", fn, "-r", str(decomp_dir), "--include=*_disasm.gc"],
            capture_output=True, text=True, check=False,
        )
        for line in r.stdout.strip().splitlines():
            stem = Path(line).stem.replace("_disasm", "")
            fn_refs[fn].add(stem)

    # -----------------------------------------------------------------------
    # Score each gap function
    # -----------------------------------------------------------------------
    entries = []
    for fn in gap:
        refs = sorted(fn_refs.get(fn, set()))
        jak3_cpp = jak3_fns[fn]

        # Compute weighted impact
        split_failed_refs: list[str] = []
        total_impact = 0.0
        for ref in refs:
            pf = per_file.get(ref)
            if not pf:
                continue
            cat = pf.get("category", "unknown")
            stubs = int(pf.get("failed", 0)) + int(pf.get("error", 0))
            contrib = W.get(cat, 0.0) * stubs
            total_impact += contrib
            if cat == "split-failed":
                split_failed_refs.append(ref)

        # Signal B bonus: is this function in jak3 AND also asm-flagged in jakx?
        asm_flagged_in_jakx = fn in asm_fn_to_files
        # Signal B bonus: does this function appear in a file with asm issues?
        fn_in_asm_file = any(
            fn in {f for f, _ in items}
            for items in asm_per_file.values()
        )

        if total_impact == 0 and not asm_flagged_in_jakx:
            continue

        blocks = count_blocks(jak3_cpp, fn)
        score = (
            total_impact * 1.0
            + (20.0 if split_failed_refs else 0.0)
            + (10.0 if asm_flagged_in_jakx else 0.0)
            - 0.1 * blocks
        )

        entries.append({
            "fn": fn,
            "jak3_cpp": jak3_cpp,
            "blocks": blocks,
            "refs": refs,
            "split_failed_refs": split_failed_refs,
            "total_impact": round(total_impact, 1),
            "asm_flagged": asm_flagged_in_jakx,
            "score": round(score, 1),
        })

    entries.sort(key=lambda e: (-e["score"], -e["total_impact"], e["fn"]))

    # -----------------------------------------------------------------------
    # Console output
    # -----------------------------------------------------------------------
    print(f"\n== mips2c candidates by score (top {args.top}) ==")
    print(f"  {'fn':<40} {'jak3 cpp':<26} {'blk':>4} {'SF':>3} {'ASM':>4} {'impact':>7} {'score':>7}")
    print("  " + "-" * 95)
    for e in entries[:args.top]:
        sf = "✓" if e["split_failed_refs"] else ""
        asm = "✓" if e["asm_flagged"] else ""
        print(
            f"  {e['fn'][:40]:<40} {e['jak3_cpp'].name:<26} {e['blocks']:>4} "
            f"{sf:>3} {asm:>4} {e['total_impact']:>7.1f} {e['score']:>7.1f}"
        )

    # -----------------------------------------------------------------------
    # Per-file asm issues (Signal B only — files with asm issues in jakx)
    # -----------------------------------------------------------------------
    print(f"\n== files with asm-flagged functions (need mips2c port or :asm-func hint) ==")
    asm_file_summary = []
    for fname, items in sorted(asm_per_file.items()):
        pf = per_file.get(fname, {})
        cat = pf.get("category", "?")
        fn_names = [fn for fn, _ in items]
        in_jak3 = [fn for fn in fn_names if fn in jak3_fns and fn not in jakx_fns]
        asm_file_summary.append((fname, cat, fn_names, in_jak3))
    for fname, cat, fn_names, in_jak3 in sorted(asm_file_summary, key=lambda x: x[1]):
        jak3_note = f"  ← jak3 has: {in_jak3}" if in_jak3 else ""
        print(f"  [{cat:12s}] {fname:<30} asm-fns: {', '.join(fn_names[:4])}{jak3_note}")

    if args.no_write:
        return 0

    # -----------------------------------------------------------------------
    # Markdown output
    # -----------------------------------------------------------------------
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# jakx mips2c port candidates",
        "",
        f"_source: `scripts/jakx_watch/mips2c_candidate_scan.py`  ·  "
        f"decompiler log: `{log_path.name if log_path else 'none'}`_",
        "",
        "Two signals combined:",
        "- **Signal A** (jak3-has-it): jak3 mips2c functions referenced in jakx disasm, "
        "not yet ported to jakx. Weighted by caller bucket (split-failed 1.5×, real-partial 1.0×).",
        "- **Signal B** (asm-error): functions the decompiler flagged as asm-heavy or "
        "failed to decompile (from the most recent `log/decompiler.*.log`).",
        "",
        "Score = `impact + (20 if split-failed caller) + (10 if asm-flagged) − 0.1·blocks`",
        "",
        f"jak3 mips2c: **{len(jak3_fns)} fns** · jakx mips2c: **{len(jakx_fns)} fns** · "
        f"gap: **{len(gap)} fns**",
        "",
        "---",
        "",
        "## Ranked candidates",
        "",
        "- **SF** — at least one calling jakx file is currently `split-failed`",
        "- **ASM** — decompiler flagged this function as asm-heavy (Signal B)",
        "- **blocks** — basic-block count in jak3 cpp (porting complexity proxy)",
        "",
        f"| # | function | jak3 .cpp | blocks | SF | ASM | refs | impact | score |",
        f"|---|----------|-----------|-------:|:--:|:---:|-----:|-------:|------:|",
    ]
    for i, e in enumerate(entries[:args.top], 1):
        sf = "✓" if e["split_failed_refs"] else ""
        asm = "✓" if e["asm_flagged"] else ""
        lines.append(
            f"| {i} | `{e['fn']}` | `{e['jak3_cpp'].name}` | {e['blocks']} | {sf} | {asm} | "
            f"{len(e['refs'])} | {e['total_impact']} | {e['score']} |"
        )

    lines += [
        "",
        "## Top-5 caller detail",
        "",
    ]
    for e in entries[:5]:
        lines.append(f"### `{e['fn']}` — jak3 source: `{e['jak3_cpp'].name}`")
        lines.append("")
        lines.append("| caller file | bucket | failed | error | category |")
        lines.append("|-------------|--------|-------:|------:|----------|")
        for ref in sorted(e["refs"])[:8]:
            pf = per_file.get(ref, {})
            cat = pf.get("category", "?")
            failed = pf.get("failed", 0)
            err = pf.get("error", 0)
            lines.append(f"| `{ref}` | {cat} | {failed} | {err} | {'**SF**' if cat=='split-failed' else ''} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Files with asm-flagged functions (Signal B)",
        "",
        "Files where the decompiler detected asm-heavy functions. "
        "These files need either mips2c ports or `:asm-func` declarations in all-types.gc.",
        "",
        f"| file | bucket | asm functions | jak3 mips2c available |",
        f"|------|--------|---------------|----------------------|",
    ]
    for fname, cat, fn_names, in_jak3 in sorted(asm_file_summary, key=lambda x: (x[1], x[0])):
        fn_str = ", ".join(f"`{f}`" for f in fn_names[:5])
        if len(fn_names) > 5:
            fn_str += f" +{len(fn_names)-5}"
        jak3_str = ", ".join(f"`{f}`" for f in in_jak3) if in_jak3 else "—"
        lines.append(f"| `{fname}` | {cat} | {fn_str} | {jak3_str} |")

    lines += [
        "",
        "---",
        "",
        "## How to port",
        "",
        "1. Pick top candidate with **SF=✓** (split-failed caller = biggest unblock).",
        "2. Copy `game/mips2c/jak3_functions/<cpp>` → `game/mips2c/jakx_functions/<same>.cpp`.",
        "3. Change `namespace Mips2C::jak3` → `namespace Mips2C::jakx`.",
        "4. Switch kernel include: `game/kernel/jak3/kscheme.h` → `game/kernel/jakx/kscheme.h`.",
        "5. Add the new .cpp to `game/mips2c/jak3_to_jakx.cpp` (or jakx equivalent) "
        "and register with `gLinkedFunctionTable.reg`.",
        "6. Run `cmake --build build/Release --target offline-test` + "
        "`python3 scripts/jakx_watch/offline_test_pass.py` to verify unblock.",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
