#!/usr/bin/env python3
"""load_offset_apply.py — DEPRECATED (cycle 26 kill).

DO NOT USE without first solving register provenance. Cycle 26 evidence:
2-edit batch (game-info skill@108, civilians-killed@324) committed
`bf51b01b5`, dropped offline_test_pass 191→110 (−81). Reverted as
`bda83c2f9`. The (caller-type::method-N, offset) clusters group by
*enclosing function's type*, not by *the actual type of the register
being loaded from* — so adding fields under that assumption produces
wrong GOAL even when jak3 cross-port evidence confirms the field exists
at that offset on that type.

See: memory/feedback_load_offset_lane_killed.md for the full kill writeup.

The defensive filters in this file (size-assert, name-collision, single-
line field-list rejection, forward-ref position check) are reusable
patterns for OTHER deftype-mutating appliers. Keep the file as-is for
those references; just don't run it.

Original docstring follows.
======================================================================

load_offset_apply.py — fact-add applier for "Could not figure out load" patterns.

Pattern: ``;; ERROR: failed type prop at N: Could not figure out load:
(set! REG (l.X (+ REG OFFS)))``  → the decompiler couldn't resolve a field
load on a struct because the deftype lacks a field at OFFS.

This applier:
  1. Reuses load_offset_scan.scan_file() to enumerate struct-shape loads
     from jakx decomp output.
  2. For each (TYPE::method-N, offset) candidate, cross-references jak3's
     all-types.gc: if jak3's TYPE has a field at exactly that offset, the
     edit is a fact-add (real evidence the field exists).
  3. Proposes adding `(<jak3-name> <jak3-type> :offset OFFS)` to jakx's
     deftype, with two safety filters:
       - the proposed field type must be declared in jakx at or before
         the deftype's line (no forward references — see
         sig_passthrough_apply.py's position-aware filter).
       - jakx must not already have a field at OFFS.
  4. Routes the batch through apply_guard (which gates on Δrc / Δerr /
     crash signals) and surfaces Δpass via offline_test_pass.py.

Per G0 (STOP_CONDITIONS.md): the win signal is Δpass, not Δrc. Run
`python3 scripts/jakx_watch/offline_test_pass.py` after a passing batch
and check `.compound_loop/convergence.jsonl` tail for Δpass attribution.
If Δrc moves but Δpass stays flat, this lane is suppress-not-fix and
should be killed.

Usage:
  # Dry-run jakx (default), top-10 candidates
  python3 scripts/jakx_watch/load_offset_apply.py --top 10

  # Apply + commit
  python3 scripts/jakx_watch/load_offset_apply.py --top 10 --apply --commit
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402
from load_offset_scan import scan_file, pick_decomp_dir  # noqa: E402
from sig_passthrough_apply import (  # noqa: E402
    types_declared_at,
    _BUILTIN_TYPES,
    _extract_referents,
    sibling_games_for,
    _load_all_types,
)

GAMES = ("jak1", "jak2", "jak3", "jakx")

RE_DEFTYPE_HEADER = re.compile(r"^\(deftype\s+(\S+)\s+\(")
# Field line within a deftype body. Captures name, type, and offset value
# (either via :offset-assert N or :offset N). Lines that don't match are
# kept as-is.
RE_FIELD_LINE = re.compile(
    r"^(\s*)\((\S+)\s+(.+?)\s*:offset(?:-assert)?\s+(?:#x([0-9a-fA-F]+)|(\d+))[^)]*\)"
)
RE_SIZE_ASSERT = re.compile(
    r":size-assert\s+(?:#x([0-9a-fA-F]+)|(\d+))"
)

# sizeof() in bytes for common scalar field types. Conservative: we only
# size-check fields whose type is in this map; anything else is treated as
# unknown and skipped (prevents unsafe size estimates for compound or
# user-defined types).
SCALAR_SIZE = {
    "int8": 1, "uint8": 1,
    "int16": 1, "uint16": 2,  # int16:1 is wrong but kept conservative
    "int32": 4, "uint32": 4, "float": 4,
    "int64": 8, "uint64": 8, "handle": 8,
    "int128": 16, "uint128": 16,
    "symbol": 4, "basic": 4, "string": 4, "type": 4,
}
# Correct int16 size
SCALAR_SIZE["int16"] = 2


def parse_caller_method(caller: str) -> tuple[str, int] | None:
    """Parse 'TYPE::method-N' → (TYPE, N). Returns None for fn:NAME callers."""
    m = re.match(r"^(\S+)::method-(\d+)$", caller)
    if not m:
        return None
    return (m.group(1), int(m.group(2)))


def find_deftype_block(lines: list[str], type_name: str) -> tuple[int, int] | None:
    """Return (start_line_idx, end_line_idx_exclusive) for `(deftype TYPE ...)`.

    end is the index of the closing `)` line — caller can insert before it.
    """
    start = None
    depth = 0
    for i, line in enumerate(lines):
        if start is None:
            m = RE_DEFTYPE_HEADER.match(line)
            if m and m.group(1) == type_name:
                start = i
                depth = line.count("(") - line.count(")")
                if depth == 0:
                    return (start, i + 1)
            continue
        depth += line.count("(") - line.count(")")
        if depth == 0:
            return (start, i + 1)
    return None


def parse_field_offset(line: str) -> int | None:
    """Extract an :offset[-assert] value from a single field line."""
    m = RE_FIELD_LINE.match(line)
    if not m:
        return None
    if m.group(4):  # hex
        return int(m.group(4), 16)
    return int(m.group(5))


def deftype_field_offsets(lines: list[str], start: int, end: int) -> set[int]:
    """Collect existing field offsets within a deftype block."""
    offsets: set[int] = set()
    in_methods = False
    for i in range(start + 1, end):
        line = lines[i]
        s = line.strip()
        if s.startswith("(:methods") or s.startswith("(:state-methods"):
            in_methods = True
        if in_methods:
            continue
        offs = parse_field_offset(line)
        if offs is not None:
            offsets.add(offs)
    return offsets


def deftype_field_names(lines: list[str], start: int, end: int) -> set[str]:
    """Collect existing field names within a deftype block.

    Same parsing as deftype_field_offsets but pulls the name capture.
    Used to reject cross-port edits whose proposed name already exists
    on the target type at a different offset (cycle 26 vehicle damage-
    factor crash: jak3 had it at offset 452, jakx had it at 692).
    """
    names: set[str] = set()
    in_methods = False
    for i in range(start + 1, end):
        line = lines[i]
        s = line.strip()
        if s.startswith("(:methods") or s.startswith("(:state-methods"):
            in_methods = True
        if in_methods:
            continue
        m = RE_FIELD_LINE.match(line)
        if m:
            names.add(m.group(2))
    return names


def deftype_size_assert(lines: list[str], start: int, end: int) -> int | None:
    """Return :size-assert in bytes for the deftype, or None if not present."""
    for i in range(start + 1, end):
        m = RE_SIZE_ASSERT.search(lines[i])
        if m:
            if m.group(1):
                return int(m.group(1), 16)
            return int(m.group(2))
    return None


def estimate_field_size(field_type: str) -> int | None:
    """Best-effort sizeof() in bytes; None for unknown / compound types.

    Only used for the size-assert safety check — when in doubt, return
    None so the caller errs on the side of skipping the candidate.
    """
    t = field_type.strip()
    return SCALAR_SIZE.get(t)


def find_field_list_close(
    lines: list[str], start: int, end: int,
) -> tuple[int, int, int, bool] | None:
    """Locate the field-list's closing `)` inside a deftype block.

    Returns (open_line_idx, close_line_idx, close_col_idx, is_empty) — the
    line where the field-list opens, the line+column of the closing `)`,
    plus whether the field list is empty (`()` with no fields between
    open and close).

    The field list is the FIRST balanced `(...)` group after the deftype
    header line. Blank lines, line comments (;;), and a string docstring at
    the top of the body are skipped.

    Returns None if structure can't be parsed — caller should skip this
    deftype rather than risk corrupting it.
    """
    field_open_line: int | None = None
    field_open_col: int | None = None
    in_doc = False
    for i in range(start + 1, end):
        line = lines[i]
        stripped = line.lstrip()
        if not stripped:
            continue
        if stripped.startswith(";"):
            continue
        if in_doc:
            if '"' in line:
                in_doc = False
            continue
        if stripped.startswith('"'):
            # Docstring may span lines; check if the closing quote is also here.
            rest = stripped[1:]
            if '"' not in rest:
                in_doc = True
            continue
        if stripped.startswith("("):
            col = line.index("(")
            field_open_line = i
            field_open_col = col
            break
        # Anything else (e.g. :method-count-assert) means no field list ever
        # opened — caller can't insert here without restructuring.
        return None
    if field_open_line is None or field_open_col is None:
        return None
    # Walk from the open paren tracking depth.
    depth = 0
    for li in range(field_open_line, end):
        cur = lines[li]
        col_start = field_open_col if li == field_open_line else 0
        for ci in range(col_start, len(cur)):
            ch = cur[ci]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    is_empty = (
                        li == field_open_line
                        and ci == field_open_col + 1
                    )
                    return (field_open_line, li, ci, is_empty)
    return None


def lookup_sibling_field_at_offset(
    type_name: str, offset: int, sibling_games: list[str],
) -> tuple[str, str, str] | None:
    """Find (field_name, field_type, source_game) at exact offset on sibling type.

    Returns None if no sibling has the type, or the type lacks a field at OFFS,
    or the field is :inline / :dynamic (those are structural; not safe to copy).
    """
    for sg in sibling_games:
        lines = _load_all_types(sg)
        if lines is None:
            continue
        block = find_deftype_block(lines, type_name)
        if block is None:
            continue
        s, e = block
        for i in range(s + 1, e):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith(":") or stripped.startswith("(:methods"):
                break
            offs = parse_field_offset(line)
            if offs != offset:
                continue
            # Reject inline / dynamic fields — they have alignment + sizing
            # implications that don't transfer cleanly.
            if ":inline" in stripped or ":dynamic" in stripped:
                return None
            m = RE_FIELD_LINE.match(line)
            if not m:
                continue
            return (m.group(2), m.group(3).strip(), sg)
    return None


def types_safe_at_line(
    field_type: str, target_game: str, edit_line_idx: int,
) -> bool:
    """All referents of field_type must be either builtins or declared in
    target_game's all-types.gc strictly before edit_line_idx (cycle 24
    forward-ref crash lesson — see sig_passthrough_apply.filter_atoms_by_position)."""
    declared_at = types_declared_at(target_game)
    refs = _extract_referents(field_type)
    for r in refs:
        if r in _BUILTIN_TYPES:
            continue
        if r in declared_at and declared_at[r] < edit_line_idx:
            continue
        return False
    return True


def collect_candidates(decomp_dir: Path) -> dict[tuple[str, int], int]:
    """Return (caller, offset) → count for struct-shape load failures."""
    counts: dict[tuple[str, int], int] = {}
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        for caller, shape, _op, _reg, offs in scan_file(fp):
            if shape != "struct":
                continue
            if "::method-" not in caller:
                continue
            counts[(caller, offs)] = counts.get((caller, offs), 0) + 1
    return counts


def plan_edits(
    candidates: dict[tuple[str, int], int],
    all_types_lines: list[str],
    target_game: str,
    sibling_games: list[str],
) -> list[dict]:
    """For each candidate, decide whether a fact-add edit is possible."""
    plans: list[dict] = []
    # Sort by count desc so the highest-confidence pairs land first.
    sorted_cands = sorted(candidates.items(), key=lambda kv: -kv[1])
    for (caller, offset), count in sorted_cands:
        parsed = parse_caller_method(caller)
        if not parsed:
            continue
        type_name, _method_num = parsed
        block = find_deftype_block(all_types_lines, type_name)
        if block is None:
            continue
        s, e = block
        existing_offsets = deftype_field_offsets(all_types_lines, s, e)
        if offset in existing_offsets:
            continue  # jakx already has a field there — don't disturb it
        sib = lookup_sibling_field_at_offset(type_name, offset, sibling_games)
        if sib is None:
            continue  # no fact-add evidence; skip
        field_name, field_type, source_game = sib
        # Name-collision check: if jakx already declares the same field name
        # at a different offset, the type-load aborts. Skip rather than
        # rename — picking a different name would break code that already
        # references it (and signals jakx's struct genuinely differs).
        if field_name in deftype_field_names(all_types_lines, s, e):
            continue
        flc = find_field_list_close(all_types_lines, s, e)
        if flc is None:
            continue  # weird deftype shape — don't risk it
        open_line, close_line, close_col, is_empty = flc
        # Single-line non-empty field list (e.g. `  ((csm-pad ... 200))`) —
        # multi-line insert before close_line would put the new line
        # outside the deftype. Skip; would need character-position editing.
        if not is_empty and open_line == close_line:
            continue
        if not types_safe_at_line(field_type, target_game, close_line):
            continue  # forward-ref would crash type-load
        # Size-assert safety: adding a field at OFFS extends the struct
        # to OFFS + sizeof(field). If that exceeds the declared
        # :size-assert, the type-load aborts (cycle 26 prim-strip
        # crash: size-assert=4 vs new field at offset 84). Only allow
        # the edit if we can prove the new end fits.
        size_assert = deftype_size_assert(all_types_lines, s, e)
        fsize = estimate_field_size(field_type)
        if size_assert is not None:
            if fsize is None:
                continue  # unknown sizeof; don't risk overrunning size-assert
            if offset + fsize > size_assert:
                continue  # would extend type beyond declared size
        plans.append({
            "caller": caller,
            "type": type_name,
            "offset": offset,
            "count": count,
            "deftype_start": s,
            "close_line": close_line,
            "close_col": close_col,
            "is_empty": is_empty,
            "field_name": field_name,
            "field_type": field_type,
            "source_game": source_game,
        })
    return plans


def apply_plan_to_lines(plans: list[dict], lines: list[str]) -> list[str]:
    """Apply a list of plans to a copy of `lines`, returning the new lines.

    Plans are applied bottom-up (highest close_line first) so earlier line
    indices stay stable. For an empty field list, the closing `)` is
    replaced in-place; for a populated list, a new field line is inserted
    before the closing `)`.
    """
    out = list(lines)
    by_close = sorted(plans, key=lambda p: -p["close_line"])
    for p in by_close:
        li = p["close_line"]
        ci = p["close_col"]
        line = out[li]
        new_field_text = (
            f"({p['field_name']} {p['field_type']} :offset {p['offset']})"
        )
        if p["is_empty"]:
            # Replace `()` (the two characters at ci-1 and ci) with `((NEW))`.
            # ci points to the `)`. The matching `(` is at ci-1.
            assert line[ci - 1] == "(" and line[ci] == ")", (
                f"is_empty plan but no `()` at line {li} col {ci}: {line!r}"
            )
            replacement = f"({new_field_text})"
            out[li] = line[: ci - 1] + replacement + line[ci + 1 :]
        else:
            # Insert a new line BEFORE the closing `)` line. Indent matches
            # close_col (existing field `(` lines up with the field-list's
            # closing `)` at the same column).
            indent = " " * ci
            out.insert(li, f"{indent}{new_field_text}\n")
    return out


def main() -> int:
    print(
        "ERROR: load_offset_apply is DEPRECATED — cycle 26 commit dropped\n"
        "       offline_test_pass by 81 files. See module docstring + memory\n"
        "       feedback_load_offset_lane_killed.md before re-enabling.\n"
        "       Pass --force-deprecated to bypass this check.",
        file=sys.stderr,
    )
    if "--force-deprecated" not in sys.argv:
        return 2
    sys.argv.remove("--force-deprecated")
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--game", choices=GAMES, default="jakx",
                    help="Target game (default jakx)")
    ap.add_argument("--top", type=int, default=10,
                    help="Apply top-N fact-add candidates per batch")
    ap.add_argument("--apply", action="store_true",
                    help="Apply the edits (default: dry-run)")
    ap.add_argument("--commit", action="store_true",
                    help="Auto-commit if guard passes")
    ap.add_argument("--err-slack", type=int, default=10)
    ap.add_argument("--decomp-out", default=None)
    args = ap.parse_args()

    all_types_path = ROOT / "decompiler" / "config" / args.game / "all-types.gc"
    decomp_dir = (
        Path(args.decomp_out) if args.decomp_out else pick_decomp_dir()
    )
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out not found: {decomp_dir}", file=sys.stderr)
        return 1

    print(f"game:        {args.game}")
    print(f"decomp_out:  {decomp_dir}")
    print(f"all-types:   {all_types_path.relative_to(ROOT)}")

    print("Collecting candidates ...", end=" ", flush=True)
    cands = collect_candidates(decomp_dir)
    print(f"{len(cands)} unique (TYPE::method-N, offset) pairs")

    print("Planning edits ...", end=" ", flush=True)
    all_types_lines = all_types_path.read_text(errors="replace").splitlines(keepends=True)
    plans_all = plan_edits(
        cands,
        [l.rstrip("\n") for l in all_types_lines],
        target_game=args.game,
        sibling_games=sibling_games_for(args.game),
    )
    print(f"{len(plans_all)} fact-add candidates (sibling field at exact offset)")

    plans = plans_all[: args.top]
    print(f"\nProposing {len(plans)} edits:")
    for p in plans[:20]:
        print(
            f"  [{p['source_game']}] {p['type']} @ offset {p['offset']:>4d}  "
            f"+ ({p['field_name']} {p['field_type']})"
        )
    if len(plans) > 20:
        print(f"  ... ({len(plans) - 20} more)")

    if not plans:
        print("\nNothing to apply.")
        return 0

    if not args.apply:
        print("\n--dry-run: pass --apply to write & gate.")
        return 0

    # --- apply ---
    edited_types = {p["type"] for p in plans}

    def do_apply() -> list[Path]:
        cur_lines = all_types_path.read_text(errors="replace").splitlines(keepends=True)
        new_lines = apply_plan_to_lines(plans, cur_lines)
        all_types_path.write_text("".join(new_lines))
        return [all_types_path]

    commit_msg = (
        f"fix({args.game}/all-types): load_offset apply {len(plans)} fact-adds\n\n"
        f"Pattern: ';; ERROR: Could not figure out load: (l.X (+ REG OFFS))'.\n"
        f"For each (TYPE::method-N, offset) cluster, the field at that offset\n"
        f"is verified to exist on the same-named TYPE in jak3's all-types.gc.\n"
        f"Field name + type are copied verbatim — concrete cross-game evidence,\n"
        f"not a placeholder.\n\n"
        f"Per G0 (STOP_CONDITIONS.md): designed as fact-add, not suppress-not-fix.\n"
        f"Validation: run scripts/jakx_watch/offline_test_pass.py after this lands\n"
        f"to read Δpass; flat Δpass with positive Δrc means kill the lane.\n\n"
        f"Gated via apply_guard --game {args.game} (err_slack={args.err_slack}).\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    print(f"\nApplying {len(plans)} edits via apply_guard --game {args.game} ...")
    result = run_with_guard(
        do_apply,
        label=f"load-offset/{args.game}/{len(plans)}",
        err_slack=args.err_slack,
        warn_slack=max(5, args.err_slack),
        commit_on_pass=args.commit,
        commit_message=commit_msg,
        game=args.game,
        edited_types=edited_types,
    )
    if not result.passed:
        print(f"FAIL: {result.reason}", file=sys.stderr)
        return 1

    print(f"PASS: Δerr={result.delta_err:+d}  Δwarn={result.delta_warn:+d}")
    if args.commit and result.commit_sha:
        print(f"  committed as {result.commit_sha}")
        print(
            "\nNEXT: refresh pass numbers + read Δpass attribution:\n"
            "  python3 scripts/jakx_watch/offline_test_pass.py\n"
            "  tail -1 .compound_loop/convergence.jsonl"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
