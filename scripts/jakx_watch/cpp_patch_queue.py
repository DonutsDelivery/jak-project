#!/usr/bin/env python3
"""C++ patch candidate scanner — cluster recurring malformed emissions.

Complements the type-level queues (`activation_queue.md`, `discovery_queue.md`,
`mips2c_queue.md`) with a PATCH-level queue that identifies patterns the
decompiler is emitting which goalc/downstream rejects. Fixing the C++ emitter
for one of these patterns clears ALL occurrences at once.

Patterns scanned (each classified by GOALC-REJECTION severity):
  * `<static-data LN>` embedded as a value form — 3-arg (define ...) /
    (set! ...) / let-binding etc. Goalc's reader rejects the 3-token
    `<static-data LN>` sequence. Canonical pattern already committed as
    static_data_scan.py; this scanner aggregates all value-positions.
  * `<link-unknown name>` — unresolved label reference.
  * `<pp>` / `<uninitialized>` / `<invalid>` — placeholder tokens that
    escape into output.
  * `.set!` / bare `.mov64` — raw asm instructions that leaked through
    conversion. These come from the ASM-func code path and shouldn't appear
    in a `(defun ...)` body.
  * `(the-as <uninitialized> ...)` — the-as applied to an untyped register.
  * `(defmethod NAME () ...)` with empty arg list — decomp couldn't infer
    args. Not strictly goalc-rejected but high-frequency noise.

Rank by: (occurrences × severity) − 0.01 × files. Higher = bigger
single-patch unblock.

Output:
  * `.jakx_watch/cpp_patch_queue.md`   — human-readable top-N
  * latest.json[cpp_patch_queue]         — compact for measure.py
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
QUEUE_MD = ROOT / ".jakx_watch" / "cpp_patch_queue.md"


# (id, severity, description, regex)
# Severity scale:
#   4 — goalc hard-reject (decomp emits unparseable source)
#   3 — goalc compile error (parseable but type-reject)
#   2 — runtime undefined
#   1 — warning / noise (compiles but degrades downstream tooling)
PATTERNS: list[tuple[str, int, str, re.Pattern]] = [
    ("static-data-define", 4,
     "(define *X* <static-data LN>) — goalc reader sees 3 tokens, expects 2",
     re.compile(r"^\(define\s+\*[^*\s]+\*\s+<static-data\s+L\d+>\)", re.M)),
    ("static-data-set", 4,
     "(set! X <static-data LN>) — same 3-token bug outside (define)",
     re.compile(r"\(set!\s+\S+\s+<static-data\s+L\d+>\)")),
    ("static-data-let", 4,
     "let-binding (X <static-data LN>) — same root bug in a different context",
     re.compile(r"\(let\s+\(\(\S+\s+<static-data\s+L\d+>\)")),
    ("link-unknown", 3,
     "<link-unknown NAME> — decomp couldn't resolve a global label",
     re.compile(r"<link-unknown\s+\S+?>")),
    ("link-label", 3,
     "<link-label LN> — label address emitted as a pseudo-token",
     re.compile(r"<link-label\s+L\d+>")),
    ("uninitialized-value", 3,
     "<uninitialized> leaked into expression position",
     re.compile(r"<uninitialized>")),
    ("invalid-value", 3,
     "<invalid> leaked into expression position",
     re.compile(r"<invalid\S*>")),
    ("the-as-uninit", 3,
     "(the-as TYPE <uninitialized>) — cast applied to an untyped register",
     re.compile(r"\(the-as\s+\S+\s+<uninitialized>\)")),
    ("pp-pseudotoken", 2,
     "<pp> — process-pointer pseudo-token leaked from state code",
     re.compile(r"<pp>")),
    ("raw-asm-mov64", 2,
     "bare .mov64 outside asm-func — asm op leaked into GOAL output",
     re.compile(r"^\s*\.mov64\s+\S+", re.M)),
    ("raw-asm-lwu", 2,
     "bare .lwu outside asm-func",
     re.compile(r"^\s*\.lwu\s+\S+", re.M)),
    ("defmethod-empty-args", 1,
     "(defmethod NAME () ...) — arg types not inferred (signature missing)",
     re.compile(r"^\(defmethod\s+\S+\s+\(\)\s", re.M)),
]


def pick_decomp_dir() -> Path:
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists() and any(p.glob("*_disasm.gc")):
            return p
    return DECOMP_PRIMARY


def _strip_diagnostic_comments(text: str) -> str:
    """Drop `;;`-prefixed lines so we only scan emitted GOAL source.

    Type-propagation diagnostics (`;; ERROR: failed type prop ... <uninitialized>
    ...`) are comment-lines, not leaked placeholder tokens. Matching them
    produces false positives that dominate the queue and bury real patches.
    """
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(";;") or stripped.startswith(";"):
            continue
        out.append(line)
    return "".join(out)


def scan(decomp_dir: Path) -> dict:
    """Return per-pattern {id: {count, files: Counter, samples}}."""
    results: dict[str, dict] = {
        pid: {"count": 0, "files": collections.Counter(), "samples": [], "severity": sev, "desc": desc}
        for pid, sev, desc, _ in PATTERNS
    }
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        text = _strip_diagnostic_comments(fp.read_text(errors="replace"))
        stem = fp.name[: -len("_disasm.gc")]
        for pid, sev, desc, pat in PATTERNS:
            hits = pat.findall(text)
            if hits:
                results[pid]["count"] += len(hits)
                results[pid]["files"][stem] += len(hits)
                if len(results[pid]["samples"]) < 3:
                    # Capture up to 3 distinct sample strings per pattern.
                    for h in hits[:3]:
                        s = h if isinstance(h, str) else " ".join(h)
                        s = s.strip()
                        if s and s not in results[pid]["samples"]:
                            results[pid]["samples"].append(s[:140])
                            if len(results[pid]["samples"]) >= 3:
                                break
    return results


def score(info: dict) -> float:
    """Higher = more attractive C++ patch target."""
    count = info["count"]
    files = len(info["files"])
    sev = info["severity"]
    return round(count * sev - 0.01 * files, 2)


def format_md(results: dict) -> str:
    ranked = sorted(
        [(pid, info) for pid, info in results.items() if info["count"] > 0],
        key=lambda kv: -score(kv[1]),
    )
    lines = [
        "# jakx C++ decompiler patch queue",
        "",
        f"_source: scripts/jakx_watch/cpp_patch_queue.py  ·  "
        f"patterns probed: {len(PATTERNS)}  ·  "
        f"non-zero: {len(ranked)}_",
        "",
        "Recurring malformed emissions in the jakx decomp output. Each row is "
        "a **single decompiler C++ patch target** — fixing the emitter clears "
        "ALL occurrences at once, so a 200-count row is 200 marker-deletes in "
        "one PR.",
        "",
        "Severity scale: **4** goalc hard-reject · **3** goalc compile error · "
        "**2** runtime undefined · **1** noise.",
        "",
    ]
    if not ranked:
        lines.append("_(queue empty — no tracked malformed patterns in current decomp output)_")
    else:
        lines.append("| # | score | sev | pattern | count | files | description |")
        lines.append("|---|------:|:---:|---------|------:|------:|-------------|")
        for i, (pid, info) in enumerate(ranked, 1):
            lines.append(
                f"| {i} | {score(info)} | {info['severity']} | `{pid}` | "
                f"{info['count']} | {len(info['files'])} | {info['desc']} |"
            )
        lines.append("")
        lines.append("## detail + top offender files")
        for pid, info in ranked[:10]:
            lines.append("")
            lines.append(f"### `{pid}` (sev={info['severity']}, count={info['count']}, files={len(info['files'])})")
            lines.append("")
            lines.append(f"{info['desc']}")
            lines.append("")
            lines.append("**top offender files:**")
            for name, c in info["files"].most_common(8):
                lines.append(f"- `{name}` — {c} hit(s)")
            if info["samples"]:
                lines.append("")
                lines.append("**sample emissions:**")
                for s in info["samples"]:
                    lines.append(f"- `{s}`")
    lines.append("")
    lines.append("## How to use this queue")
    lines.append("")
    lines.append(
        "1. Pick the row with the highest **score** that's still an unpatched "
        "pattern."
    )
    lines.append(
        "2. Read a few offender files to confirm the pattern is consistent "
        "(same root cause, not superficially-similar but distinct bugs)."
    )
    lines.append(
        "3. Locate the emitter in `decompiler/analysis/*.cpp` or "
        "`decompiler/IR2/*.cpp` that's producing the malformed output."
    )
    lines.append(
        "4. Patch the emitter; re-run `bash scripts/jakx_watch/run.sh`."
    )
    lines.append(
        "5. The row should drop to zero — if it doesn't, the pattern has "
        "multiple emission paths (split it into a sub-pattern)."
    )
    return "\n".join(lines)


def persist(results: dict) -> None:
    if not LATEST.exists():
        return
    try:
        snap = json.loads(LATEST.read_text())
    except Exception:
        return
    ranked = sorted(
        [(pid, info) for pid, info in results.items() if info["count"] > 0],
        key=lambda kv: -score(kv[1]),
    )
    snap["cpp_patch_queue"] = {
        "probed": len(PATTERNS),
        "non_zero": len(ranked),
        "top": [
            {
                "id": pid,
                "severity": info["severity"],
                "count": info["count"],
                "files": len(info["files"]),
                "score": score(info),
                "desc": info["desc"],
                "top_files": info["files"].most_common(5),
            }
            for pid, info in ranked[:10]
        ],
    }
    LATEST.write_text(json.dumps(snap, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decomp-out", help="Decomp output dir (default: auto)")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists() or not any(decomp_dir.glob("*_disasm.gc")):
        print(f"no _disasm.gc files in {decomp_dir}", file=sys.stderr)
        if not args.no_write:
            QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
            QUEUE_MD.write_text(
                "# jakx C++ decompiler patch queue\n\n"
                "**No decomp output available.** Run "
                "`JAKX_WATCH_FORCE=1 bash scripts/jakx_watch/run.sh` first.\n"
            )
        return 0

    results = scan(decomp_dir)
    ranked = sorted(
        [(pid, info) for pid, info in results.items() if info["count"] > 0],
        key=lambda kv: -score(kv[1]),
    )
    print(f"non-zero patterns: {len(ranked)} / {len(PATTERNS)}")
    for pid, info in ranked[:12]:
        print(
            f"  {score(info):>7}  sev={info['severity']}  "
            f"{pid:<24}  count={info['count']:>5}  files={len(info['files']):>4}"
        )

    if not args.no_write:
        md = format_md(results)
        QUEUE_MD.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_MD.write_text(md)
        persist(results)
        print(f"\nwrote {QUEUE_MD.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
