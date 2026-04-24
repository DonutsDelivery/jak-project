#!/usr/bin/env python3
"""Emit base-register type_casts for "field not found at offset" loads
whose known base type has a descendant subclass that introduces the field.

Heuristic name: ``ir2-subclass-guess``.

Plugs into the same IR2 pre-type + apply_guard plumbing as
``ir2_type_cast_extract.py``.  The difference: this heuristic only fires
when the base register's pre-type does *not* contain the requested offset,
but a subclass of that type does.

For a load error like::

    ;; ERROR: failed type prop at 17: Could not figure out load: \\
        (set! a2 (l.wu (+ v1 156)))          ;; [v1: trsqv]

``trsqv`` has no field at offset 156, but its direct descendant
``collide-shape`` introduces ``(event-other symbol :offset-assert 156)``.
Emitting a SRC cast ``[17, "v1", "collide-shape"]`` upgrades v1 before
the load so type propagation resolves it on its own.

Hard rules
----------

* Only emit when the base is a "small-tree" type: the subtree of all
  descendants is ≤ MAX_DESC_SUBTREE nodes. Large roots like ``process``
  (hundreds of descendants, many of which use the same offset for
  unrelated fields) are systemically unreliable, so we skip them.
* Only consider descendants whose OWN field dict has the offset — the
  descendant that *introduces* the field at O. This naturally picks the
  shallowest meaningful subclass and avoids picking a random grand-child.
* Load width (l.b/l.h/l.w/l.d) must match the field's byte size.
* If multiple descendants introduce a field at O at the same minimum
  depth, try lexical-proximity tiebreak (base type's .gc file mentions
  the chosen descendant).  If still ambiguous, skip.
* Never cast to the SAME type as the current base pre-type (no-op,
  see P2's finding).
* Every apply goes through ``apply_guard`` (Δerr must be ≤0).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402
from ir2_type_cast_extract import (  # noqa: E402
    ALL_TYPES, DECOMP_OUT_FALLBACK, DECOMP_OUT_PRIMARY, TYPE_CASTS_JAKX,
    append_new_keys, build_field_index, existing_covers, extend_existing_key,
    is_usable_base_type, load_jsonc, resolve_field_type, scan_ir2_file,
)

ROOT = Path(__file__).resolve().parents[2]
GOAL_SRC_JAKX = ROOT / "goal_src" / "jakx"

# MIPS load op -> expected byte width on the bus
LOAD_WIDTH = {
    "l.b": 1, "l.bu": 1,
    "l.h": 2, "l.hu": 2,
    "l.w": 4, "l.wu": 4,
    "l.s": 4, "l.f": 4,
    "l.d": 8,
    "l.q": 16,
}

# GOAL primitive type -> byte size (for load-width validation)
_PRIMITIVE_SIZE = {
    "int8": 1, "uint8": 1,
    "int16": 2, "uint16": 2,
    "int32": 4, "uint32": 4, "float": 4,
    "int64": 8, "uint64": 8, "seconds": 8,
    "time-frame": 8,
    "int128": 16, "uint128": 16,
    # GOAL pointer-sized
    "symbol": 4, "basic": 4, "object": 4, "type": 4, "string": 4,
    "process": 4, "handle": 8,
    "pointer": 4, "function": 4,
    "meters": 4, "degrees": 4,
}

# Hard cap: if a base type has more descendants than this, the
# "subclass introduces field at offset" heuristic is too permissive
# (many unrelated subclasses use the same offset for unrelated fields).
# trsqv has 2 descendants: reliable.  process has 600+: not reliable.
MAX_DESC_SUBTREE = 10


def field_byte_size(ftype: str) -> int | None:
    """Approximate byte size of a GOAL type for width matching."""
    if ftype in _PRIMITIVE_SIZE:
        return _PRIMITIVE_SIZE[ftype]
    # Compound types like "(pointer uint32)" -> 4 bytes (pointer).
    if ftype.startswith("(pointer") or ftype.startswith("(function"):
        return 4
    # "(inline-array ...)" is inline and variable; refuse to validate.
    if ftype.startswith("(inline-array"):
        return None
    # Named structure or basic -> assume pointer-sized ref (4 bytes).
    # (If the field is actually an inline struct, size won't match and
    # we'll still be OK because the parent type would already know about
    # it — we'd never hit the field-not-found bucket.)
    return 4


# --- children index from parents dict ---------------------------------------

def build_children_index(parents: dict) -> dict[str, list[str]]:
    """Invert parents dict to parent -> [children]."""
    children: dict[str, list[str]] = {}
    for child, parent in parents.items():
        children.setdefault(parent, []).append(child)
    return children


def all_descendants(children: dict, root: str) -> list[str]:
    """Collect all proper descendants of root (BFS)."""
    out: list[str] = []
    stack = list(children.get(root, []))
    seen = set(stack)
    while stack:
        t = stack.pop()
        out.append(t)
        for c in children.get(t, []):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return out


def depth_from_root(children: dict, root: str, target: str) -> int | None:
    if root == target:
        return 0
    q = [(root, 0)]
    seen = {root}
    while q:
        t, d = q.pop(0)
        for c in children.get(t, []):
            if c == target:
                return d + 1
            if c not in seen:
                seen.add(c)
                q.append((c, d + 1))
    return None


# --- goal_src scan for lexical proximity -----------------------------------

_GC_TEXT_CACHE: dict[str, str] = {}


def goal_src_gc_text(stem: str) -> str:
    """Return concatenated text of goal_src/jakx/**/<stem>.gc files.

    Used only for lexical-proximity tiebreak. Returns '' when no source
    file matches — in which case tiebreak skips.
    """
    if stem in _GC_TEXT_CACHE:
        return _GC_TEXT_CACHE[stem]
    if not GOAL_SRC_JAKX.exists():
        _GC_TEXT_CACHE[stem] = ""
        return ""
    hits = list(GOAL_SRC_JAKX.rglob(f"{stem}.gc"))
    text = ""
    for p in hits:
        try:
            text += p.read_text(errors="replace")
        except Exception:
            pass
    _GC_TEXT_CACHE[stem] = text
    return text


def mentioned_in_source(file_stem: str, type_name: str) -> bool:
    """Cheap substring check: does stem.gc mention type_name as a token?"""
    text = goal_src_gc_text(file_stem)
    if not text:
        return False
    # Word-ish boundaries (GOAL tokens allow many chars, so just check
    # that the name isn't embedded inside another identifier).
    pat = re.compile(r"(?<![\w<>\-!?:\+\*/=])"
                     + re.escape(type_name)
                     + r"(?![\w<>\-!?:\+\*/=])")
    return bool(pat.search(text))


# --- core heuristic --------------------------------------------------------

@dataclass
class SubclassGuess:
    file_stem: str
    fn_key: str
    op_num: int
    load_op: str
    base_reg: str          # MIPS reg name from IR2 (e.g. "v1")
    offset: int
    base_pretype: str      # current (known) pre-type of base reg
    chosen_subclass: str   # the subclass we want to cast base to
    field_name: str        # field that exists at offset in chosen_subclass
    field_type: str        # field's declared type
    subtree_size: int      # number of descendants of base_pretype


def classify_candidate(
    err,
    pretype: str,
    fields: dict,
    parents: dict,
    children: dict,
) -> tuple[SubclassGuess | None, str]:
    """Return (guess, reason).  Reason is a bucket key for stats.

    When guess is None, no emission.  When non-None, reason describes
    which tiebreak path was taken.
    """
    if err.offset <= 0:
        return None, "neg-offset"
    if not is_usable_base_type(pretype):
        return None, f"unusable-base:{pretype[:20]}"
    # Base MUST not already have the field (that's P2's job).
    ft_self = resolve_field_type(fields, parents, pretype, err.offset)
    if ft_self is not None:
        return None, "base-has-field"  # P2 territory

    ds = all_descendants(children, pretype)
    if len(ds) == 0:
        return None, "no-desc"
    if len(ds) > MAX_DESC_SUBTREE:
        return None, f"tree-too-big(>{MAX_DESC_SUBTREE})"

    # Descendants that INTRODUCE the field at this offset (OWN field dict).
    matches: list[tuple[str, tuple[str, str]]] = []
    for d in ds:
        fd = fields.get(d, {})
        if err.offset in fd:
            matches.append((d, fd[err.offset]))
    if not matches:
        return None, "no-match-in-tree"

    expected = LOAD_WIDTH.get(err.load_op)
    width_ok = []
    for d, (fname, ftype) in matches:
        sz = field_byte_size(ftype)
        if expected is None or sz is None or sz == expected:
            width_ok.append((d, (fname, ftype)))
    if not width_ok:
        return None, "width-mismatch"

    matches = width_ok

    # Single match -> winner.
    if len(matches) == 1:
        d, (fname, ftype) = matches[0]
        return SubclassGuess(
            file_stem=err.file_stem,
            fn_key=err.fn_key,
            op_num=err.op_num,
            load_op=err.load_op,
            base_reg=err.base_reg,
            offset=err.offset,
            base_pretype=pretype,
            chosen_subclass=d,
            field_name=fname,
            field_type=ftype,
            subtree_size=len(ds),
        ), "single-match"

    # Multiple. Pick minimum depth in subtree.
    with_depth = [(m, depth_from_root(children, pretype, m[0])) for m in matches]
    min_d = min(d for _, d in with_depth if d is not None)
    at_min = [m for m, d in with_depth if d == min_d]
    if len(at_min) == 1:
        d, (fname, ftype) = at_min[0]
        return SubclassGuess(
            file_stem=err.file_stem, fn_key=err.fn_key, op_num=err.op_num,
            load_op=err.load_op, base_reg=err.base_reg, offset=err.offset,
            base_pretype=pretype, chosen_subclass=d,
            field_name=fname, field_type=ftype, subtree_size=len(ds),
        ), "min-depth-unique"

    # Lexical tiebreak.
    lex = [m for m in at_min if mentioned_in_source(err.file_stem, m[0])]
    if len(lex) == 1:
        d, (fname, ftype) = lex[0]
        return SubclassGuess(
            file_stem=err.file_stem, fn_key=err.fn_key, op_num=err.op_num,
            load_op=err.load_op, base_reg=err.base_reg, offset=err.offset,
            base_pretype=pretype, chosen_subclass=d,
            field_name=fname, field_type=ftype, subtree_size=len(ds),
        ), "lexical-unique"

    return None, "ambiguous"


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
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--batch-size", type=int, default=0)
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--err-slack", type=int, default=0)
    ap.add_argument("--skip-file", default=None)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument(
        "--max-desc", type=int, default=10,
        help=("Skip candidates whose base type has > N descendants "
              "(default 10). Raising this picks up more candidates but "
              "increases false-positive risk."),
    )
    ap.add_argument(
        "--allowed-bases", default=None,
        help=("Comma-separated list of base types to limit emission to "
              "(e.g. 'trsqv'). If unset, all types under --max-desc are "
              "eligible."),
    )
    args = ap.parse_args()

    if args.apply:
        args.dry_run = False

    global MAX_DESC_SUBTREE
    MAX_DESC_SUBTREE = args.max_desc
    allowed_bases = None
    if args.allowed_bases:
        allowed_bases = {s.strip() for s in args.allowed_bases.split(",") if s.strip()}

    decomp_dir = Path(args.decomp_out) if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out not found: {decomp_dir}", file=sys.stderr)
        return 1

    print(f"decomp_out:  {decomp_dir}")
    print(f"type_casts:  {TYPE_CASTS_JAKX.relative_to(ROOT)}")
    print(f"all-types:   {ALL_TYPES.relative_to(ROOT)}")
    print(f"max-desc:    {MAX_DESC_SUBTREE}")
    if allowed_bases:
        print(f"allowed:     {sorted(allowed_bases)}")

    print("Building field index ...", end=" ", flush=True)
    fields, parents = build_field_index(ALL_TYPES)
    children = build_children_index(parents)
    print(f"{len(fields)} types, {sum(len(v) for v in fields.values())} fields")

    print("Loading existing type_casts.jsonc ...", end=" ", flush=True)
    existing = load_jsonc(TYPE_CASTS_JAKX)
    print(f"{len(existing)} keys, {sum(len(v) for v in existing.values())} entries")

    skip_set = _read_skip_set(args.skip_file)
    if skip_set:
        print(f"skip-file: {len(skip_set)} (fn|op|reg) entries to exclude")

    print("Scanning IR2 files ...", end=" ", flush=True)
    files = sorted(decomp_dir.glob("*_ir2.asm"))
    all_errs: list[tuple] = []
    for fp in files:
        all_errs.extend(scan_ir2_file(fp))
    print(f"{len(all_errs)} load errors across {len(files)} files")

    reasons: Counter = Counter()
    guesses: list[SubclassGuess] = []
    for err, pretype in all_errs:
        if pretype is None:
            reasons["no-pretype"] += 1
            continue
        if allowed_bases is not None and pretype not in allowed_bases:
            reasons["not-in-allowed"] += 1
            continue
        g, reason = classify_candidate(err, pretype, fields, parents, children)
        reasons[reason] += 1
        if g is None:
            continue
        # De-dup / skip checks
        if existing_covers(existing, g.fn_key, g.op_num, g.base_reg):
            reasons["already-covered"] += 1
            continue
        skip_key = f"{g.fn_key}|{g.op_num}|{g.base_reg}"
        if skip_key in skip_set:
            reasons["skip-file"] += 1
            continue
        # Never emit a no-op (same type as current pre-type).
        if g.chosen_subclass == g.base_pretype:
            reasons["noop-same-type"] += 1
            continue
        guesses.append(g)

    print("\nBreakdown:")
    print(f"  emitted: {len(guesses)}")
    for k, v in reasons.most_common(30):
        print(f"  {k:30s} {v}")

    if args.stats:
        return 0

    if not guesses:
        print("Nothing to add.")
        return 0

    # Deduplicate
    seen = set()
    unique: list[SubclassGuess] = []
    for g in guesses:
        key = (g.fn_key, g.op_num, g.base_reg)
        if key in seen:
            continue
        seen.add(key)
        unique.append(g)
    if len(unique) < len(guesses):
        print(f"  dedup: {len(guesses)} -> {len(unique)}")
    guesses = unique

    # Apply batch cap (trim while preserving order).
    if args.batch_size > 0:
        guesses = guesses[: args.batch_size]

    proposed: dict[str, list[list]] = {}
    for g in guesses:
        proposed.setdefault(g.fn_key, []).append(
            [g.op_num, g.base_reg, g.chosen_subclass]
        )

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
                print(f"WARN: failed to extend key {fn!r}", file=sys.stderr)
        if brand_new:
            append_new_keys(TYPE_CASTS_JAKX, brand_new)
        return [TYPE_CASTS_JAKX]

    commit_msg = (
        f"fix(jakx/type-casts): ir2-subclass-guess {total} base casts\n\n"
        f"Heuristic: for 'could not figure out load' errors where the base\n"
        f"register's pre-type has no field at the requested offset but a\n"
        f"descendant subclass introduces one, emit a SRC cast upgrading\n"
        f"the base register to that subclass so type propagation resolves\n"
        f"the load itself.\n\n"
        f"Filters: base subtree <= {MAX_DESC_SUBTREE} descendants;\n"
        f"descendant's OWN field must match load width; single-match or\n"
        f"unique-min-depth / unique-lexical tiebreak only.\n\n"
        f"Gated via apply_guard (err_slack={args.err_slack}).\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    print(f"\nApplying {total} entries via apply_guard ...")
    result = run_with_guard(
        do_apply,
        label=f"ir2-subclass-guess/{total}",
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
