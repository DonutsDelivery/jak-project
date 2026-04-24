#!/usr/bin/env python3
"""One-off: cast v0/process → in-game-hud at offset 6372 stores.

Heuristic: ``ir2-store-process-proxy``.

For stores like ``(s.w! (+ v0 6372) 0)`` where the base register's
pre-type is a generic ``process`` (not resolvable), but the enclosing
file is a ``hud-*.gc`` whose natural subclass tree is rooted at
``in-game-hud`` (the only reasonable process descendant with a field
at offset 6372 that matches the store width), emit a type_cast on
the base register to ``in-game-hud``.

Narrow tool — only handles one (base=process, offset=6372) case with
hud-* filename gate. If more similar cases surface we can generalize.
Gated through apply_guard like the sibling scripts.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402
from ir2_store_cast_extract import (  # noqa: E402
    scan_ir2_file_stores,
    _strip_reg_suffix,
    _is_mips_reg,
)
from ir2_type_cast_extract import (  # noqa: E402
    DECOMP_OUT_FALLBACK,
    DECOMP_OUT_PRIMARY,
    TYPE_CASTS_JAKX,
    append_new_keys,
    existing_covers,
    extend_existing_key,
    load_jsonc,
)

ROOT = Path(__file__).resolve().parents[2]

# (pretype, offset) -> target cast type, filename pattern
RULES = [
    # process at 6372 in hud-*.gc -> in-game-hud (4-byte manager basic)
    {"pretype": "process", "offset": 6372, "target": "in-game-hud",
     "file_pattern": re.compile(r"^hud(-|_|$)")},
]


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--batch-size", type=int, default=0)
    ap.add_argument("--err-slack", type=int, default=0)
    ap.add_argument("--decomp-out", default=None)
    args = ap.parse_args()
    if args.apply:
        args.dry_run = False

    decomp_dir = Path(args.decomp_out) if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out not found: {decomp_dir}", file=sys.stderr)
        return 1

    existing = load_jsonc(TYPE_CASTS_JAKX)
    print(f"type_casts: {len(existing)} keys")

    reasons: Counter[str] = Counter()
    candidates: list[tuple[str, int, str, str]] = []  # (fn_key, op, reg, cast_ty)

    for fp in sorted(decomp_dir.glob("*_ir2.asm")):
        stem = fp.name[: -len("_ir2.asm")]
        try:
            errs = scan_ir2_file_stores(fp)
        except FileNotFoundError:
            continue
        for err, pretypes, mips_base, mips_val in errs:
            if pretypes is None:
                continue
            base_mips = mips_base or _strip_reg_suffix(err.base_reg)
            if not _is_mips_reg(base_mips):
                continue
            bpre = pretypes.get(base_mips, "").strip()
            for rule in RULES:
                if bpre != rule["pretype"]:
                    continue
                if err.offset != rule["offset"]:
                    continue
                if not rule["file_pattern"].match(stem):
                    continue
                target = rule["target"]
                # Never cast to the same type
                if bpre == target:
                    reasons["same-type"] += 1
                    continue
                if existing_covers(existing, err.fn_key, err.op_num, base_mips):
                    reasons["already-covered"] += 1
                    continue
                candidates.append((err.fn_key, err.op_num, base_mips, target))
                break

    print(f"\nCandidates: {len(candidates)}")
    for r, c in reasons.most_common():
        print(f"  {r}: {c}")

    # Dedup
    seen = set()
    unique = []
    for c in candidates:
        k = (c[0], c[1], c[2])
        if k in seen:
            continue
        seen.add(k)
        unique.append(c)
    candidates = unique

    if args.batch_size > 0:
        candidates = candidates[: args.batch_size]

    if not candidates:
        print("Nothing to propose.")
        return 0

    proposed: dict[str, list[list]] = {}
    for fn, op, reg, ty in candidates:
        proposed.setdefault(fn, []).append([op, reg, ty])

    total = sum(len(v) for v in proposed.values())
    print(f"\nProposing {total} entries across {len(proposed)} fns:")
    for fn, entries in sorted(proposed.items())[:20]:
        entries.sort(key=lambda e: e[0])
        for e in entries[:3]:
            print(f"  {fn}: [{e[0]}, {e[1]!r}, {e[2]!r}]")

    if args.dry_run:
        print("\n--dry-run: pass --apply to write and gate.")
        return 0

    def do_apply() -> list[Path]:
        brand_new: dict[str, list[list]] = {}
        to_extend: dict[str, list[list]] = {}
        for fn, entries in proposed.items():
            if fn in existing:
                to_extend[fn] = entries
            else:
                brand_new[fn] = entries
        for fn, entries in sorted(to_extend.items()):
            entries.sort(key=lambda e: e[0])
            ok = extend_existing_key(TYPE_CASTS_JAKX, fn, entries)
            if not ok:
                print(f"WARN: failed to extend key {fn!r}", file=sys.stderr)
        if brand_new:
            append_new_keys(TYPE_CASTS_JAKX, brand_new)
        return [TYPE_CASTS_JAKX]

    commit_msg = (
        f"fix(jakx/type-casts): ir2-store-process-proxy {total} stores\n\n"
        f"Cast generic process base to in-game-hud for hud-* file stores at\n"
        f"offset 6372 (the manager field). Narrow lexical-proximity rule for\n"
        f"the one systematic failure pattern the main extractor can't handle.\n\n"
        f"Gated via apply_guard (err_slack={args.err_slack}).\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    result = run_with_guard(
        do_apply,
        label=f"ir2-store-process-proxy/{total}",
        err_slack=args.err_slack,
        warn_slack=5,
        commit_on_pass=args.commit,
        commit_message=commit_msg,
    )

    if not result.passed:
        print(f"FAIL: {result.reason}", file=sys.stderr)
        return 1
    print(f"PASS: Δerr={result.delta_err:+d}  Δwarn={result.delta_warn:+d}")
    if args.commit and result.commit_sha:
        print(f"  committed as {result.commit_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
