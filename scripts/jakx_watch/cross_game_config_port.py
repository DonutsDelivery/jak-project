#!/usr/bin/env python3
"""cross_game_config_port.py — port jak3's config entries to jakx.

For each jakx file with errors that look like type-prop or sig issues,
look up the same function/method in jak3's config and propose porting
the entry. jak3's type_casts.jsonc has 3407 keys covering ~12000 entries
that are battle-tested.

Strategy:
  1. Scan jakx IR2 for "Could not figure out load" + "Function may read a register that is not set"
  2. For each error, get the function name (e.g., "(method 11 memory-usage-block)")
  3. Look up that function in jak3's type_casts.jsonc
  4. If jak3 has entries that jakx LACKS at the matching op_idx, propose porting them

Output: .jakx_watch/research/cross_game_port_<ts>.md (candidate list)
        .jakx_watch/research/cross_game_port_<ts>.jsonc (apply-able patch fragment)

Usage:
  python3 scripts/jakx_watch/cross_game_config_port.py [--apply] [--max-batch N]

If --apply, edits jakx's type_casts.jsonc with the candidates and runs apply_guard.
Without --apply, just generates the report (dry-run).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "jakx_watch"
RESEARCH = ROOT / ".jakx_watch" / "research"
DECOMP_OUT = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
TYPE_CASTS_JAKX = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "type_casts.jsonc"
TYPE_CASTS_JAK3 = ROOT / "decompiler" / "config" / "jak3" / "ntsc_v1" / "type_casts.jsonc"

sys.path.insert(0, str(SCRIPTS))
from apply_guard import run_with_guard  # noqa: E402

ERROR_LOAD_RE = re.compile(
    r";;\s*ERROR:\s*failed type prop at (\d+):\s*Could not figure out load:\s*\(set!\s+(\w+)\s+\(l\.\w+\s+\(?\+?\s*(\w+)\s*(\d+)\)?\)\)"
)
FUNC_HEADER_RE = re.compile(r"^;\s*\.function\s+(.+)$")


def load_jsonc(path):
    """Load a .jsonc (drop // and /* */ comments)."""
    text = path.read_text()
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r",(\s*[}\]])", r"\1", text)  # trailing commas
    return json.loads(text)


def find_failing_function(ir2_text, error_line_no):
    lines = ir2_text.splitlines()
    for i in range(error_line_no, max(0, error_line_no - 200), -1):
        m = FUNC_HEADER_RE.match(lines[i])
        if m:
            return m.group(1).strip()
    return None


def scan_jakx_errors():
    """Return dict[func_name] -> set of error op indices."""
    func_errors = {}
    for ir2_path in DECOMP_OUT.glob("*_ir2.asm"):
        text = ir2_path.read_text(errors="replace")
        for i, line in enumerate(text.splitlines()):
            m = ERROR_LOAD_RE.search(line)
            if m:
                func = find_failing_function(text, i)
                if func:
                    func_errors.setdefault(func, set()).add(int(m.group(1)))
    return func_errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--max-batch", type=int, default=50,
                    help="Cap candidates per run")
    args = ap.parse_args()

    print("[cross-port] loading jak3 type_casts ...", end=" ", flush=True)
    jak3_casts = load_jsonc(TYPE_CASTS_JAK3)
    print(f"{len(jak3_casts)} keys")

    print("[cross-port] loading jakx type_casts ...", end=" ", flush=True)
    jakx_casts = load_jsonc(TYPE_CASTS_JAKX)
    print(f"{len(jakx_casts)} keys")

    print("[cross-port] scanning jakx IR2 errors ...", end=" ", flush=True)
    jakx_errors = scan_jakx_errors()
    print(f"{len(jakx_errors)} functions with type-prop errors")

    candidates = []  # list of (func, [entries to add])
    skipped_no_jak3 = 0
    skipped_already_have = 0
    # Loose match: port jak3's casts for any function where jakx has ANY
    # error. Op indices drift between games (Lane 2 cycle 4 finding); the
    # rc-positive bisect-revert in apply_guard handles bad ports.
    for func, error_ops in jakx_errors.items():
        if func not in jak3_casts:
            skipped_no_jak3 += 1
            continue
        jak3_entries = jak3_casts[func]
        existing = jakx_casts.get(func, [])
        # Build (op, reg) set of casts jakx already has
        existing_op_regs = set()
        for e in existing:
            if isinstance(e, list) and len(e) >= 3:
                op = e[0]
                reg = e[1]
                if isinstance(op, list):
                    for o in range(op[0], op[1] + 1):
                        existing_op_regs.add((o, reg))
                else:
                    existing_op_regs.add((op, reg))
        new_entries = []
        for e in jak3_entries:
            if not isinstance(e, list) or len(e) < 3:
                continue
            op = e[0]
            reg = e[1]
            if isinstance(op, list):
                continue  # skip range entries (apply later)
            if (op, reg) in existing_op_regs:
                skipped_already_have += 1
                continue
            new_entries.append(e)
        if new_entries:
            candidates.append((func, new_entries))

    total_new = sum(len(e) for _, e in candidates)
    print(f"\n[cross-port] candidates: {total_new} entries across {len(candidates)} functions")
    print(f"[cross-port] skipped: {skipped_no_jak3} functions not in jak3, {skipped_already_have} (already have cast)")

    if args.max_batch and total_new > args.max_batch:
        # Keep the top max_batch entries (high-value funcs first by entry count)
        candidates.sort(key=lambda x: -len(x[1]))
        kept = []
        running = 0
        for func, entries in candidates:
            if running + len(entries) > args.max_batch:
                slice_n = args.max_batch - running
                if slice_n > 0:
                    kept.append((func, entries[:slice_n]))
                break
            kept.append((func, entries))
            running += len(entries)
        candidates = kept
        total_new = sum(len(e) for _, e in candidates)
        print(f"[cross-port] limited to {total_new} entries (--max-batch={args.max_batch})")

    RESEARCH.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    report_path = RESEARCH / f"cross_game_port_{ts}.md"

    body = [f"# Cross-game config port from jak3 → jakx ({ts})", "",
            f"Total candidate entries: {total_new}",
            f"Functions affected: {len(candidates)}",
            f"Skipped (no jak3 entry): {skipped_no_jak3}",
            f"Skipped (jakx already has): {skipped_already_have}",
            ""]
    if candidates:
        body.extend(["## Candidates", "",
                     "| function | new entries |",
                     "|---|---:|"])
        for func, entries in candidates[:50]:
            body.append(f"| `{func}` | {len(entries)} |")
        body.append("")

    report_path.write_text("\n".join(body))
    print(f"[cross-port] report: {report_path}")

    if not args.apply:
        print("[cross-port] dry-run only; pass --apply to actually edit")
        return 0

    if not candidates:
        print("[cross-port] nothing to apply")
        return 0

    # Build the edit function for apply_guard
    def apply_edits():
        # Re-load latest jakx casts (in case file changed)
        text = TYPE_CASTS_JAKX.read_text()
        # Clean parse for edits
        clean = re.sub(r"//[^\n]*", "", text)
        clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL)
        clean = re.sub(r",(\s*[}\]])", r"\1", clean)
        d = json.loads(clean)
        for func, entries in candidates:
            if func in d:
                # Append non-duplicate entries
                existing_keys = set()
                for e in d[func]:
                    if isinstance(e, list) and len(e) >= 3 and not isinstance(e[0], list):
                        existing_keys.add((e[0], e[1]))
                for new in entries:
                    if (new[0], new[1]) not in existing_keys:
                        d[func].append(new)
            else:
                d[func] = entries
        # Pretty-write back
        TYPE_CASTS_JAKX.write_text(json.dumps(d, indent=2) + "\n")
        return [TYPE_CASTS_JAKX]

    label = f"cross-port-jak3-{total_new}-entries"
    msg = (f"fix(jakx/type-casts): cross-port {total_new} entries from jak3 "
           f"({len(candidates)} fns)\n\n"
           f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>\n")
    result = run_with_guard(apply_edits, label=label,
                            commit_on_pass=args.commit, commit_message=msg)
    if not result.passed:
        print(f"[cross-port] FAIL — {result.reason}")
        return 2
    print(f"[cross-port] PASS — Δerr={result.delta_err}, sha={result.commit_sha[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
