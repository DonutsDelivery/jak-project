#!/usr/bin/env python3
"""Wrap inspect_to_type_casts.py with apply_guard + batching.

The existing ``inspect_to_type_casts.py`` walks all method bodies, finds
failing struct-field loads whose base reg is the method's this-pointer
(a0 for any method, also gp for method 3), looks up the field in
all-types.gc, and emits ``[op, DST, field_type]`` cast entries. Its
heuristic is known-good — commits like 936c3736a shipped Δerr wins.

This wrapper:
  1. Runs the extractor in-process to get proposed casts.
  2. Applies a random subset (default 10) to type_casts.jsonc.
  3. Runs the decompiler via ``apply_guard``.
  4. Commits on PASS, reverts on FAIL.
  5. Accepts ``--skip-file`` of ``fn_key|op|reg`` to exclude bad entries.

Unlike the raw extractor, this lets us DRAIN the candidate pool safely
in the presence of proposals that individually regress decomp output.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402
from inspect_to_type_casts import (  # noqa: E402
    ALL_TYPES,
    TYPE_CASTS,
    build_field_index,
    pick_decomp_dir,
    scan_method_field_loads,
)
from ir2_type_cast_extract import (  # noqa: E402
    append_new_keys,
    existing_covers,
    extend_existing_key,
    load_jsonc,
)

TYPE_CASTS_JAKX = TYPE_CASTS


def _read_skip_set(path: str | None) -> set[str]:
    if not path:
        return set()
    p = Path(path)
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.add(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--err-slack", type=int, default=3)
    ap.add_argument("--skip-file", default=None)
    ap.add_argument("--shuffle", action="store_true",
                    help="Shuffle candidates; useful when draining to avoid "
                         "repeatedly hitting the same poisoned entries first.")
    args = ap.parse_args()

    if args.apply:
        args.dry_run = False

    decomp_dir = pick_decomp_dir()
    print(f"decomp_out: {decomp_dir}")

    print("Building field index ...", end=" ", flush=True)
    fields, parents = build_field_index(ALL_TYPES)
    print(f"{len(fields)} types, {sum(len(v) for v in fields.values())} fields")

    print("Loading existing casts ...", end=" ", flush=True)
    existing = load_jsonc(TYPE_CASTS_JAKX)
    print(f"{len(existing)} keys")

    skip_set = _read_skip_set(args.skip_file)

    print("Scanning method field loads ...", end=" ", flush=True)
    raw = scan_method_field_loads(decomp_dir, fields, parents)
    total_raw = sum(len(v) for v in raw.values())
    print(f"{total_raw} candidates across {len(raw)} fns")

    # Flatten and filter
    flat = []
    for fn, entries in raw.items():
        for e in entries:
            op, reg, ty = e[0], e[1], e[2]
            if existing_covers(existing, fn, op, reg):
                continue
            skip_key = f"{fn}|{op}|{reg}"
            if skip_key in skip_set:
                continue
            flat.append((fn, [op, reg, ty]))

    print(f"  after dedup + skip: {len(flat)} candidates")

    if not flat:
        print("Nothing to add.")
        return 0

    if args.shuffle:
        random.shuffle(flat)

    # Cap to batch-size
    if args.batch_size > 0:
        flat = flat[: args.batch_size]

    # Group by fn
    proposed: dict[str, list[list]] = {}
    for fn, entry in flat:
        proposed.setdefault(fn, []).append(entry)

    total = sum(len(v) for v in proposed.values())
    print(f"\nProposing {total} entries across {len(proposed)} fns:")
    for fn, entries in sorted(proposed.items()):
        entries.sort(key=lambda e: e[0])
        print(f"  {fn}:")
        for e in entries:
            print(f"    [{e[0]}, {e[1]!r}, {e[2]!r}]")

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
                print(f"WARN: failed to extend {fn!r}", file=sys.stderr)
        if brand_new:
            append_new_keys(TYPE_CASTS_JAKX, brand_new)
        return [TYPE_CASTS_JAKX]

    commit_msg = (
        f"fix(jakx/type-casts): inspect-scanner {total} method-field loads\n\n"
        f"Via inspect_to_type_casts.scan_method_field_loads: for each failing\n"
        f"`(set! DST (LOAD (+ THIS OFFS)))` in a method body where THIS is a0\n"
        f"(or gp for method 3), look up TYPE.field[OFFS] in all-types.gc and\n"
        f"emit [op, DST, field_type]. Gated via apply_guard.\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    print(f"\nApplying {total} entries via apply_guard ...")
    result = run_with_guard(
        do_apply,
        label=f"inspect-dst/{total}",
        err_slack=args.err_slack,
        warn_slack=max(5, args.err_slack),
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
