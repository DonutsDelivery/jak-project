#!/usr/bin/env python3
"""Detect drift between existing _REF.gc files and current decompiler output.

Compares each file in test/decompiler/reference/jakx/**/*_REF.gc against the
corresponding *_disasm.gc in .jakx_watch/decomp_out/jakx/ (or decompiler_out/jakx/).

Categories:
  green      — REF matches current disasm exactly
  regression — disasm is WORSE than REF (type went from defined → unknown, or
               content shrunk). REF still holds what we want; decomp regressed.
  stale_ref  — disasm is BETTER than REF (type went from unknown → defined, or
               content grew). REF needs to be updated via seed_refs.py --force.
  changed    — both have content but differ in a way that's neither clearly
               better nor worse (e.g., different field names, reordering).
  missing    — REF exists but no disasm found (file may have been merged or removed).
  unseeded   — disasm exists and file is real-clean but no REF yet.

Output:
  .jakx_watch/ref_drift_queue.md  — per-file classification with diff preview
  stdout                          — summary counts + action items

This scanner is read-only — it does NOT modify any REF files.
To update stale REFs: python3 scripts/jakx_watch/seed_refs.py --force
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF_DIR = ROOT / "test" / "decompiler" / "reference" / "jakx"
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST_JSON = ROOT / ".jakx_watch" / "history" / "latest.json"
OUTPUT_MD = ROOT / ".jakx_watch" / "ref_drift_queue.md"

# Patterns that indicate a type is unknown/undecompiled in a disasm file
RE_UNKNOWN_TYPE = re.compile(
    r"^\s*;;\s+type \S+ is defined here, but it is unknown to the decompiler",
    re.MULTILINE,
)
RE_FUNCTION_NO_TYPE = re.compile(
    r"^\s*;;\s+(?:ERROR|WARN).*(?:no type analysis|Cannot decompile|not converted)",
    re.MULTILINE,
)


def score_quality(text: str) -> int:
    """Rough quality score for a disasm file.

    Higher = more decompiled content.
    Counts non-stub definition lines vs error/stub markers.
    """
    lines = text.splitlines()
    score = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("(deftype ") or stripped.startswith("(defun "):
            score += 5
        elif stripped.startswith("(define ") or stripped.startswith("(defmethod "):
            score += 3
        elif stripped.startswith(";; type") and "unknown to the decompiler" in stripped:
            score -= 3
        elif ";; ERROR:" in stripped or ";; stub" in stripped.lower():
            score -= 1
    return score


def classify_drift(ref_text: str, dis_text: str) -> tuple[str, str]:
    """Classify the relationship between REF and disasm.

    Returns (category, reason_string).
    """
    if ref_text == dis_text:
        return "green", ""

    ref_score = score_quality(ref_text)
    dis_score = score_quality(dis_text)

    ref_unknowns = len(RE_UNKNOWN_TYPE.findall(ref_text))
    dis_unknowns = len(RE_UNKNOWN_TYPE.findall(dis_text))

    ref_errors = len(RE_FUNCTION_NO_TYPE.findall(ref_text))
    dis_errors = len(RE_FUNCTION_NO_TYPE.findall(dis_text))

    # Clear regression: disasm has more unknowns/errors than REF
    if dis_unknowns > ref_unknowns or dis_errors > ref_errors:
        reason = (
            f"disasm has more unknowns ({dis_unknowns} vs {ref_unknowns}) "
            f"or errors ({dis_errors} vs {ref_errors})"
        )
        return "regression", reason

    # Clear improvement: disasm has fewer unknowns/errors → stale REF
    if dis_unknowns < ref_unknowns or dis_errors < ref_errors:
        reason = (
            f"disasm has fewer unknowns ({dis_unknowns} vs {ref_unknowns}) "
            f"or errors ({dis_errors} vs {ref_errors}) — REF needs update"
        )
        return "stale_ref", reason

    # Score-based classification
    if dis_score < ref_score - 5:
        return "regression", f"quality score dropped {ref_score} → {dis_score}"
    if dis_score > ref_score + 5:
        return "stale_ref", f"quality score improved {ref_score} → {dis_score} — REF needs update"

    # Fallback: different but unclear direction
    ref_lines = len(ref_text.splitlines())
    dis_lines = len(dis_text.splitlines())
    reason = f"content differs ({ref_lines} REF lines vs {dis_lines} disasm lines)"
    return "changed", reason


def short_diff(ref_text: str, dis_text: str, max_lines: int = 12) -> list[str]:
    """Return a compact unified diff excerpt."""
    diff = list(difflib.unified_diff(
        ref_text.splitlines(keepends=True),
        dis_text.splitlines(keepends=True),
        fromfile="REF",
        tofile="disasm",
        n=2,
    ))
    if not diff:
        return []
    out = []
    for line in diff[2:]:  # skip the --- +++ header lines
        if line.startswith("@@") or line.startswith("-") or line.startswith("+"):
            out.append(line.rstrip("\n"))
        if len(out) >= max_lines:
            out.append("... (truncated)")
            break
    return out


def load_real_clean_set(decomp_dir: Path) -> set[str]:
    """Return the set of file stems classified as real-clean.

    1. Try latest.json per_file data (authoritative, only present after a full decomp run).
    2. Fall back to heuristic scan: files in decomp_dir with quality score > 0
       and no stub/error markers (approximates the decompiler's real-clean bucket).
    """
    # Primary: read from latest.json per_file categories
    try:
        import json
        data = json.loads(LATEST_JSON.read_text())
        per_file = data.get("per_file", {})
        if per_file:
            result = {stem for stem, info in per_file.items()
                      if info.get("category") == "real-clean"}
            if result:
                return result
    except Exception:
        pass

    # Fallback: heuristic scan of decomp_dir
    result = set()
    if not decomp_dir or not decomp_dir.exists():
        return result
    stub_pat = re.compile(
        r";; stub\b|Cannot decompile|function was not converted"
        r"|UNRESOLVED-REF|function has no type analysis"
        r"|Failed store:|failed type prop"
    )
    for disasm in decomp_dir.glob("*_disasm.gc"):
        stem = disasm.name[: -len("_disasm.gc")]
        try:
            text = disasm.read_text(errors="replace")
        except OSError:
            continue
        if stub_pat.search(text):
            continue
        if score_quality(text) > 0:
            result.add(stem)
    return result


def pick_decomp_dir() -> Path | None:
    # Prefer the dir with more _disasm.gc files (partial runs in primary can mislead)
    candidates = []
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists():
            count = sum(1 for _ in p.glob("*_disasm.gc"))
            if count > 0:
                candidates.append((count, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--show-green", action="store_true",
                    help="Include green (identical) files in report")
    args = ap.parse_args()

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if decomp_dir is None:
        print("ERROR: no decomp output dir with _disasm.gc files found", file=sys.stderr)
        return 1
    print(f"decomp dir: {decomp_dir.relative_to(ROOT)}")

    all_refs = sorted(REF_DIR.rglob("*_REF.gc"))
    real_clean = load_real_clean_set(decomp_dir)
    print(f"REF files: {len(all_refs)}  real-clean (from disasm scan): {len(real_clean)}")

    # Collect results per category
    results: dict[str, list[dict]] = {
        "regression": [],
        "stale_ref": [],
        "changed": [],
        "missing": [],
        "green": [],
    }

    for ref_path in all_refs:
        stem = ref_path.stem[: -len("_REF")]
        disasm_path = decomp_dir / f"{stem}_disasm.gc"

        if not disasm_path.exists():
            results["missing"].append({"stem": stem, "ref_path": ref_path})
            continue

        ref_text = ref_path.read_text(errors="replace")
        dis_text = disasm_path.read_text(errors="replace")
        cat, reason = classify_drift(ref_text, dis_text)
        diff_lines = short_diff(ref_text, dis_text) if cat != "green" else []

        results[cat].append({
            "stem": stem,
            "ref_path": ref_path,
            "reason": reason,
            "diff": diff_lines,
        })

    # Unseeded: real-clean in latest.json but no REF exists
    existing_stems = {r.stem[: -len("_REF")] for r in all_refs}
    unseeded = sorted(real_clean - existing_stems)

    total = len(all_refs)
    print(f"\nRef drift summary ({total} total REFs):")
    print(f"  green      : {len(results['green'])}")
    print(f"  regression : {len(results['regression'])}  ← disasm regressed vs REF")
    print(f"  stale_ref  : {len(results['stale_ref'])}  ← disasm improved; run seed_refs.py --force")
    print(f"  changed    : {len(results['changed'])}  ← content differs, direction unclear")
    print(f"  missing    : {len(results['missing'])}  ← REF exists but no current disasm")
    print(f"  unseeded   : {len(unseeded)}  ← real-clean but no REF yet")

    if results["regression"]:
        print("\nREGRESSIONS (disasm worse than REF):")
        for r in results["regression"]:
            print(f"  {r['stem']}: {r['reason']}")

    if results["stale_ref"]:
        print("\nSTALE REFs (disasm improved; update REF):")
        for r in results["stale_ref"][:10]:
            print(f"  {r['stem']}: {r['reason']}")

    if results["missing"]:
        print("\nMISSING disasm (REF has no current counterpart):")
        for r in results["missing"][:5]:
            print(f"  {r['stem']}")

    if unseeded[:5]:
        print(f"\nUNSEEDED real-clean (first 5 of {len(unseeded)}):")
        for s in unseeded[:5]:
            print(f"  {s}")

    if args.no_write:
        return 0

    # Write markdown
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# jakx REF drift scan",
        "",
        f"_source: `scripts/jakx_watch/ref_drift_scan.py`_",
        "",
        "Compares each `_REF.gc` in `test/decompiler/reference/jakx/` against the "
        "current `_disasm.gc` output. Identifies regressions (decomp got worse) and "
        "stale REFs (decomp improved but REF not updated).",
        "",
        f"| category | count | action |",
        f"|----------|------:|--------|",
        f"| green | {len(results['green'])} | no action needed |",
        f"| regression | {len(results['regression'])} | **investigate** — disasm regressed vs REF |",
        f"| stale_ref | {len(results['stale_ref'])} | run `seed_refs.py --force` to update |",
        f"| changed | {len(results['changed'])} | review manually |",
        f"| missing | {len(results['missing'])} | REF exists but no current disasm |",
        f"| unseeded | {len(unseeded)} | real-clean with no REF — run `seed_refs.py` |",
        "",
    ]

    def section(title: str, entries: list[dict], show: bool = True) -> list[str]:
        out = [f"## {title}", ""]
        if not entries:
            out += [f"_None._", ""]
            return out
        if not show:
            out += [f"_{len(entries)} files (use --show-green to list)_", ""]
            return out
        for e in entries:
            out.append(f"### `{e['stem']}`")
            out.append("")
            if e.get("reason"):
                out.append(f"**Reason:** {e['reason']}")
                out.append("")
            if e.get("diff"):
                out.append("```diff")
                out.extend(e["diff"])
                out.append("```")
                out.append("")
        return out

    lines += section(
        f"Regressions ({len(results['regression'])}) — disasm worse than REF",
        results["regression"],
    )
    lines += section(
        f"Stale REFs ({len(results['stale_ref'])}) — disasm improved, REF needs update",
        results["stale_ref"],
    )
    lines += section(
        f"Changed ({len(results['changed'])}) — content differs, direction unclear",
        results["changed"],
    )
    lines += section(
        f"Missing ({len(results['missing'])}) — REF exists but no current disasm",
        results["missing"],
    )
    if args.show_green:
        lines += section(
            f"Green ({len(results['green'])}) — identical",
            results["green"],
        )
    else:
        lines += [
            f"## Green ({len(results['green'])}) — identical",
            "",
            f"_{len(results['green'])} files match exactly (use --show-green to list)._",
            "",
        ]

    if unseeded:
        lines += [
            f"## Unseeded ({len(unseeded)}) — real-clean with no REF",
            "",
            "Run `python3 scripts/jakx_watch/seed_refs.py` to create REF files for these:",
            "",
        ]
        for s in unseeded:
            lines.append(f"- `{s}`")
        lines.append("")

    lines += [
        "---",
        "",
        "## How to use",
        "",
        "**Fix regressions**: identify what changed in `all-types.gc` or the decompiler "
        "that caused the type to go unknown. Use `clobber_scan.py` output to check for "
        "new clobbers. File a note in the decomp issue tracker.",
        "",
        "**Fix stale REFs**: run `python3 scripts/jakx_watch/seed_refs.py --force` to "
        "overwrite REF files with the improved disasm output. Only do this after confirming "
        "the new output is actually better (not a different kind of wrong).",
        "",
        "**Fix unseeded**: run `python3 scripts/jakx_watch/seed_refs.py` (no --force) to "
        "seed REF files for any real-clean file that doesn't have one yet.",
        "",
        "Re-run this scan after any `all-types.gc` change or decompiler C++ patch.",
    ]

    OUTPUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUTPUT_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
