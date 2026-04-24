#!/usr/bin/env python3
"""Emit type_casts.jsonc entries for "Failed store" IR2 errors.

Heuristic: ``ir2-store-fieldtype``.

For each ``;; ERROR: Failed store: (s.W! (+ BASE N) VALUE) at op M`` in IR2
output where the BASE register has a known pre-type annotation ``[BASE: TY]``
on the asm op-line, look up the field at offset N in TY's deftype (via
``all-types.gc``) and emit a type_cast entry to nudge the decompiler into
resolving the store as ``(set! (-> base field) value)``.

Two sub-strategies (pick via ``--cast-target``):

* ``base`` (default): emit cast on BASE register to its own type.
  This just re-asserts the base type — useful when the decompiler widened
  it (e.g. to ``structure`` or ``object``) by the time the store runs.
  Lowest risk.
* ``value``: emit cast on the VALUE register to the field's type.
  Helps when the failure is a value/field type mismatch.
* ``both``: emit BOTH a base-reassertion and a value cast.

Zero-offset stores like ``(s.w! BASE VALUE)`` are parsed as offset=0
(the same way loads at offset 0 are handled).

All applies go through ``apply_guard`` — bad entries veto automatically.
Heavily reuses helpers from ``ir2_type_cast_extract``.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402
from ir2_type_cast_extract import (  # noqa: E402
    ALL_TYPES,
    DECOMP_OUT_FALLBACK,
    DECOMP_OUT_PRIMARY,
    MIPS_REG_ALT,
    RE_ASM_OP_LINE,
    TYPE_CASTS_JAKX,
    _ATOM,
    _OPAQUE_FIELD_TYPES,
    _UNUSABLE_BASE_TYPES,
    _classify_fn_header,
    append_new_keys,
    build_field_index,
    existing_covers,
    extend_existing_key,
    is_usable_base_type,
    load_jsonc,
    parse_pretypes,
    resolve_field_type,
)

ROOT = Path(__file__).resolve().parents[2]

# Store errors: two forms
#   (s.w! (+ base N) value)     — offset N, non-zero
#   (s.w! base value)           — offset 0
# s.w! / s.b! / s.h! / s.d! / s.f! / s.q!
# NOTE: base name may be an IR variable like "this", "arg0", "v1-2", or
# even "(the-as foo v1-2)". For the "(the-as ...)" case we skip (value
# already gets an explicit cast elsewhere). For named args we map via the
# asm instruction's real MIPS base reg (parsed separately).
RE_STORE_ERR_OFF = re.compile(
    r";;\s*ERROR:\s*Failed store:\s*\((s\.\w+)!\s+\(\+\s+(\S+)\s+(-?\d+)\)\s+(\S+)\)"
    r"\s+at op\s+(\d+)"
)
RE_STORE_ERR_ZERO = re.compile(
    r";;\s*ERROR:\s*Failed store:\s*\((s\.\w+)!\s+(\S+)\s+(\S+)\)"
    r"\s+at op\s+(\d+)"
)

# MIPS store: "sw v1, 252(gp)" — extract base reg from "(gp)" part.
RE_MIPS_STORE_BASE = re.compile(
    r"^\s+s[bhwdq]c?1?\s+\S+,\s*-?\d+\((" + MIPS_REG_ALT + r")\)"
)
# MIPS store: extract the value (source) reg — the register between
# the store mnemonic and the comma. "swc1 f0, 76(a0)" → "f0".
RE_MIPS_STORE_VALUE = re.compile(
    r"^\s+s[bhwdq]c?1?\s+(\S+),\s*-?\d+\("
)

# Store width (bytes) — used to sanity-check vs field size (optional).
STORE_WIDTH = {
    "s.b": 1,
    "s.h": 2,
    "s.w": 4,
    "s.f": 4,
    "s.d": 8,
    "s.q": 16,
}


@dataclass
class StoreErr:
    file_stem: str
    fn_key: str
    op_num: int
    store_op: str           # "s.w" etc (no trailing !)
    base_reg: str           # IR reg with suffix, e.g. "gp" or "a0-1"
    value_reg: str          # IR reg or literal ("#f", "0", etc.)
    offset: int


def _strip_reg_suffix(ir_reg: str) -> str:
    """'a0-10' -> 'a0'. Literals (e.g. '#f', '0') pass through unchanged."""
    # Only strip if it matches a MIPS reg with numeric suffix
    m = re.match(r"^(" + MIPS_REG_ALT + r")-\d+$", ir_reg)
    if m:
        return m.group(1)
    # Plain MIPS reg (no -N)
    if re.match(r"^" + MIPS_REG_ALT + r"$", ir_reg):
        return ir_reg
    return ir_reg  # literal — can't cast it


def _is_mips_reg(s: str) -> bool:
    return bool(re.match(r"^" + MIPS_REG_ALT + r"$", s))


def _parse_mips_store_base(asm_line: str) -> str | None:
    """Extract the base MIPS reg from a store instruction line.

    e.g. "    sw v1, 252(gp)" → "gp". Returns None if no match.
    """
    m = RE_MIPS_STORE_BASE.match(asm_line)
    if m:
        return m.group(1)
    return None


def _parse_mips_store_value(asm_line: str) -> str | None:
    """Extract the value/source reg from a store instruction line.

    e.g. "    sw v1, 252(gp)" → "v1". Returns None if no match.
    Note: FPU stores (swc1) use f-regs like 'f0' — these are NOT in
    MIPS_REG_ALT and cannot be cast via type_casts (float cast is a
    different path). Caller must filter.
    """
    m = RE_MIPS_STORE_VALUE.match(asm_line)
    if m:
        return m.group(1)
    return None


def scan_ir2_file_stores(fp: Path) -> list[tuple[StoreErr, dict[str, str] | None, str | None]]:
    """Scan one IR2 .asm file.

    Returns list of (StoreErr, pretypes_dict|None, mips_base_reg|None, mips_val_reg|None).
    mips_base_reg / mips_val_reg are parsed from the asm store instruction
    itself, which handles cases where the IR2 ``BASE`` name is
    ``this``/``arg0``/``self`` (unrelated to the MIPS reg) — the MIPS reg
    is what the pre-types dict is keyed on.
    """
    stem = fp.name[: -len("_ir2.asm")]
    lines = fp.read_text(errors="replace").splitlines()

    # Pass 1: fn spans
    fn_spans: list[tuple[int, int, str]] = []
    curr_start = -1
    curr_key: str | None = None
    for i, line in enumerate(lines):
        fn_key = _classify_fn_header(line)
        if fn_key is not None:
            if curr_start >= 0 and curr_key is not None:
                fn_spans.append((curr_start, i, curr_key))
            curr_start = i
            curr_key = fn_key
    if curr_start >= 0 and curr_key is not None:
        fn_spans.append((curr_start, len(lines), curr_key))

    results: list[tuple[StoreErr, dict[str, str] | None, str | None, str | None]] = []
    for start, end, fn_key in fn_spans:
        # Build op -> asm-line-idx map
        op_to_line: dict[int, int] = {}
        for i in range(start, end):
            m = re.search(r";;\s*\[\s*(\d+)\]", lines[i])
            if m:
                op = int(m.group(1))
                op_to_line.setdefault(op, i)
        # Errors
        for i in range(start, end):
            line = lines[i]
            m = RE_STORE_ERR_OFF.search(line)
            if m:
                store_op = m.group(1).rstrip("!")
                base_reg_ir = m.group(2)
                offset = int(m.group(3))
                value_reg = m.group(4)
                op_num = int(m.group(5))
            else:
                m = RE_STORE_ERR_ZERO.search(line)
                if not m:
                    continue
                # Only accept if the second and third args are regs or literals
                # (not a (+...) sub-expression — that'd be caught by _OFF above)
                store_op = m.group(1).rstrip("!")
                base_reg_ir = m.group(2)
                value_reg = m.group(3)
                op_num = int(m.group(4))
                offset = 0
                # Skip if base_reg_ir looks like a (+ ...) prefix that didn't match OFF (paren unbalanced)
                if base_reg_ir.startswith("("):
                    continue

            err = StoreErr(
                file_stem=stem,
                fn_key=fn_key,
                op_num=op_num,
                store_op=store_op,
                base_reg=base_reg_ir,
                value_reg=value_reg,
                offset=offset,
            )

            asm_idx = op_to_line.get(op_num)
            if asm_idx is None:
                results.append((err, None, None, None))
                continue

            asm_line = lines[asm_idx]
            mm = RE_ASM_OP_LINE.search(asm_line)
            if not mm:
                results.append((err, None, None, None))
                continue
            pretypes = parse_pretypes(mm.group(2))
            mips_base = _parse_mips_store_base(asm_line)
            mips_val = _parse_mips_store_value(asm_line)
            results.append((err, pretypes, mips_base, mips_val))

    return results


# --- main ------------------------------------------------------------------

def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


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
    ap.add_argument("--apply", action="store_true",
                    help="Write type_casts.jsonc and run regression guard")
    ap.add_argument("--batch-size", type=int, default=0,
                    help="Cap entries at N (0 = unlimited)")
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--commit", action="store_true",
                    help="Auto-commit if guard passes")
    ap.add_argument("--err-slack", type=int, default=0)
    ap.add_argument("--skip-file", default=None,
                    help="File of lines 'fn_key|op|reg' to exclude")
    ap.add_argument("--stats", action="store_true",
                    help="Print candidate stats and exit")
    ap.add_argument("--cast-target", choices=["base", "value", "both"],
                    default="base",
                    help="Which register to cast: base (re-assert base type), "
                         "value (field type on the value), both. Default: base.")
    ap.add_argument("--only-file", default=None,
                    help="Only consider errors in this IR2 file stem (e.g. 'dma')")
    ap.add_argument("--store-ops", default="",
                    help="Comma-separated store ops to include (e.g. 's.w,s.b'). "
                         "Default: all.")
    args = ap.parse_args()

    if args.apply:
        args.dry_run = False

    decomp_dir = Path(args.decomp_out) if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out not found: {decomp_dir}", file=sys.stderr)
        return 1

    only_store_ops: set[str] | None = None
    if args.store_ops:
        only_store_ops = set(s.strip() for s in args.store_ops.split(",") if s.strip())

    print(f"decomp_out:  {decomp_dir}")
    print(f"type_casts:  {TYPE_CASTS_JAKX.relative_to(ROOT)}")

    print("Building field index ...", end=" ", flush=True)
    fields, parents = build_field_index(ALL_TYPES)
    print(f"{len(fields)} types, {sum(len(v) for v in fields.values())} fields")

    print("Loading existing type_casts.jsonc ...", end=" ", flush=True)
    existing = load_jsonc(TYPE_CASTS_JAKX)
    print(f"{len(existing)} keys, "
          f"{sum(len(v) for v in existing.values())} entries")

    skip_set = _read_skip_set(args.skip_file)
    if skip_set:
        print(f"skip-file: {len(skip_set)} entries")

    # Scan
    print("Scanning IR2 files for Failed store ...", end=" ", flush=True)
    files = sorted(decomp_dir.glob("*_ir2.asm"))
    if args.only_file:
        files = [f for f in files if f.name[: -len("_ir2.asm")] == args.only_file]
    all_errs: list[tuple[StoreErr, dict[str, str] | None, str | None, str | None]] = []
    for fp in files:
        all_errs.extend(scan_ir2_file_stores(fp))
    print(f"{len(all_errs)} store errors across {len(files)} files")

    # Filter by store-op
    if only_store_ops is not None:
        all_errs = [(e, p, mb, mv) for (e, p, mb, mv) in all_errs if e.store_op in only_store_ops]
        print(f"  filter --store-ops: {len(all_errs)} remain")

    reasons: Counter[str] = Counter()
    candidates: list[tuple[StoreErr, str, str, str]] = []  # (err, reg, cast_ty, why)

    for err, pretypes, mips_base, mips_val in all_errs:
        if pretypes is None:
            reasons["no-asm-pretype-match"] += 1
            continue

        # Prefer MIPS-reg parsed from the asm instruction (handles this/arg0).
        # Fall back to the IR reg suffix-stripped if we didn't get one.
        base_mips = mips_base or _strip_reg_suffix(err.base_reg)
        if not _is_mips_reg(base_mips):
            reasons["no-mips-base"] += 1
            continue
        base_pretype = pretypes.get(base_mips)
        if base_pretype is None:
            reasons["no-base-pretype"] += 1
            continue
        base_pretype = base_pretype.strip()
        if not is_usable_base_type(base_pretype):
            reasons[f"unusable-base:{base_pretype[:30]}"] += 1
            continue
        if err.offset < 0:
            reasons["negative-offset"] += 1
            continue

        field_type = resolve_field_type(fields, parents, base_pretype, err.offset)
        if field_type is None:
            reasons["field-not-found"] += 1
            continue

        # Build target list
        targets: list[tuple[str, str, str, str]] = []
        if args.cast_target in ("base", "both"):
            # Cast base → its own pretype (re-assertion)
            targets.append((base_mips, base_pretype, "base-reassert", "base"))

        if args.cast_target in ("value", "both"):
            value_mips = mips_val or _strip_reg_suffix(err.value_reg)
            if value_mips and _is_mips_reg(value_mips):
                # Skip if value pretype already matches field type
                val_pretype = pretypes.get(value_mips, "").strip()
                if val_pretype == field_type:
                    reasons["value-matches-field"] += 1
                else:
                    # Avoid casting to opaque primitives — won't help
                    if field_type in _OPAQUE_FIELD_TYPES:
                        reasons[f"opaque-field:{field_type}"] += 1
                    else:
                        targets.append((value_mips, field_type, "value-cast", "value"))
            else:
                # e.g. FPU reg f0 (swc1), or non-reg value
                reasons["value-not-gpr"] += 1

        if not targets:
            continue

        for reg, cast_ty, why, kind in targets:
            if existing_covers(existing, err.fn_key, err.op_num, reg):
                reasons[f"already-covered-{kind}"] += 1
                continue
            skip_key = f"{err.fn_key}|{err.op_num}|{reg}"
            if skip_key in skip_set:
                reasons["skip-file"] += 1
                continue
            candidates.append((err, reg, cast_ty, why))

    print("\nBreakdown:")
    print(f"  candidates:           {len(candidates)}")
    for r, ct in reasons.most_common():
        print(f"  {r:40s} {ct}")

    if args.stats:
        return 0

    if not candidates:
        print("Nothing to add.")
        return 0

    # Dedup by (fn, op, reg)
    seen: set[tuple[str, int, str]] = set()
    unique: list[tuple[StoreErr, str, str, str]] = []
    for err, reg, cast_ty, why in candidates:
        key = (err.fn_key, err.op_num, reg)
        if key in seen:
            continue
        seen.add(key)
        unique.append((err, reg, cast_ty, why))
    if len(unique) < len(candidates):
        print(f"  dedup:              {len(candidates)} -> {len(unique)}")
    candidates = unique

    # Group by fn
    proposed: dict[str, list[list]] = {}
    for err, reg, cast_ty, _why in candidates:
        proposed.setdefault(err.fn_key, []).append([err.op_num, reg, cast_ty])

    # Apply batch cap
    if args.batch_size > 0:
        flat = []
        for fn, entries in proposed.items():
            for e in entries:
                flat.append((fn, e))
        flat = flat[: args.batch_size]
        proposed = {}
        for fn, e in flat:
            proposed.setdefault(fn, []).append(e)

    total = sum(len(v) for v in proposed.values())
    print(f"\nProposing {total} entries across {len(proposed)} fns:")
    shown = 0
    for fn, entries in sorted(proposed.items()):
        entries.sort(key=lambda e: e[0])
        if shown < 40:
            print(f"  {fn}:")
            for e in entries[:8]:
                print(f"    [{e[0]}, {e[1]!r}, {e[2]!r}]")
                shown += 1
            if len(entries) > 8:
                print(f"    ... ({len(entries) - 8} more in this fn)")
    if shown < total:
        print(f"  ... ({total - shown} more entries omitted from preview)")

    if args.dry_run:
        print("\n--dry-run: pass --apply to write and gate.")
        return 0

    # --- apply ---
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
        f"fix(jakx/type-casts): ir2-store-fieldtype extract {total} stores\n\n"
        f"Heuristic: read base-register pre-type on IR2 asm line for\n"
        f"'Failed store' errors; look up field at offset N in all-types.gc;\n"
        f"emit cast ({args.cast_target}) so the decompiler resolves the\n"
        f"store as (set! (-> base field) value).\n\n"
        f"Gated via apply_guard (err_slack={args.err_slack}).\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    print(f"\nApplying {total} entries via apply_guard ...")
    result = run_with_guard(
        do_apply,
        label=f"ir2-store-fieldtype/{total}",
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
