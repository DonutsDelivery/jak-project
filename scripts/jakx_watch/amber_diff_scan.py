#!/usr/bin/env python3
"""amber_diff_scan.py — classify amber-file diffs for the offline-test queue.

Amber files COMPILE but don't bytematch their `_REF.gc`. Each diff
between `decomp_out/<name>_disasm.gc` and `test/decompiler/reference/jakx/.../<name>_REF.gc`
is potentially a single-fact amber→green flip.

This tool is **scan/classify only — no apply path**. Per cycle 28 retro:
manual review of the queue before any apply.

Categories (config-fixable vs decompiler-internal):

  config-fixable:
    sig-arg-extra      : current decomp has more method args than REF
                         (sig_passthrough placeholder, likely)
    sig-arg-missing    : current decomp has fewer args than REF
    sig-ret-mismatch   : method return type differs (REF vs current)
    type-cast-diff     : `(the-as TYPE expr)` added/removed/changed
    field-access-diff  : `(-> obj field)` expression differs (likely
                         missing/wrong field on deftype)
    var-name-diff      : variable name differs (var_names.jsonc target)
    static-type-diff   : static-data type annotation differs
                         (label_types.jsonc target)

  decompiler-internal (do NOT chase via config edits):
    bytecode-only      : text identical, only compiled bytecode differs
                         (goalc / decompiler internals)
    structural-rewrite : large multi-line rewrites (decompiler IR2 logic
                         change required)
    unknown            : pattern not recognized — manual review

Usage:
  python3 scripts/jakx_watch/amber_diff_scan.py [--skip 'wcar*,v-gila*']

Outputs:
  .jakx_watch/research/amber_diff_scan_<ts>.md   (sorted queue, human-readable)
  .jakx_watch/research/amber_diff_scan_<ts>.json (machine-readable)
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / ".jakx_watch" / "research"
OFFLINE_LATEST = ROOT / ".jakx_watch" / "history" / "offline_test_latest.json"
DECOMP_OUT = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
REF_ROOT = ROOT / "test" / "decompiler" / "reference" / "jakx"


# ---------------------------------------------------------------------------
# Diff-hunk classification regexes
# ---------------------------------------------------------------------------
# Each pattern matches a diff line (with leading `-`/`+`/` `) and tags it.

# Method declaration line inside a deftype's :methods or :state-methods block.
# `    (foo-method-11 (_type_ T1 T2) ret) ;; 11`  or
# `    (initialize! (_type_) _type_)`
RE_METHOD_DECL = re.compile(
    r"^\s*\(([\w\-?!*]+)\s+\(_type_\s*([^)]*)\)\s*([\w\-?!*<>(),. \[\]]+?)\)\s*(;;.*)?$"
)
# defmethod top-level form
RE_DEFMETHOD = re.compile(r"^\(defmethod\s+([\w\-?!*]+)\s+")
# the-as cast in code
RE_THE_AS = re.compile(r"\(the-as\s+([\w\-?!*<>(),. ]+?)\s+")
# Field access (-> obj field [field2 ...])
RE_FIELD_ACCESS = re.compile(r"\(->\s+\S+\s+([\w\-?!*]+)")
# WARN/ERROR comment annotations (often paired with REF→current diffs)
RE_WARN_COMMENT = re.compile(r";;\s*(WARN|ERROR):")
# Variable name patterns: `(let ((name-N ...))`
RE_LET_VAR = re.compile(r"\(let\s+\(\(([\w\-?!*]+)\s")
# Static-data type label
RE_STATIC_LABEL = re.compile(r"\(new\s+'static\s+'(\S+)")


def classify_hunk(hunk_lines: list[str]) -> tuple[str, str]:
    """Return (category, sub-pattern) for a unified-diff hunk.

    hunk_lines includes lines starting with `-`, `+`, or ` ` (context).
    """
    minus = [l for l in hunk_lines if l.startswith("-") and not l.startswith("---")]
    plus = [l for l in hunk_lines if l.startswith("+") and not l.startswith("+++")]

    # Pure context-only hunks (shouldn't appear in unified diff but guard anyway)
    if not minus and not plus:
        return ("decompiler-internal", "context-only")

    # Try to identify shape: are these the same "kind" of line?
    # Common case: 1 line removed + 1 line added (replacement)
    if len(minus) == 1 and len(plus) == 1:
        m_line, p_line = minus[0][1:], plus[0][1:]
        return classify_replacement(m_line, p_line)

    # Multi-line additions only (REF has more) → sig-arg-missing usually
    if not minus and plus:
        # Check if all additions are inside a deftype methods block
        for p in plus:
            if RE_METHOD_DECL.match(p[1:]):
                return ("config-fixable", "method-decl-missing-in-current")
        if any("(the-as" in p for p in plus):
            return ("config-fixable", "type-cast-added-by-ref")
        return ("decompiler-internal", "addition-only")

    # Multi-line deletions only (current has more) → extra in current
    if minus and not plus:
        for m in minus:
            if RE_WARN_COMMENT.search(m[1:]):
                return ("config-fixable", "warn-removed-by-current")
        return ("decompiler-internal", "deletion-only")

    # N:M replacement — structural rewrite
    return ("decompiler-internal", "structural-rewrite")


def classify_replacement(m_line: str, p_line: str) -> tuple[str, str]:
    """Classify a single-line `-`/`+` pair."""
    m_strip = m_line.strip()
    p_strip = p_line.strip()

    # Method declaration in a deftype :methods block
    m_decl = RE_METHOD_DECL.match(m_strip)
    p_decl = RE_METHOD_DECL.match(p_strip)
    if m_decl and p_decl and m_decl.group(1) == p_decl.group(1):
        # Same method name; compare params + return
        m_args = m_decl.group(2).strip().split()
        p_args = p_decl.group(2).strip().split()
        m_ret = m_decl.group(3).strip()
        p_ret = p_decl.group(3).strip()
        if len(m_args) > len(p_args):
            return ("config-fixable", "sig-arg-missing")  # REF has more args
        if len(m_args) < len(p_args):
            return ("config-fixable", "sig-arg-extra")    # current has more args
        if m_ret != p_ret:
            return ("config-fixable", "sig-ret-mismatch")
        return ("config-fixable", "sig-other")

    # WARN comment removal
    if RE_WARN_COMMENT.search(m_strip) and not RE_WARN_COMMENT.search(p_strip):
        return ("config-fixable", "warn-comment-removed")
    if RE_WARN_COMMENT.search(p_strip) and not RE_WARN_COMMENT.search(m_strip):
        return ("config-fixable", "warn-comment-added")

    # the-as cast change
    m_cast = RE_THE_AS.search(m_strip)
    p_cast = RE_THE_AS.search(p_strip)
    if m_cast and p_cast and m_cast.group(1) != p_cast.group(1):
        return ("config-fixable", "type-cast-changed")
    if m_cast and not p_cast:
        return ("config-fixable", "type-cast-removed")
    if p_cast and not m_cast:
        return ("config-fixable", "type-cast-added")

    # Field access expression
    m_fld = RE_FIELD_ACCESS.search(m_strip)
    p_fld = RE_FIELD_ACCESS.search(p_strip)
    if m_fld and p_fld and m_fld.group(1) != p_fld.group(1):
        return ("config-fixable", "field-access-diff")

    # Static label type
    m_st = RE_STATIC_LABEL.search(m_strip)
    p_st = RE_STATIC_LABEL.search(p_strip)
    if m_st and p_st and m_st.group(1) != p_st.group(1):
        return ("config-fixable", "static-type-diff")

    # Variable name differences (let bindings)
    m_v = RE_LET_VAR.search(m_strip)
    p_v = RE_LET_VAR.search(p_strip)
    if m_v and p_v and m_v.group(1) != p_v.group(1):
        return ("config-fixable", "var-name-diff")

    return ("decompiler-internal", "line-replacement-unmatched")


# ---------------------------------------------------------------------------
# Diff extraction
# ---------------------------------------------------------------------------

def split_hunks(diff_lines: list[str]) -> list[list[str]]:
    """Split a unified-diff line list into per-hunk groups.

    Each hunk starts with `@@ -...,... +...,... @@`.
    """
    hunks: list[list[str]] = []
    cur: list[str] = []
    for line in diff_lines:
        if line.startswith("@@"):
            if cur:
                hunks.append(cur)
            cur = [line]
        elif cur:
            cur.append(line)
    if cur:
        hunks.append(cur)
    return hunks


def diff_file(name: str, ref_path: Path, dec_path: Path) -> dict:
    """Return classification for one amber file."""
    ref_text = ref_path.read_text(errors="replace")
    dec_text = dec_path.read_text(errors="replace")

    if ref_text == dec_text:
        return {
            "name": name,
            "ref_path": str(ref_path.relative_to(ROOT)),
            "dec_path": str(dec_path.relative_to(ROOT)),
            "byte_identical": True,
            "category": "decompiler-internal",
            "primary_pattern": "bytecode-only",
            "hunks": [],
            "config_fixable_count": 0,
            "decompiler_internal_count": 1,  # the file as a whole
        }

    diff = list(difflib.unified_diff(
        ref_text.splitlines(keepends=False),
        dec_text.splitlines(keepends=False),
        fromfile=f"REF/{name}",
        tofile=f"DEC/{name}",
        n=2,
    ))

    hunks = split_hunks([l for l in diff if not l.startswith("---") and not l.startswith("+++")])
    hunk_classifications = []
    cf = 0
    di = 0
    pattern_counts: dict[str, int] = {}
    for h in hunks:
        body = h[1:]  # skip the @@ line
        cat, pat = classify_hunk(body)
        hunk_classifications.append({
            "header": h[0] if h else "",
            "category": cat,
            "pattern": pat,
            "size": len(body),
            "preview": [l[:120] for l in body[:6]],
        })
        if cat == "config-fixable":
            cf += 1
        else:
            di += 1
        pattern_counts[pat] = pattern_counts.get(pat, 0) + 1

    primary = sorted(pattern_counts.items(), key=lambda kv: -kv[1])[0][0] if pattern_counts else "none"
    overall_cat = "config-fixable" if cf >= di else "decompiler-internal"

    return {
        "name": name,
        "ref_path": str(ref_path.relative_to(ROOT)),
        "dec_path": str(dec_path.relative_to(ROOT)),
        "byte_identical": False,
        "category": overall_cat,
        "primary_pattern": primary,
        "hunks": hunk_classifications,
        "config_fixable_count": cf,
        "decompiler_internal_count": di,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_decomp_path(name: str) -> Path | None:
    """Return the decomp _disasm.gc path, preferring .jakx_watch over decompiler_out."""
    primary = DECOMP_OUT / f"{name}_disasm.gc"
    if primary.exists():
        return primary
    fallback = DECOMP_OUT_FALLBACK / f"{name}_disasm.gc"
    return fallback if fallback.exists() else None


def find_ref_path(name: str) -> Path | None:
    matches = list(REF_ROOT.rglob(f"{name}_REF.gc"))
    return matches[0] if matches else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--skip", default="",
                    help="Comma-separated fnmatch patterns of names to skip "
                         "(e.g. 'wcar*,v-gila*' for Sonnet's lane)")
    ap.add_argument("--out-prefix", default=None,
                    help="Override output filename prefix (default: timestamp)")
    args = ap.parse_args()

    skip_patterns = [p.strip() for p in args.skip.split(",") if p.strip()]

    if not OFFLINE_LATEST.exists():
        print(f"ERROR: {OFFLINE_LATEST} not found. Run offline_test_pass.py first.",
              file=sys.stderr)
        return 1

    with OFFLINE_LATEST.open() as f:
        offline = json.load(f)
    amber = offline.get("offline_test", {}).get("amber", [])
    print(f"Total amber files in offline_test_latest.json: {len(amber)}")

    skipped = []
    classified = []
    missing = []
    for name in amber:
        if any(fnmatch.fnmatch(name, p) for p in skip_patterns):
            skipped.append(name)
            continue
        ref = find_ref_path(name)
        dec = find_decomp_path(name)
        if not ref or not dec:
            missing.append((name, "no-ref" if not ref else "no-decomp"))
            continue
        classified.append(diff_file(name, ref, dec))

    print(f"Skipped (matched --skip patterns): {len(skipped)}")
    print(f"Missing REF or decomp output: {len(missing)}")
    print(f"Classified: {len(classified)}")

    # Summary stats
    cf_files = sum(1 for c in classified if c["category"] == "config-fixable")
    di_files = sum(1 for c in classified if c["category"] == "decompiler-internal")
    byte_id = sum(1 for c in classified if c["byte_identical"])
    pattern_totals: dict[str, int] = {}
    for c in classified:
        for h in c["hunks"]:
            pattern_totals[h["pattern"]] = pattern_totals.get(h["pattern"], 0) + 1

    # Sort: config-fixable first, then by hunk count ascending (easier wins first)
    classified.sort(key=lambda c: (
        0 if c["category"] == "config-fixable" else 1,
        c["config_fixable_count"] + c["decompiler_internal_count"],
    ))

    # Write outputs
    RESEARCH.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    prefix = args.out_prefix or f"amber_diff_scan_{ts}"
    md_path = RESEARCH / f"{prefix}.md"
    json_path = RESEARCH / f"{prefix}.json"

    # Markdown report
    with md_path.open("w") as f:
        f.write(f"# Amber-file diff classification — {ts}\n\n")
        f.write(f"Source: `.jakx_watch/history/offline_test_latest.json` "
                f"@ git `{offline.get('git_sha','?')[:12]}`\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Total amber: {len(amber)}\n")
        f.write(f"- Skipped (--skip): {len(skipped)} ({', '.join(skipped) if skipped else 'none'})\n")
        f.write(f"- Missing REF/decomp: {len(missing)}\n")
        f.write(f"- Classified: {len(classified)}\n")
        f.write(f"- Byte-identical (bytecode-only diff, decompiler-internal): {byte_id}\n")
        f.write(f"- Config-fixable (overall): {cf_files}\n")
        f.write(f"- Decompiler-internal (overall): {di_files}\n\n")

        f.write(f"## Pattern frequency across all hunks\n\n")
        for p, c in sorted(pattern_totals.items(), key=lambda kv: -kv[1]):
            f.write(f"- `{p}`: {c}\n")
        f.write("\n")

        f.write(f"## Per-file queue (config-fixable first, smallest diffs first)\n\n")
        for c in classified:
            cat = c["category"]
            f.write(f"### `{c['name']}` — **{cat}** "
                    f"(primary: `{c['primary_pattern']}`)\n\n")
            f.write(f"- ref: `{c['ref_path']}`\n")
            f.write(f"- dec: `{c['dec_path']}`\n")
            if c["byte_identical"]:
                f.write(f"- BYTE-IDENTICAL — bytecode-only difference. "
                        f"Not config-fixable; goalc/decompiler-internal.\n\n")
                continue
            f.write(f"- hunks: {c['config_fixable_count']} config-fixable + "
                    f"{c['decompiler_internal_count']} decompiler-internal\n\n")
            for h in c["hunks"]:
                f.write(f"  - `{h['pattern']}` ({h['category']}) {h['header']}\n")
                for pl in h["preview"][:3]:
                    f.write(f"    {pl}\n")
            f.write("\n")

    # JSON report
    with json_path.open("w") as f:
        json.dump({
            "ts": ts,
            "git_sha": offline.get("git_sha"),
            "total_amber": len(amber),
            "skipped": skipped,
            "missing": missing,
            "byte_identical_count": byte_id,
            "config_fixable_files": cf_files,
            "decompiler_internal_files": di_files,
            "pattern_totals": pattern_totals,
            "files": classified,
        }, f, indent=2)

    print(f"\nWrote: {md_path.relative_to(ROOT)}")
    print(f"Wrote: {json_path.relative_to(ROOT)}")
    print(f"\nTop patterns:")
    for p, c in sorted(pattern_totals.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {c:3d}  {p}")

    print(f"\nBytecode-only (decompiler-internal): {byte_id}/{len(classified)} "
          f"({100*byte_id/max(1,len(classified)):.0f}%)")
    print(f"Overall config-fixable: {cf_files}/{len(classified)} "
          f"({100*cf_files/max(1,len(classified)):.0f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
