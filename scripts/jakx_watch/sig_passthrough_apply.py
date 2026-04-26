#!/usr/bin/env python3
"""sig_passthrough_apply.py — auto-apply passthrough-arg signature fixes.

Pattern: ``;; ERROR: Function may read a register that is not set: aN``

When a method's body reads register aN but the declared signature only
has fewer params, the decompiler can't type-prop the read. The fix:
extend the signature with extra params up to aN.

This applier:
  1. Reuses sig_passthrough_scan.scan_file() to enumerate candidates
  2. For each candidate with a parseable signature, computes the
     missing param count and the proposed new signature line
  3. Optionally cross-ports the new param types from the matching
     jak3 method (default), else uses ``object`` placeholders
  4. Edits all-types.gc in-place, batches by ``--top N``
  5. Routes through apply_guard for auto-revert on regression

Usage:
  # Dry-run jakx (default)
  python3 scripts/jakx_watch/sig_passthrough_apply.py --top 30

  # Apply jakx batch
  python3 scripts/jakx_watch/sig_passthrough_apply.py --top 30 --apply --commit

  # jak2 / jak3
  python3 scripts/jakx_watch/sig_passthrough_apply.py --game jak3 --top 20 --apply --commit
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402
from sig_passthrough_scan import (  # noqa: E402
    scan_file,
    ARG_REGS,
)

GAMES = ("jak1", "jak2", "jak3", "jakx")


def paths_for(game: str) -> dict:
    cfg_dir = ROOT / "decompiler" / "config" / game
    if game == "jakx":
        decomp_primary = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
    else:
        decomp_primary = ROOT / f".{game}_watch" / "decomp_out" / game
    decomp_fallback = ROOT / "decompiler_out" / game
    return {
        "game": game,
        "decomp_primary": decomp_primary,
        "decomp_fallback": decomp_fallback,
        "all_types": cfg_dir / "all-types.gc",
    }


def pick_decomp_dir(cfg: dict) -> Path:
    if cfg["decomp_primary"].exists():
        return cfg["decomp_primary"]
    return cfg["decomp_fallback"]


# ---------------------------------------------------------------------------
# Signature edit
# ---------------------------------------------------------------------------

# Method declaration line, e.g.:
#   (foo-method-12 (_type_ int) symbol) ;; 12
# Captures: name, params (everything inside _type_'s parens after _type_),
#           ret type, comment tail.
RE_METHOD_LINE = re.compile(
    r"^(\s*\()(\S+)\s+\(_type_(?P<params>[^)]*)\)\s*(?P<ret>[^)]*?)\)(?P<tail>.*)$"
)
RE_DEFTYPE_HEADER = re.compile(r"^\(deftype\s+(\S+)\s+\(")


def parse_func_key(func: str) -> tuple[str | None, int | None, str | None]:
    """Split '(method N TYPE)' or '(new N TYPE)' into (kind, n, type).
    Returns (None, None, name) for plain function references.
    """
    m = re.match(r"^\((method|new)\s+(\d+)\s+(\S+)\)\s*$", func)
    if m:
        return (m.group(1), int(m.group(2)), m.group(3))
    return (None, None, func.strip())


def split_param_atoms(params_text: str) -> list[str]:
    """Split a method's _type_ param list into atoms.

    The _type_ self-reference is OUTSIDE this function — params_text starts
    AFTER ``_type_`` and ends BEFORE the closing paren of (_type_ ...).
    Atoms can be plain (``int``) or sexpr (``(pointer X)``).
    """
    out: list[str] = []
    s = params_text.strip()
    i = 0
    n = len(s)
    while i < n:
        # skip whitespace
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        if s[i] == "(":
            depth = 0
            start = i
            while i < n:
                if s[i] == "(":
                    depth += 1
                elif s[i] == ")":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            out.append(s[start:i])
        else:
            start = i
            while i < n and not s[i].isspace() and s[i] not in "()":
                i += 1
            tok = s[start:i]
            if tok:
                out.append(tok)
    return out


def find_method_in_deftype(
    all_types: list[str],
    type_name: str,
    method_num: int,
) -> int | None:
    """Return the 0-based line index of the method declaration, or None.

    Scans for ``(deftype TYPE_NAME (...)`` then walks forward looking for
    a method line whose trailing comment matches `;; <method_num>`. We
    stop on the next deftype header.
    """
    in_target = False
    for idx, line in enumerate(all_types):
        if not in_target:
            m = RE_DEFTYPE_HEADER.match(line)
            if m and m.group(1) == type_name:
                in_target = True
            continue
        # Stop at next deftype
        if line.startswith("(deftype "):
            return None
        # Parse method line
        m = RE_METHOD_LINE.match(line)
        if m:
            tail = m.group("tail")
            tm = re.search(r";;\s*(\d+)\b", tail)
            if tm and int(tm.group(1)) == method_num:
                return idx
    return None


def find_function_def_extern(all_types: list[str], func_name: str) -> int | None:
    """Find ``(define-extern <func> (function ARGS RET))`` line index."""
    pat = re.compile(
        r"^\(define-extern\s+" + re.escape(func_name) + r"\s+\(function\s+"
    )
    for idx, line in enumerate(all_types):
        if pat.match(line):
            return idx
    return None


def build_new_method_line(
    line: str,
    n_params_needed: int,
    fillers: list[str] | None = None,
) -> tuple[str, int] | None:
    """Return (new_line, n_added) if change needed, else None.

    n_params_needed = the count of *non-this* params the method must have
    (i.e. how many slots after _type_).
    """
    m = RE_METHOD_LINE.match(line)
    if not m:
        return None
    params_atoms = split_param_atoms(m.group("params"))
    n_added = n_params_needed - len(params_atoms)
    if n_added <= 0:
        return None
    if fillers is None:
        fillers = ["object"] * n_added
    elif len(fillers) < n_added:
        fillers = fillers + ["object"] * (n_added - len(fillers))
    fillers = fillers[:n_added]
    new_atoms = params_atoms + fillers
    new_params = " " + " ".join(new_atoms)
    new_inner = "_type_" + new_params
    # Reconstruct: lead "(NAME " + "(" + new_inner + ") " + ret + ")" + tail
    indent_paren = m.group(1)
    name = m.group(2)
    ret = m.group("ret").strip()
    tail = m.group("tail")
    new_line = f"{indent_paren}{name} ({new_inner}) {ret}){tail}"
    return (new_line, n_added)


def build_new_extern_line(
    line: str, n_params_needed: int, fillers: list[str] | None = None,
) -> tuple[str, int] | None:
    """Add params to a (define-extern X (function ARGS RET)) line."""
    m = re.match(
        r"^(\(define-extern\s+\S+\s+\(function)(?P<args>[^()]*)\)\)$",
        line,
    )
    if not m:
        return None
    args_atoms = split_param_atoms(m.group("args"))
    if not args_atoms:
        return None
    # Last atom is the return type; rest are params.
    ret = args_atoms[-1]
    params = args_atoms[:-1]
    n_added = n_params_needed - len(params)
    if n_added <= 0:
        return None
    if fillers is None:
        fillers = ["object"] * n_added
    fillers = (fillers + ["object"] * n_added)[:n_added]
    new_args = params + fillers + [ret]
    new_line = m.group(1) + " " + " ".join(new_args) + "))"
    return (new_line, n_added)


# ---------------------------------------------------------------------------
# Cross-port type-guesser
# ---------------------------------------------------------------------------
# Goal: replace plain `object` placeholders with real param types when a
# sibling game (jak2/jak3) declares the same method on a same-named type.
# Exact-name match only — no fuzzy logic. Whatever doesn't match falls back
# to `object`.

# Cache of (game → list[str] of all-types.gc lines) so we don't re-read
# the multi-megabyte file once per candidate.
_ALL_TYPES_CACHE: dict[str, list[str]] = {}


def _load_all_types(game: str) -> list[str] | None:
    if game in _ALL_TYPES_CACHE:
        return _ALL_TYPES_CACHE[game] or None
    path = ROOT / "decompiler" / "config" / game / "all-types.gc"
    if not path.exists():
        _ALL_TYPES_CACHE[game] = []
        return None
    lines = path.read_text(errors="replace").splitlines()
    _ALL_TYPES_CACHE[game] = lines
    return lines


def lookup_sibling_method_params(
    type_name: str, method_num: int, sibling_games: list[str],
) -> list[str] | None:
    """Look up (method N TYPE) in each sibling game's all-types.gc.

    Returns the non-this param atoms from the first sibling that has it,
    or None if no sibling has the method. Sibling order is priority order.
    """
    for sg in sibling_games:
        lines = _load_all_types(sg)
        if lines is None:
            continue
        idx = find_method_in_deftype(lines, type_name, method_num)
        if idx is None:
            continue
        m = RE_METHOD_LINE.match(lines[idx])
        if not m:
            continue
        atoms = split_param_atoms(m.group("params"))
        return atoms
    return None


def lookup_sibling_extern_params(
    func_name: str, sibling_games: list[str],
) -> list[str] | None:
    """Look up (define-extern FUNC (function ARGS RET)) in each sibling.

    Returns ARGS (excluding RET). None if not found.
    """
    for sg in sibling_games:
        lines = _load_all_types(sg)
        if lines is None:
            continue
        idx = find_function_def_extern(lines, func_name)
        if idx is None:
            continue
        m = re.match(
            r"^(\(define-extern\s+\S+\s+\(function)(?P<args>[^()]*)\)\)$",
            lines[idx].rstrip("\n"),
        )
        if not m:
            continue
        atoms = split_param_atoms(m.group("args"))
        if len(atoms) < 1:
            continue
        return atoms[:-1]  # drop return type
    return None


def sibling_games_for(game: str) -> list[str]:
    """Priority order: closest-relative first.

    jakx ← jak3 ← jak2 ← jak1.  jak3 ← jak2 ← jak1.  etc.
    """
    chain = ["jakx", "jak3", "jak2", "jak1"]
    if game not in chain:
        return []
    i = chain.index(game)
    return chain[i + 1:]


# GOAL builtin types — always considered "present" (no deftype needed).
# Conservative set; missing entries just fall back to `object` filler.
_BUILTIN_TYPES = frozenset({
    "object", "structure", "basic", "symbol", "pair", "type",
    "int", "uint", "int8", "uint8", "int16", "uint16",
    "int32", "uint32", "int64", "uint64", "int128", "uint128",
    "float", "vu-function", "string", "vector", "vector4w",
    "matrix", "quaternion", "function",
    "array", "pointer", "inline-array",
    "kheap", "process", "handle", "none", "_type_",
    "boxed-array", "stack-frame",
    "qword", "uint8q", "binteger", "integer-type",
})

# Pattern for compound type expressions like (pointer X) or (array uint8).
# Returns just the base type name(s) referenced (excluding the compound wrapper).
_RE_COMPOUND_TYPE_REF = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_\-?!*]*)\b")


def _extract_referents(atom: str) -> set[str]:
    """Extract referent type names from a param atom.

    `int` → {int}
    `(pointer connection-minimap)` → {pointer, connection-minimap}
    `(array uint8)` → {array, uint8}
    """
    return set(_RE_COMPOUND_TYPE_REF.findall(atom))


def types_declared_at(game: str) -> dict[str, int]:
    """Return name → line_index for the FIRST `(deftype NAME ...)` line.

    Cached. Used for forward-reference detection: a type is only
    "present at line K" if its deftype line index is < K.

    Skips deftypes inside `#|...|#` block comments — those aren't
    visible to the type loader. Detection is conservative (line-by-line
    scan); nested `#|` blocks would defeat it but jakx all-types.gc
    doesn't use them.
    """
    cache_attr = f"_types_at_{game}"
    if hasattr(types_declared_at, cache_attr):
        return getattr(types_declared_at, cache_attr)
    lines = _load_all_types(game) or []
    declared: dict[str, int] = {}
    in_comment = False
    for i, line in enumerate(lines):
        if in_comment:
            if "|#" in line:
                in_comment = False
            continue
        if line.lstrip().startswith("#|"):
            if "|#" not in line[line.index("#|") + 2:]:
                in_comment = True
            continue
        m = re.match(r"^\(deftype\s+([a-zA-Z_][a-zA-Z0-9_\-?!*]*)\b", line)
        if m and m.group(1) not in declared:
            declared[m.group(1)] = i
    setattr(types_declared_at, cache_attr, declared)
    return declared


def filter_atoms_by_position(
    atoms: list[str], game: str, edit_line_idx: int,
) -> list[str]:
    """Replace any atom referencing a not-yet-declared type with `object`.

    Considers a type "available at edit_line_idx" if either:
      - it's a GOAL builtin (always available), or
      - it has a `(deftype NAME ...)` line at index < edit_line_idx in
        the target game's all-types.gc.

    Forward references crash type-load (see cycle 24: nav-mesh-editable
    referenced by nav-mesh-poly-method-10 but declared 50 lines after).
    """
    declared_at = types_declared_at(game)
    filtered: list[str] = []
    for atom in atoms:
        refs = _extract_referents(atom)
        ok = True
        for r in refs:
            if r in _BUILTIN_TYPES:
                continue
            if r in declared_at and declared_at[r] < edit_line_idx:
                continue
            ok = False
            break
        filtered.append(atom if ok else "object")
    return filtered


# ---------------------------------------------------------------------------
# Candidate planning
# ---------------------------------------------------------------------------

def collect_candidates(decomp_dir: Path) -> list[dict]:
    """Run sig_passthrough_scan.scan_file across decomp_dir, dedup."""
    files = sorted(decomp_dir.glob("*_ir2.asm"))
    raw: list[dict] = []
    for fp in files:
        raw.extend(scan_file(fp))
    seen: dict[tuple[str, str], dict] = {}
    for c in raw:
        key = (c["function"], c["missing_reg"])
        if key not in seen or seen[key]["min_params_needed"] < c["min_params_needed"]:
            seen[key] = c
    return list(seen.values())


def plan_edits(
    candidates: list[dict],
    all_types_lines: list[str],
    skip_no_sig: bool = True,
    sibling_games: list[str] | None = None,
    target_game: str | None = None,
) -> list[dict]:
    """For each candidate, compute the (line_index, new_line, ...) change.

    sibling_games:
        If non-empty, look up missing param types from these games' all-types.gc
        (priority order). Falls back to `object` for params not found.
        If empty/None, all fillers are `object` (legacy behavior).
    target_game:
        Required when sibling_games is non-empty. Sibling param atoms are
        filtered against this game's declared types — atoms referencing
        types missing from the target are replaced with `object` to avoid
        crashing decomp's type-load (cycle 24 evidence: `minimap-trail`
        from jak3's minimap-method-11 isn't declared in jakx).
    """
    if sibling_games is None:
        sibling_games = []
    plans: list[dict] = []
    for c in candidates:
        kind, mnum, name = parse_func_key(c["function"])
        if kind in ("method", "new"):
            idx = find_method_in_deftype(all_types_lines, name, mnum)
            if idx is None:
                if skip_no_sig:
                    continue
                continue
            fillers = None
            sibling_match = False
            if sibling_games:
                sib = lookup_sibling_method_params(name, mnum, sibling_games)
                if sib is not None:
                    # Existing local atoms: derive from the line itself so we
                    # only fill the *new* slots beyond what's already there.
                    m = RE_METHOD_LINE.match(all_types_lines[idx])
                    local_atoms = split_param_atoms(m.group("params")) if m else []
                    n_have = len(local_atoms)
                    needed = c["min_params_needed"]
                    # Use sibling atoms in positions [n_have .. needed)
                    if len(sib) >= needed:
                        fillers = sib[n_have:needed]
                        sibling_match = True
                    elif len(sib) > n_have:
                        # partial: use what we can, pad rest with object
                        fillers = sib[n_have:] + ["object"] * (needed - len(sib))
                        sibling_match = True
                    if fillers and target_game is not None:
                        fillers = filter_atoms_by_position(fillers, target_game, idx)
            built = build_new_method_line(
                all_types_lines[idx], c["min_params_needed"], fillers=fillers
            )
            if not built:
                continue
            new_line, n_added = built
            plans.append({
                **c,
                "kind": "method",
                "line_idx": idx,
                "old_line": all_types_lines[idx],
                "new_line": new_line,
                "n_added": n_added,
                "sibling_match": sibling_match,
            })
        else:
            # plain function: try define-extern
            idx = find_function_def_extern(all_types_lines, name)
            if idx is None:
                continue
            fillers = None
            sibling_match = False
            if sibling_games:
                sib = lookup_sibling_extern_params(name, sibling_games)
                if sib is not None:
                    line = all_types_lines[idx].rstrip("\n")
                    mm = re.match(
                        r"^(\(define-extern\s+\S+\s+\(function)(?P<args>[^()]*)\)\)$",
                        line,
                    )
                    local_atoms = split_param_atoms(mm.group("args"))[:-1] if mm else []
                    n_have = len(local_atoms)
                    needed = c["min_params_needed"]
                    if len(sib) >= needed:
                        fillers = sib[n_have:needed]
                        sibling_match = True
                    elif len(sib) > n_have:
                        fillers = sib[n_have:] + ["object"] * (needed - len(sib))
                        sibling_match = True
                    if fillers and target_game is not None:
                        fillers = filter_atoms_by_position(fillers, target_game, idx)
            built = build_new_extern_line(
                all_types_lines[idx], c["min_params_needed"], fillers=fillers,
            )
            if not built:
                continue
            new_line, n_added = built
            plans.append({
                **c,
                "kind": "extern",
                "line_idx": idx,
                "old_line": all_types_lines[idx],
                "new_line": new_line,
                "n_added": n_added,
                "sibling_match": sibling_match,
            })
    # Sort by file (deterministic) then by min_params_needed desc
    plans.sort(key=lambda p: (-p["min_params_needed"], p["function"]))
    # Dedup by line_idx (multiple candidates may converge on same method
    # if scan picked up multiple a-regs). Keep the one with most params.
    by_idx: dict[int, dict] = {}
    for p in plans:
        i = p["line_idx"]
        if i not in by_idx or p["min_params_needed"] > by_idx[i]["min_params_needed"]:
            by_idx[i] = p
    return list(by_idx.values())


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--game", choices=GAMES, default="jakx")
    ap.add_argument("--top", type=int, default=20,
                    help="Apply top-N candidates per batch (default 20)")
    ap.add_argument("--apply", action="store_true",
                    help="Apply the edit (default: dry-run)")
    ap.add_argument("--commit", action="store_true",
                    help="Auto-commit if guard passes")
    ap.add_argument("--err-slack", type=int, default=0)
    ap.add_argument("--decomp-out", default=None)
    ap.add_argument("--no-cross-port", action="store_true",
                    help="Disable sibling-game param lookup (fallback: `object`)")
    ap.add_argument("--cross-port-only", action="store_true",
                    help="Only apply edits where a sibling-game signature was found")
    args = ap.parse_args()

    cfg = paths_for(args.game)
    decomp_dir = Path(args.decomp_out) if args.decomp_out else pick_decomp_dir(cfg)
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out not found: {decomp_dir}", file=sys.stderr)
        return 1

    all_types_path = cfg["all_types"]

    print(f"game:        {args.game}")
    print(f"decomp_out:  {decomp_dir}")
    print(f"all-types:   {all_types_path.relative_to(ROOT)}")

    print("Collecting candidates ...", end=" ", flush=True)
    cands = collect_candidates(decomp_dir)
    print(f"{len(cands)} unique (function, reg) pairs")

    print("Planning edits ...", end=" ", flush=True)
    all_types_lines = all_types_path.read_text(errors="replace").splitlines(keepends=True)
    # build_field_index expects lines without keepends in place; preserve newlines
    # for write-out fidelity.
    siblings = [] if args.no_cross_port else sibling_games_for(args.game)
    plans_all = plan_edits(
        cands, [l.rstrip("\n") for l in all_types_lines],
        sibling_games=siblings, target_game=args.game,
    )
    n_with_sibling = sum(1 for p in plans_all if p.get("sibling_match"))
    print(f"{len(plans_all)} fixable ({n_with_sibling} with sibling sig)")

    if args.cross_port_only:
        plans_all = [p for p in plans_all if p.get("sibling_match")]
        print(f"--cross-port-only: filtered to {len(plans_all)}")

    plans = plans_all[: args.top]
    print(f"\nProposing {len(plans)} edits:")
    for p in plans[:30]:
        tag = "[sib]" if p.get("sibling_match") else "[obj]"
        print(f"  {tag} {p['function']}  +{p['n_added']} (need a{ARG_REGS.index(p['missing_reg'])})")
    if len(plans) > 30:
        print(f"  ... ({len(plans) - 30} more)")

    if not plans:
        print("\nNothing to apply.")
        return 0

    if not args.apply:
        print("\n--dry-run: pass --apply to write & gate.")
        return 0

    # --- apply ---
    def do_apply() -> list[Path]:
        # Re-read fresh (in case anything changed since planning)
        cur_lines = all_types_path.read_text(errors="replace").splitlines(keepends=True)
        for p in plans:
            cur_lines[p["line_idx"]] = (
                p["new_line"] + ("\n" if not p["new_line"].endswith("\n") else "")
            )
        all_types_path.write_text("".join(cur_lines))
        return [all_types_path]

    commit_msg = (
        f"fix({args.game}/all-types): sig_passthrough apply {len(plans)} methods\n\n"
        f"Pattern: 'Function may read a register that is not set: aN'.\n"
        f"Adds missing param slots (typed `object`) to under-declared\n"
        f"method signatures so type-prop can resolve passthrough reads.\n\n"
        f"Gated via apply_guard --game {args.game} (err_slack={args.err_slack}).\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    print(f"\nApplying {len(plans)} edits via apply_guard --game {args.game} ...")
    result = run_with_guard(
        do_apply,
        label=f"sig-passthrough/{args.game}/{len(plans)}",
        err_slack=args.err_slack,
        warn_slack=max(5, args.err_slack),
        commit_on_pass=args.commit,
        commit_message=commit_msg,
        game=args.game,
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
