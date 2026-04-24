#!/usr/bin/env python3
"""Emit type_casts.jsonc entries using IR2 pre-type annotations.

Heuristic: `ir2-prectype`.

For each "Could not figure out load" error in IR2 output where the base
register already has a known type annotation ``[BASE: TYPE ]`` on the
same asm line as the load, look up the field type at that offset in
``all-types.gc`` and emit a type_cast entry for the DESTINATION register.
This is materially more reliable than porting by (function, op, reg)
from jak3: op numbers drift with basic-block reordering but the
pre-type annotation is computed in-place for the current decomp, and
casting the DST (like ``inspect_to_type_casts.py`` does) informs the
decompiler of the load result directly.

The applier uses ``apply_guard`` to gate every write. Bad entries veto
automatically. ``--skip-file`` support lets the drain loop exclude
entries that happen to decompile into a crash or regression.

Example IR2 asm line::

    lw s2, 4(gp)    ;; [ 19] (set! s2-0 (l.w (+ a0-0 4))) \
                    [gp: fact-info ] -> [s2: <uninitialized> ]

The error block at the top of the method reports::

    ;; ERROR: failed type prop at 19: Could not figure out load: \
      (set! s2 (l.w (+ gp 4)))

Together they tell us: at op 19 gp is ``fact-info``; fact-info's field
at offset 4 is ``process``. We emit ``[19, "s2", "process"]`` into
type_casts.jsonc for the enclosing method, telling the decompiler the
load result holds ``process``. The load then resolves.
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
TYPE_CASTS_JAKX = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "type_casts.jsonc"
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"


# --- all-types.gc parsing (robust to compound field types) ------------------

_ATOM = r"[\w<>\-!?:\+\*/=]+"
RE_DEFTYPE = re.compile(r"^\(deftype\s+(" + _ATOM + r")\s+\((" + _ATOM + r")\)")

# A field line: (name TYPE [...anything...] :offset[-assert] N ...)
# TYPE is either an atom OR a balanced (...) up to 3 levels deep.
# We build a sexpr-aware matcher by first capturing the whole field paren group.
RE_FIELD_LINE_PAREN = re.compile(
    r"^\s*\(+\s*(" + _ATOM + r")\s+"
)

# Opaque types where a cast of the load dst is meaningless (base is the
# structure, but the byte at offset is a filler/pad that has no declared
# field type that's worth hinting).
_OPAQUE_FIELD_TYPES = {
    "uint8", "int8", "uint16", "int16", "uint32", "int32", "uint64", "int64",
}

# Base pre-types we consider unusable for field lookup (too generic / not a
# real struct whose fields are in all-types).
_UNUSABLE_BASE_TYPES = {
    "object", "none", "basic", "structure",
    "int", "uint", "float", "symbol", "string",
    "<uninitialized>",
}


def _extract_sexpr(text: str, start: int) -> tuple[str, int]:
    """Given text[start] is '(', return (sexpr_str, index_after_close).
    Balances parens; crude but works for our all-types content."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1], i + 1
        i += 1
    return text[start:], len(text)


def _next_token(text: str, start: int) -> tuple[str, int]:
    """Read next whitespace-delimited token (or sexpr) starting at start.
    Returns (token_str, index_after_token). Token may be '(...)' compound.
    """
    # Skip whitespace
    i = start
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text):
        return "", i
    if text[i] == "(":
        return _extract_sexpr(text, i)
    # Plain atom: read until whitespace or closing paren
    j = i
    while j < len(text) and not text[j].isspace() and text[j] not in "()":
        j += 1
    return text[i:j], j


def _parse_field_line(line: str) -> tuple[str, str, int] | None:
    """Parse a field line into (name, type, offset), or None if not a field.

    Expected form within a deftype body::

        (NAME  TYPE  [:flag ...]  :offset[-assert] N [...])

    TYPE may be an atom or a compound S-expression.
    """
    # Find the opening paren of the field (there may be multiple opening parens
    # on the first field line).
    i = 0
    n = len(line)
    while i < n and line[i].isspace():
        i += 1
    if i >= n or line[i] != "(":
        return None
    # Skip leading parens until we hit the field-name paren (skip '(' and another '(' if multi-open)
    # Simpler: greedily skip '(' chars
    while i < n and line[i] == "(":
        i += 1
    # Now read name
    name_tok, i = _next_token(line, i)
    if not name_tok or name_tok.startswith(":") or not re.match(r"^" + _ATOM + r"$", name_tok):
        return None
    # Read type
    type_tok, i = _next_token(line, i)
    if not type_tok:
        return None
    # Find :offset[-assert]
    m = re.search(r":offset(?:-assert)?\s+(\d+)", line[i:])
    if not m:
        return None
    try:
        offset = int(m.group(1))
    except ValueError:
        return None
    return (name_tok, type_tok, offset)


def build_field_index(all_types_path: Path) -> tuple[dict, dict]:
    """Parse all-types.gc. Returns (fields, parents)."""
    fields: dict[str, dict[int, tuple[str, str]]] = {}
    parents: dict[str, str] = {}

    lines = all_types_path.read_text(errors="replace").splitlines()
    in_block_comment = False
    current_type: str | None = None
    in_fields = False
    seen_fields_open = False

    for line in lines:
        if not in_block_comment and "#|" in line:
            in_block_comment = True
        if in_block_comment:
            if "|#" in line:
                in_block_comment = False
            continue
        stripped = line.lstrip()
        if stripped.startswith(";;") or stripped.startswith(";"):
            continue

        dm = RE_DEFTYPE.match(stripped)
        if dm:
            current_type = dm.group(1)
            parents[current_type] = dm.group(2)
            fields.setdefault(current_type, {})
            in_fields = False
            seen_fields_open = False
            continue

        if current_type is None:
            continue

        # End-of-deftype markers reset our state.
        s = stripped
        if (s.startswith(":methods") or s.startswith(":size")
                or s.startswith(":flag") or s.startswith(":method-count")
                or s.startswith(":no-runtime-type")
                or s.startswith("(:methods") or s.startswith("(:state-methods")):
            in_fields = False
            # The deftype may still have more, don't reset current_type yet
            continue

        # Try parsing this line as a field
        parsed = _parse_field_line(line)
        if parsed:
            fname, ftype, foff = parsed
            # Don't treat keyword-style lines or out-of-range offsets as fields
            if fname in (":methods", ":size-assert", ":flag-assert", ":method-count-assert",
                         ":no-runtime-type"):
                continue
            if foff < 0 or foff > 65536:
                continue
            # Don't overwrite existing entries at same offset (first win).
            fields[current_type].setdefault(foff, (fname, ftype))

    return fields, parents


def resolve_field_type(
    fields: dict,
    parents: dict,
    type_name: str,
    offset: int,
    depth: int = 0,
    skip_opaque: bool = False,
) -> str | None:
    """Walk inheritance chain; return field type at offset or None.

    When ``skip_opaque`` is True, return None for uint8/int16/etc. fields —
    useful for inspect-method prints where ``uint32`` isn't a meaningful cast.
    For general type-prop we want those cast targets: a load of a uint32
    field resolves cleanly if we tell the decompiler the dst is uint32.
    """
    if depth > 20 or not type_name:
        return None
    if type_name in ("object", "none", "structure", "basic"):
        return None
    type_fields = fields.get(type_name, {})
    if offset in type_fields:
        _fname, ftype = type_fields[offset]
        if skip_opaque and ftype in _OPAQUE_FIELD_TYPES:
            return None
        return ftype
    parent = parents.get(type_name)
    if parent:
        return resolve_field_type(fields, parents, parent, offset,
                                  depth + 1, skip_opaque=skip_opaque)
    return None


# --- IR2 asm scanning ------------------------------------------------------

MIPS_REG_RE = re.compile(r"(?:r0|at|v[01]|a[0-3]|t[0-9]|s[0-8]|k[01]|gp|sp|fp|ra)$")
MIPS_REG_ALT = r"(?:r0|at|v[01]|a[0-3]|t[0-9]|s[0-8]|k[01]|gp|sp|fp|ra)"

# Function / method header in IR2 .asm
RE_FN_HEADER = re.compile(r"^; \.function \(method (\d+) (" + _ATOM + r")\)\s*$")
RE_FN_HEADER_PLAIN = re.compile(r"^; \.function (" + _ATOM + r")\s*$")

# Error in IR2 asm (identical to _disasm.gc form)
RE_LOAD_ERR = re.compile(
    r";; ERROR: failed type prop at (\d+): "
    r"Could not figure out load: \(set! (\S+) \((l\.\w+) \(\+ (\S+) (-?\d+)\)\)\)"
)

# Asm line with op-number comment
RE_ASM_OP_LINE = re.compile(
    r";;\s*\[\s*(\d+)\]\s+.*?\[([^\]]*)\]\s*->\s*\[([^\]]*)\]"
)


def parse_pretypes(bracket_content: str) -> dict[str, str]:
    """Parse '[r1: type1 r2: type2 ...]' content into {reg: type}."""
    pat = re.compile(r"(?:^|\s)(" + MIPS_REG_ALT + r"):\s")
    matches = list(pat.finditer(bracket_content))
    out = {}
    for i, m in enumerate(matches):
        reg = m.group(1)
        s = m.end()
        e = matches[i + 1].start() if i + 1 < len(matches) else len(bracket_content)
        ty = bracket_content[s:e].rstrip()
        out[reg] = ty
    return out


def is_usable_base_type(ty: str) -> bool:
    """Is this pre-type a real named struct whose fields we can look up?"""
    ty = ty.strip()
    if not ty:
        return False
    if ty in _UNUSABLE_BASE_TYPES:
        return False
    # Compound types like "(pointer uint64)" or "(function ...)" — base is not a struct whose offset-N field we can derive.
    if ty.startswith("("):
        return False
    # Annotations like "<sym ...>", "<the etype ...>", "<integer N>", "<value x 8>"
    if ty.startswith("<"):
        return False
    # Symbols wrapped like '#f or '#t or '#f
    if ty.startswith("'"):
        return False
    # Register references that slipped through (like <register `a0` @ op 2>)
    if "register" in ty or "<" in ty:
        return False
    return True


@dataclass
class LoadErr:
    file_stem: str
    fn_key: str           # "(method N type)" or "fn-name"
    op_num: int
    dst_reg: str
    load_op: str          # e.g. "l.wu"
    base_reg: str         # MIPS reg name (e.g. "gp")
    offset: int


def _classify_fn_header(line: str) -> str | None:
    m = RE_FN_HEADER.match(line)
    if m:
        return f"(method {m.group(1)} {m.group(2)})"
    m = RE_FN_HEADER_PLAIN.match(line)
    if m:
        return m.group(1)
    return None


def scan_ir2_file(fp: Path) -> list[tuple[LoadErr, str | None]]:
    """Scan one IR2 .asm file. Returns [(LoadErr, base_pretype_or_None), ...].

    base_pretype is looked up on the asm line whose op-comment matches the
    error's op_num, scoped to the enclosing function.
    """
    stem = fp.name[: -len("_ir2.asm")]
    lines = fp.read_text(errors="replace").splitlines()

    # Pass 1: walk lines, track (fn_header_line_idx, fn_key)
    fn_spans: list[tuple[int, int, str]] = []  # (start, end_excl, fn_key)
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

    # Pass 2: within each fn span, collect errors and build op->asm-line map
    results: list[tuple[LoadErr, str | None]] = []
    for start, end, fn_key in fn_spans:
        # Build op_num -> list of line indices for this fn span
        op_to_line: dict[int, int] = {}
        for i in range(start, end):
            line = lines[i]
            m = re.search(r";;\s*\[\s*(\d+)\]", line)
            if m:
                op = int(m.group(1))
                # First occurrence wins (subsequent wraps are continuations)
                op_to_line.setdefault(op, i)
        # Find errors in this span
        for i in range(start, end):
            m = RE_LOAD_ERR.search(lines[i])
            if not m:
                continue
            op_num = int(m.group(1))
            dst_reg = m.group(2)
            load_op = m.group(3)
            base_reg_ir = m.group(4)
            offset = int(m.group(5))

            # base_reg_ir from the ERROR line is the IR register (e.g. "gp" or "a0-0")
            # The pre-type annotation on the asm line uses the MIPS reg. We need
            # to find the pre-type for base_reg_ir via the asm line for this op.
            err = LoadErr(
                file_stem=stem,
                fn_key=fn_key,
                op_num=op_num,
                dst_reg=dst_reg,
                load_op=load_op,
                base_reg=base_reg_ir,
                offset=offset,
            )

            asm_idx = op_to_line.get(op_num)
            if asm_idx is None:
                results.append((err, None))
                continue

            # Parse pre-types from the asm line
            asm_line = lines[asm_idx]
            mm = RE_ASM_OP_LINE.search(asm_line)
            if not mm:
                results.append((err, None))
                continue
            pre_text = mm.group(2)
            pretypes = parse_pretypes(pre_text)
            # The base_reg_ir from the ERROR form is a MIPS reg (the decompiler
            # normalizes it back for that display). Try direct lookup, then try
            # stripping any "-N" suffix (defensive; shouldn't happen on ERROR form).
            base_mips = base_reg_ir.split("-")[0]
            pretype = pretypes.get(base_mips)
            results.append((err, pretype))

    return results


# --- existing-casts dedup --------------------------------------------------

def load_jsonc(path: Path) -> dict:
    text = path.read_text(errors="replace")
    clean = []
    for line in text.splitlines():
        idx = line.find("//")
        if idx != -1:
            line = line[:idx]
        clean.append(line)
    return json.loads("\n".join(clean))


def entry_covers_op(entry: list, op_num: int) -> bool:
    op_spec = entry[0]
    if isinstance(op_spec, int):
        return op_spec == op_num
    if isinstance(op_spec, list) and len(op_spec) == 2:
        lo, hi = op_spec
        return lo <= op_num <= hi
    return False


def existing_covers(existing: dict, fn_key: str, op_num: int, reg: str) -> bool:
    for e in existing.get(fn_key, []):
        if len(e) < 3:
            continue
        if e[1] != reg:
            continue
        if entry_covers_op(e, op_num):
            return True
    return False


# --- jsonc writing (same surgical edit as type_cast_extractor.py) ----------

def _format_entry(entry: list) -> str:
    e0 = json.dumps(entry[0]) if isinstance(entry[0], list) else str(entry[0])
    return f"    [{e0}, {json.dumps(entry[1])}, {json.dumps(entry[2])}]"


def append_new_keys(path: Path, new_keys: dict[str, list[list]]) -> None:
    raw = path.read_text(errors="replace")
    rstrip = raw.rstrip()
    if not rstrip.endswith("}"):
        raise ValueError(f"{path}: expected file to end with '}}'")
    body = rstrip[:-1].rstrip()
    if not body.endswith(","):
        body = body + ","
    parts = [body]
    keys = sorted(new_keys.keys())
    for i, key in enumerate(keys):
        entries = new_keys[key]
        is_last = i == len(keys) - 1
        parts.append(f"  {json.dumps(key)}: [")
        for j, entry in enumerate(entries):
            ecomma = "," if j < len(entries) - 1 else ""
            parts.append(f"{_format_entry(entry)}{ecomma}")
        parts.append("  ]" + ("," if not is_last else ""))
    parts.append("}")
    path.write_text("\n".join(parts) + "\n")


def extend_existing_key(path: Path, key: str, new_entries: list[list]) -> bool:
    raw = path.read_text(errors="replace")
    lines = raw.splitlines(keepends=True)
    key_pat = re.compile(r"^\s*" + re.escape(json.dumps(key)) + r"\s*:\s*\[")
    start_idx = -1
    for i, line in enumerate(lines):
        if key_pat.match(line):
            start_idx = i
            break
    if start_idx < 0:
        return False
    depth = 0
    end_idx = -1
    for i in range(start_idx, len(lines)):
        stripped = lines[i].split("//", 1)[0]
        for ch in stripped:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx >= 0:
            break
    if end_idx < 0:
        return False
    last_content_idx = -1
    for i in range(end_idx - 1, start_idx, -1):
        content = lines[i].split("//", 1)[0].strip()
        if content:
            last_content_idx = i
            break
    if last_content_idx >= 0:
        line = lines[last_content_idx]
        mm = re.match(r"^(.*?)(\s*)$", line, re.DOTALL)
        body_part = mm.group(1)
        trail = mm.group(2)
        cm = body_part.find("//")
        if cm != -1:
            code = body_part[:cm].rstrip()
            comment = body_part[cm:]
            if not code.endswith(","):
                code = code + ","
            lines[last_content_idx] = code + " " + comment + trail
        else:
            code = body_part.rstrip()
            if not code.endswith(","):
                code = code + ","
            lines[last_content_idx] = code + trail
    insertion = []
    for j, entry in enumerate(new_entries):
        ecomma = "," if j < len(new_entries) - 1 else ""
        insertion.append(f"{_format_entry(entry)}{ecomma}\n")
    lines[end_idx:end_idx] = insertion
    path.write_text("".join(lines))
    return True


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
                    help="Print candidate stats (including unusable pre-types) and exit")
    ap.add_argument("--cast-target", choices=["base", "dst", "both"], default="base",
                    help="Which register to cast: base (resolve the load) or dst "
                         "(type the load result). 'both' emits two entries per load. "
                         "Default 'base' — most reliable for fixing load errors.")
    args = ap.parse_args()

    if args.apply:
        args.dry_run = False

    decomp_dir = Path(args.decomp_out) if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out not found: {decomp_dir}", file=sys.stderr)
        return 1

    print(f"decomp_out:  {decomp_dir}")
    print(f"type_casts:  {TYPE_CASTS_JAKX.relative_to(ROOT)}")
    print(f"all-types:   {ALL_TYPES.relative_to(ROOT)}")

    print("Building field index ...", end=" ", flush=True)
    fields, parents = build_field_index(ALL_TYPES)
    print(f"{len(fields)} types, "
          f"{sum(len(v) for v in fields.values())} fields")

    print("Loading existing type_casts.jsonc ...", end=" ", flush=True)
    existing = load_jsonc(TYPE_CASTS_JAKX)
    print(f"{len(existing)} keys, "
          f"{sum(len(v) for v in existing.values())} entries")

    skip_set = _read_skip_set(args.skip_file)
    if skip_set:
        print(f"skip-file: {len(skip_set)} (fn|op|reg) entries to exclude")

    # Scan all IR2 files
    print("Scanning IR2 files ...", end=" ", flush=True)
    files = sorted(decomp_dir.glob("*_ir2.asm"))
    all_errs: list[tuple[LoadErr, str | None]] = []
    for fp in files:
        all_errs.extend(scan_ir2_file(fp))
    print(f"{len(all_errs)} load errors across {len(files)} files")

    # Stats breakdown
    from collections import Counter
    reasons = Counter()
    candidates: list[tuple[LoadErr, str, str]] = []  # (err, base_type, field_type)

    for err, pretype in all_errs:
        if pretype is None:
            reasons["no-asm-pretype-match"] += 1
            continue
        if err.offset <= 0:
            reasons["negative-offset"] += 1
            continue
        if not is_usable_base_type(pretype):
            reasons[f"unusable-base:{pretype[:30]}"] += 1
            continue
        field_type = resolve_field_type(fields, parents, pretype, err.offset)
        if field_type is None:
            reasons["field-not-found"] += 1
            continue
        # `cast_target` determines the cast register(s).
        #   base: cast BASE to its struct type — decompiler re-runs field lookup
        #   dst:  cast DST to the field's type — decompiler propagates forward
        target_regs = []
        if args.cast_target in ("base", "both"):
            target_regs.append(("base", err.base_reg, pretype))
        if args.cast_target in ("dst", "both"):
            target_regs.append(("dst", err.dst_reg, field_type))

        for kind, reg, cast_ty in target_regs:
            if existing_covers(existing, err.fn_key, err.op_num, reg):
                reasons[f"already-covered-{kind}"] += 1
                continue
            skip_key = f"{err.fn_key}|{err.op_num}|{reg}"
            if skip_key in skip_set:
                reasons["skip-file"] += 1
                continue
            candidates.append((err, reg, cast_ty))

    print(f"\nBreakdown:")
    print(f"  candidates:           {len(candidates)}")
    for r, ct in reasons.most_common():
        print(f"  {r:30s} {ct}")

    if args.stats:
        return 0

    if not candidates:
        print("Nothing to add.")
        return 0

    # Deduplicate by (fn_key, op_num, reg)
    seen = set()
    unique = []
    for err, reg, cast_ty in candidates:
        key = (err.fn_key, err.op_num, reg)
        if key in seen:
            continue
        seen.add(key)
        unique.append((err, reg, cast_ty))

    if len(unique) < len(candidates):
        print(f"  dedup:              {len(candidates)} -> {len(unique)}")

    candidates = unique

    # Group by fn_key
    proposed: dict[str, list[list]] = {}
    for err, reg, cast_ty in candidates:
        proposed.setdefault(err.fn_key, []).append(
            [err.op_num, reg, cast_ty]
        )

    # Apply batch cap. Prefer entries in files with MORE candidates first so
    # we batch the high-density files together (fewer scanner restarts per
    # error).
    if args.batch_size > 0:
        # Flatten + re-group under the cap
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
        f"fix(jakx/type-casts): ir2-prectype extract {total} loads\n\n"
        f"Heuristic: read base-register pre-type from IR2 asm annotation\n"
        f"and look up its field at offset N in all-types.gc. Far more\n"
        f"reliable than jak3 op-number porting (which drifts with basic\n"
        f"block reordering).\n\n"
        f"Gated via apply_guard (err_slack={args.err_slack}).\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    print(f"\nApplying {total} entries via apply_guard ...")
    result = run_with_guard(
        do_apply,
        label=f"ir2-prectype/{total}",
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
