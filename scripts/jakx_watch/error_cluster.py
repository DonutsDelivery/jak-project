#!/usr/bin/env python3
"""Lane 2 — error clustering.

Walk all .jakx_watch/decomp_out/jakx/*_disasm.gc, harvest `;; ERROR:` lines,
canonicalize each (strip register names, integer literals, hex addrs, line
operands), cluster by canonical form, count instances, write
LANE2_ERROR_CLUSTERS.md.

Per-cluster output:
  - canonical pattern
  - instance count
  - distinct files affected
  - 3 example occurrences (file:fn or file:line)
  - method-vs-defun bias

Hypothesis: top-10 patterns cover 60%+ of errors. If true → recipe lane has
strong leverage; if false → errors are file-specific and recipe lane is weak.
"""
import json, re, sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DECOMP = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
OUT_MD = ROOT / ".jakx_watch" / "research" / "LANE2_ERROR_CLUSTERS.md"
OUT_JSON = ROOT / ".jakx_watch" / "research" / "LANE2_ERROR_CLUSTERS.json"

# Canonicalization patterns
RE_REG_GPR = re.compile(r"\b(?:[asvkt][0-9]|gp|sp|fp|ra|at|zero|t[89])\b")
RE_REG_FPR = re.compile(r"\bf[0-9]+(?:-\d+)?\b")
RE_REG_VEC = re.compile(r"\bv[0-9]+(?:-\d+)?\b")
RE_HEX = re.compile(r"\b0x[0-9a-fA-F]+\b")
RE_HEXADDR = re.compile(r"#x[0-9a-fA-F]+")
RE_NUM = re.compile(r"\b-?\d+\b")
RE_OP = re.compile(r"\bop\s+\d+\b")
RE_AT = re.compile(r"\bat\s+\d+\b")
RE_OP_BRACKET = re.compile(r"\[OP:\s*\d+\]")
RE_LBL = re.compile(r"\bL\d+\b")
RE_BLOCK = re.compile(r"\bB\d+\b")
RE_IN_FN = re.compile(r"\bIn\s+(?:\([^)]+\)|[^:]+):")
RE_FN_HEADER_BACK = re.compile(r"^;\s*\.function\s+(.+?)\s*$")
RE_DEFUN_LINE = re.compile(r"^\(def(?:un|method|behavior)\b.*?\b(\S+)\b")

def canonicalize(msg: str) -> str:
    s = msg.strip()
    # Strip leading ";; ERROR: " prefix
    if s.startswith(";; ERROR:"):
        s = s[len(";; ERROR:"):].strip()
    elif s.startswith("; ERROR:"):
        s = s[len("; ERROR:"):].strip()
    # Strip "In <name>:" prefix
    s = RE_IN_FN.sub("In FN:", s)
    # Strip op/at counts
    s = RE_OP_BRACKET.sub("[OP:N]", s)
    s = RE_OP.sub("op N", s)
    s = RE_AT.sub("at N", s)
    # Labels and blocks
    s = RE_LBL.sub("LBL", s)
    s = RE_BLOCK.sub("BLK", s)
    # Hex addresses
    s = RE_HEX.sub("H", s)
    s = RE_HEXADDR.sub("H", s)
    # GPR / FPR / VEC registers
    s = RE_REG_GPR.sub("REG", s)
    s = RE_REG_FPR.sub("FREG", s)
    s = RE_REG_VEC.sub("VREG", s)
    # Numeric literals (after registers, since regs contain digits)
    s = RE_NUM.sub("N", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s

def find_enclosing_fn(lines: list[str], i: int) -> str:
    """Walk backwards from line i to find the enclosing function header."""
    j = i
    while j >= 0:
        if lines[j].startswith("(") and (
            lines[j].startswith("(defun") or
            lines[j].startswith("(defmethod") or
            lines[j].startswith("(defbehavior")
        ):
            m = RE_DEFUN_LINE.match(lines[j])
            if m:
                # Try to extract method form: (defmethod NAME TYPE) or (defmethod IDX TYPE)
                if lines[j].startswith("(defmethod"):
                    # (defmethod TYPE NAME ((this TYPE) ...) ...) or (defmethod IDX TYPE ...)
                    parts = lines[j].split(None, 3)
                    if len(parts) >= 3:
                        return f"(method {parts[1]} {parts[2]})"
                return m.group(1)
        j -= 1
    return "<top-level>"

def main():
    if not DECOMP.exists():
        print(f"FATAL: {DECOMP} missing", file=sys.stderr); sys.exit(1)
    files = sorted(DECOMP.glob("*_disasm.gc"))
    print(f"scanning {len(files)} disasm.gc files...", file=sys.stderr)

    clusters: dict[str, dict] = {}
    total_errors = 0
    files_with_errors = 0

    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = text.splitlines()
        n = 0
        for i, line in enumerate(lines):
            ls = line.lstrip()
            if not (ls.startswith(";; ERROR:") or ls.startswith("; ERROR:")):
                continue
            total_errors += 1
            n += 1
            canonical = canonicalize(line)
            if canonical not in clusters:
                clusters[canonical] = {
                    "count": 0,
                    "files": Counter(),
                    "examples": [],
                }
            c = clusters[canonical]
            c["count"] += 1
            stem = f.name[:-len("_disasm.gc")]
            c["files"][stem] += 1
            if len(c["examples"]) < 5:
                fn = find_enclosing_fn(lines, i)
                c["examples"].append({
                    "file": stem, "line": i + 1, "fn": fn,
                    "raw": line.strip()[:240],
                })
        if n > 0:
            files_with_errors += 1

    # Sort clusters by count
    sorted_clusters = sorted(clusters.items(), key=lambda kv: -kv[1]["count"])
    print(f"total errors: {total_errors}, distinct clusters: {len(clusters)}, "
          f"files with errors: {files_with_errors}", file=sys.stderr)

    # Top-10 coverage
    top10_count = sum(c[1]["count"] for c in sorted_clusters[:10])
    top20_count = sum(c[1]["count"] for c in sorted_clusters[:20])
    top50_count = sum(c[1]["count"] for c in sorted_clusters[:50])
    pct10 = 100 * top10_count / max(1, total_errors)
    pct20 = 100 * top20_count / max(1, total_errors)
    pct50 = 100 * top50_count / max(1, total_errors)
    print(f"top-10 coverage: {top10_count}/{total_errors} ({pct10:.1f}%)", file=sys.stderr)
    print(f"top-20 coverage: {top20_count}/{total_errors} ({pct20:.1f}%)", file=sys.stderr)
    print(f"top-50 coverage: {top50_count}/{total_errors} ({pct50:.1f}%)", file=sys.stderr)

    # ----- JSON output (machine-readable for downstream tools)
    json_out = {
        "total_errors": total_errors,
        "distinct_clusters": len(clusters),
        "files_with_errors": files_with_errors,
        "coverage": {"top10": top10_count, "top20": top20_count, "top50": top50_count},
        "clusters": [
            {
                "rank": i + 1,
                "canonical": canonical,
                "count": c["count"],
                "n_files": len(c["files"]),
                "top_files": dict(c["files"].most_common(10)),
                "examples": c["examples"],
            }
            for i, (canonical, c) in enumerate(sorted_clusters[:200])
        ],
    }
    OUT_JSON.write_text(json.dumps(json_out, indent=1))
    print(f"wrote {OUT_JSON}", file=sys.stderr)

    # ----- Markdown report
    md = ["# Lane 2 — error clustering"]
    md.append("")
    md.append(f"_2026-04-25 cycle 0 (inventory pass)_")
    md.append("")
    md.append(f"Source: `{DECOMP}` ({len(files)} files)")
    md.append("")
    md.append("## Headline")
    md.append("")
    md.append(f"- Total errors: **{total_errors}**")
    md.append(f"- Files with errors: **{files_with_errors}** of {len(files)}")
    md.append(f"- Distinct canonical clusters: **{len(clusters)}**")
    md.append(f"- Top-10 coverage: **{top10_count}** ({pct10:.1f}%)")
    md.append(f"- Top-20 coverage: **{top20_count}** ({pct20:.1f}%)")
    md.append(f"- Top-50 coverage: **{top50_count}** ({pct50:.1f}%)")
    md.append("")
    if pct10 >= 60:
        md.append(f"**Hypothesis CONFIRMED**: top-10 covers ≥60% — recipe lane has strong leverage.")
    elif pct20 >= 60:
        md.append(f"**Hypothesis PARTIALLY CONFIRMED**: top-20 covers ≥60% (top-10 = {pct10:.1f}%).")
    else:
        md.append(f"**Hypothesis NOT CONFIRMED**: errors are spread across many patterns. "
                  f"Top-10 only covers {pct10:.1f}%. Recipe lane has WEAK leverage; consider per-file work.")
    md.append("")
    md.append("## Top 50 clusters")
    md.append("")
    md.append("| Rank | Count | Files | Pattern |")
    md.append("|---:|---:|---:|:---|")
    for i, (canonical, c) in enumerate(sorted_clusters[:50]):
        pat = canonical[:140]
        if len(canonical) > 140: pat += "…"
        # Escape pipes for markdown
        pat = pat.replace("|", "\\|")
        md.append(f"| {i+1} | {c['count']} | {len(c['files'])} | `{pat}` |")
    md.append("")
    md.append("## Top 20 clusters — detail")
    md.append("")
    for i, (canonical, c) in enumerate(sorted_clusters[:20]):
        md.append(f"### #{i+1} — count={c['count']}, n_files={len(c['files'])}")
        md.append("")
        md.append(f"Canonical: `{canonical}`")
        md.append("")
        md.append("Top files:")
        for fname, fcount in c["files"].most_common(8):
            md.append(f"- `{fname}` × {fcount}")
        md.append("")
        md.append("Examples:")
        for ex in c["examples"][:3]:
            raw = ex["raw"][:180].replace("|", "\\|")
            md.append(f"- `{ex['file']}:{ex['line']}` in `{ex['fn']}` — `{raw}`")
        md.append("")
    OUT_MD.write_text("\n".join(md))
    print(f"wrote {OUT_MD}", file=sys.stderr)

if __name__ == "__main__":
    main()
