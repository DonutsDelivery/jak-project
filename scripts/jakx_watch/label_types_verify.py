#!/usr/bin/env python3
"""Verify jak3 label_types entries against jakx's binary before bulk-applying.

Background
----------
A previous bulk-port (commit 1485297b5, reverted in 73d60039d) copied 253
jak3 label_types entries into jakx's label_types.jsonc. It was reverted
because L-numbers are assigned per-disassembly-pass and the static data at
L<N> in jak3 is rarely the same data at L<N> in jakx — the type-tags don't
match. The audit at .jakx_watch/label_types_copy_safe_vetted.md found 0/112
"safe" entries when checked against the binary.

This tool re-runs that verification programmatically and emits an
apply-ready candidate list (vetted_safe.jsonc) plus a histogram of failure
reasons (vetted_unsafe.md).

Verification pipeline
---------------------
For each (file, label_name, type, [extra]) entry in jak3's label_types.jsonc:

1. SKIP-COVERED — if jakx label_types.jsonc already has an entry for
   (file, label_name), skip (don't re-propose).
2. TYPE-INACTIVE — if the proposed type is NOT defined / declared in jakx's
   all-types.gc (uncommented (deftype ...) / (declare-type ...)), reject.
   Builtin scalars (uint8/16/32/64, int8/16/32/64, float, symbol, etc.) and
   compound forms (pointer T, inline-array T, array T, ...) are unwrapped to
   their inner element type before checking.
3. NO-ASM — if decompiler_out/jakx/<file>_ir2.asm doesn't exist, reject
   (can't verify; file hasn't been decompiled yet).
4. LABEL-ABSENT — if the label `LN:` is not defined in the jakx asm, reject
   (binary differs, label doesn't exist at that L-number).
5. TYPE-TAG-MISMATCH — read the .type directive immediately preceding the
   label (the disassembler's read of the basic-type-tag word at offset -4
   in the binary). If present, it must be compatible with the proposed type:
       - proposed `T` (basic type) ⇒ asm `.type T` exact match
       - proposed `(inline-array T)` ⇒ asm `.type T` (the first element's tag)
       - proposed `(pointer T)` / scalar (uint64, int32, ...) ⇒ asm should
         have NO `.type` directive (no type-tag in the binary)
   If the asm has no `.type` directive AND the proposed type is a basic
   (something declared/defined as a basic in all-types.gc), that's a
   TYPE-TAG-MISSING reject — basics always carry a type-tag.

Pass = SAFE. Anything else is logged in vetted_unsafe.md with the reason.

NOTE: This tool does NOT extract bytes from the iso_data binary. The
decompiler's _ir2.asm files already contain the disassembled words inline
(as `.word 0x...`) plus the disassembler's type-tag interpretation (as
`.type X` directives). That is the same information a binary reader would
recover, with the disassembler having already done the work. If we later
need stricter byte-level checks (e.g., for non-basic struct contents), the
asm `.word` lines are right there to compare.

Outputs
-------
.jakx_watch/vetted_safe.jsonc   — apply-ready entries, grouped by filename.
                                  Format matches label_types.jsonc exactly.
.jakx_watch/vetted_unsafe.md    — rejected entries with histogram + per-entry
                                  reasons.

Lane: this tool is read-only — DO NOT apply. The user can splice
vetted_safe.jsonc into label_types.jsonc in a follow-up.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JAK3_LABEL_TYPES = ROOT / "decompiler" / "config" / "jak3" / "ntsc_v1" / "label_types.jsonc"
JAKX_LABEL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "label_types.jsonc"
JAKX_ALLTYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
DECOMP_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_FALLBACK = ROOT / "decompiler_out" / "jakx"

OUT_SAFE = ROOT / ".jakx_watch" / "vetted_safe.jsonc"
OUT_UNSAFE = ROOT / ".jakx_watch" / "vetted_unsafe.md"

# Built-in GOAL scalar / value types that have NO type-tag in memory.
# They're either bit-stuffed scalars or pointer-like values, never basics.
BUILTIN_VALUE_TYPES = {
    "int8", "int16", "int32", "int64", "int128",
    "uint8", "uint16", "uint32", "uint64", "uint128",
    "float", "double",
    "byte", "word", "dword", "qword",
    "pointer", "symbol", "object", "none",
    "time-frame", "seconds",
}

# Compound type-spec heads (parenthesized) — the inner element type is what
# the binary actually stores. e.g. `(inline-array vector)` ⇒ first element's
# type-tag is `vector`. `(pointer T)` ⇒ no type-tag (raw pointer).
COMPOUND_HEADS = {
    "inline-array",  # tag of the first element should match
    "array",         # GOAL `array` is a basic itself; element type doesn't appear at offset 0
    "pointer",       # raw pointer, no tag
    "function",      # function pointer, no tag at the data
}

# Pattern: `LN:` label definition at start of line, optionally with `(offset N)`
RE_LABEL_DEF = re.compile(r"^(L\d+)\s*:(?:\s*\(offset\s+(\d+)\))?\s*$", re.MULTILINE)

# Pattern: `.type TYPENAME` directive (TYPENAME is a non-whitespace token).
RE_TYPE_DIRECTIVE = re.compile(r"^\s*\.type\s+(\S+)\s*$")

# Pattern: `(deftype NAME (` or `(declare-type NAME ` from all-types.gc.
RE_DEFTYPE = re.compile(r"^\s*\(deftype\s+(\S+)\s*\(", re.MULTILINE)
RE_DECLARETYPE = re.compile(r"^\s*\(declare-type\s+(\S+)\s+(\S+)\s*\)", re.MULTILINE)
RE_DEFENUM = re.compile(r"^\s*\(defenum\s+(\S+)", re.MULTILINE)


# ---------------------------------------------------------------------------
# JSONC loader (matches label_types_copy_scan.py behavior)
# ---------------------------------------------------------------------------

def load_jsonc(path: Path) -> dict:
    text = path.read_text(errors="replace")
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return json.loads(text)


# ---------------------------------------------------------------------------
# all-types.gc parsing — find ACTIVE types (uncommented deftype / declare-type)
# ---------------------------------------------------------------------------

def load_active_types(path: Path) -> tuple[set[str], dict[str, str]]:
    """Return (active_type_names, parent_kind_map).

    parent_kind_map[name] = "basic" | "structure" | "<parent-type>"
    Used to decide whether a type is expected to carry a type-tag at offset -4.

    Skips lines that are entirely commented out (start with `;`).
    """
    active: set[str] = set()
    parent: dict[str, str] = {}

    if not path.exists():
        return active, parent

    # Strip whole-line comments first to avoid matching commented-out deftypes
    out_lines = []
    for line in path.read_text(errors="replace").splitlines():
        stripped = line.lstrip()
        if stripped.startswith(";"):
            continue
        out_lines.append(line)
    text = "\n".join(out_lines)

    for m in RE_DEFTYPE.finditer(text):
        name = m.group(1)
        active.add(name)
        # Find the parent inside the immediate paren after the name.
        # Format: (deftype NAME (PARENT [...]) ...
        tail = text[m.end():]
        # Up to the first `)` that closes the parent list
        paren_end = tail.find(")")
        if paren_end > 0:
            parent_tok = tail[:paren_end].strip().split()
            if parent_tok:
                parent[name] = parent_tok[0]

    for m in RE_DECLARETYPE.finditer(text):
        name = m.group(1)
        kind = m.group(2)
        active.add(name)
        # Only set parent if not already known from a deftype above
        parent.setdefault(name, kind)

    # Defenums are also active types — they can be used as field types and in
    # type-specs. Lane SM2 found 14 false-positive type_inactive entries (e.g.
    # bucket-id, bucket-id-16, game-task-node-command) caused by skipping these.
    for m in RE_DEFENUM.finditer(text):
        name = m.group(1)
        active.add(name)
        parent.setdefault(name, "uint")

    return active, parent


# ---------------------------------------------------------------------------
# Type-spec helpers
# ---------------------------------------------------------------------------

def split_top_tokens(spec: str) -> list[str]:
    """Tokenize a GOAL type-spec respecting paren nesting. Used for compound types."""
    tokens: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in spec:
        if ch == "(":
            if depth == 0 and cur:
                tokens.append("".join(cur).strip())
                cur = []
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
            if depth == 0:
                tokens.append("".join(cur).strip())
                cur = []
        elif ch.isspace() and depth == 0:
            if cur:
                tokens.append("".join(cur).strip())
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur).strip())
    return [t for t in tokens if t]


def unwrap_typespec(spec: str) -> tuple[str, str]:
    """Return (head, inner_element_type) for a type-spec.

    Examples:
        "vector"                 -> ("vector",       "vector")
        "(inline-array vector)"  -> ("inline-array", "vector")
        "(pointer float)"        -> ("pointer",      "float")
        "(pointer uint16)"       -> ("pointer",      "uint16")
        "(array uint8)"          -> ("array",        "uint8")
        "uint64"                 -> ("uint64",       "uint64")
    """
    spec = spec.strip()
    if not spec.startswith("("):
        return spec, spec
    inner = spec[1:-1].strip()
    toks = split_top_tokens(inner)
    if not toks:
        return spec, spec
    head = toks[0]
    if head in COMPOUND_HEADS and len(toks) >= 2:
        inner_elem = toks[1]
        # Recurse one level if needed (e.g. `(inline-array (pointer X))` — rare)
        if inner_elem.startswith("("):
            _, inner_elem = unwrap_typespec(inner_elem)
        return head, inner_elem
    # Unknown compound — treat as basic-name
    return head, head


def expects_type_tag(typespec: str, parent_kind_map: dict[str, str]) -> tuple[bool, str]:
    """Return (expects_tag, element_type).

    A type-tag at offset -4 is present in the binary IFF the underlying type
    is a `basic` (or descended from one). Pointers, scalars, and inline-arrays
    of value types don't carry a tag.

    For inline-array of basics, the FIRST element does carry a tag at its
    offset 0 (which is +0 of the label — same place we'd look).
    """
    head, elem = unwrap_typespec(typespec)

    # Pure scalars / values
    if elem in BUILTIN_VALUE_TYPES:
        return False, elem

    # Pointers and arrays of value types: no tag
    if head == "pointer":
        return False, elem
    if head == "function":
        return False, elem

    # `array` is itself a basic — when proposed type is `(array T)` the data at
    # the label is the array header (basic), tag = `array`.
    if head == "array":
        return True, "array"

    # `inline-array T`: first element starts at offset 0. If the element is a
    # basic, it carries a tag.
    if head == "inline-array":
        # Walk parent chain to determine if elem is a basic-derived type
        return _is_basic_descended(elem, parent_kind_map), elem

    # Plain basic type (e.g. "vector", "light-hash-work", "gs-store-image-packet")
    return _is_basic_descended(elem, parent_kind_map), elem


def _is_basic_descended(name: str, parent_kind_map: dict[str, str]) -> bool:
    """Walk the parent chain in all-types.gc to determine basic-vs-structure."""
    # Built-in roots
    if name == "basic":
        return True
    if name in ("structure", "uint128", "int128"):
        return False
    if name in BUILTIN_VALUE_TYPES:
        return False

    # Walk up the parent chain
    seen: set[str] = set()
    cur = name
    while cur and cur not in seen:
        seen.add(cur)
        parent = parent_kind_map.get(cur)
        if parent is None:
            # Unknown — assume basic if name suggests so; otherwise default to basic
            # because most named types in all-types.gc are basics.
            return True
        if parent == "basic":
            return True
        if parent == "structure":
            return False
        cur = parent
    return True  # default optimistic — un-tagged would surface as a separate failure


# ---------------------------------------------------------------------------
# ASM scanning — find label + preceding .type directive
# ---------------------------------------------------------------------------

def pick_decomp_dir() -> Path | None:
    for p in (DECOMP_PRIMARY, DECOMP_FALLBACK):
        if p.exists() and any(p.glob("*_ir2.asm")):
            return p
    return None


def scan_asm_labels(asm_path: Path) -> dict[str, dict]:
    """Return { label_name: { 'tag': str|None, 'is_pair': bool, 'is_data': bool } }.

    `tag` is the disassembler-emitted `.type X` directive immediately above
    the LN: line (skipping blank/comment lines). It corresponds to the basic
    type-tag word in the binary at offset -4 of the label.

    `is_pair` is True when the label is defined with `(offset 2)`, indicating
    a Lisp pair (cons cell). Pair cells are pointer-tagged, so any proposed
    scalar/integer type is wrong.

    `is_data` is True if the FIRST non-blank, non-comment line AFTER the label
    is a data directive (`.word`, `.type`, `.symbol`, `.empty-list`, ...). A
    label_types entry only makes sense for data labels — code labels (inside
    function bodies) are jump targets and have no associated GOAL type.
    """
    if not asm_path.exists():
        return {}
    text = asm_path.read_text(errors="replace")
    lines = text.splitlines()
    result: dict[str, dict] = {}

    for i, line in enumerate(lines):
        m = re.match(r"^(L\d+)\s*:(?:\s*\(offset\s+(\d+)\))?", line)
        if not m:
            continue
        label = m.group(1)
        offset = m.group(2)
        is_pair = offset == "2"

        # Look upward for the most recent `.type X` directive.
        type_tag: str | None = None
        for j in range(i - 1, max(-1, i - 8), -1):
            prev = lines[j].rstrip()
            if not prev.strip():
                continue
            if prev.lstrip().startswith(";"):
                continue
            tm = RE_TYPE_DIRECTIVE.match(prev)
            if tm:
                type_tag = tm.group(1)
            break

        # Look downward for the first non-blank, non-comment line — if it's
        # a data directive, this is a data label; otherwise it's a code label.
        is_data = False
        for j in range(i + 1, min(len(lines), i + 8)):
            nxt = lines[j].rstrip()
            if not nxt.strip():
                continue
            if nxt.lstrip().startswith(";"):
                continue
            # If we hit another label or a `B<N>:` block header, treat as data
            # iff the line LOOKS like a directive — block headers themselves
            # are above-code and don't tell us anything.
            if re.match(r"^L\d+\s*:", nxt) or re.match(r"^B\d+\s*:", nxt):
                continue
            if RE_DATA_DIRECTIVE.match(nxt):
                is_data = True
            break

        # Pair cells ARE data (just pointer-tagged) — disassembler emits
        # `.symbol` / `.word L...` / `.empty-list` for them, so the directive
        # check covers it. But guard explicitly in case offset-2 ever appears
        # without a directive line.
        if is_pair:
            is_data = True

        result.setdefault(label, {"tag": type_tag, "is_pair": is_pair, "is_data": is_data})

    return result


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

REASONS = (
    "skip_already_in_jakx",
    "type_inactive",
    "no_asm",
    "label_absent",
    "code_label",
    "type_tag_mismatch",
    "type_tag_missing",
    "pair_cell_mismatch",
)

# Lines that indicate a label points to STATIC DATA (not code).
# `.word`, `.type`, `.symbol`, `.empty-list` are all data directives the
# disassembler emits. Anything else (a MIPS mnemonic like `sw`, `addiu`,
# `lw`, etc.) means we're inside a function body and the label is a code
# label — never a valid label_types target.
RE_DATA_DIRECTIVE = re.compile(
    r"^\s*\.(word|type|symbol|empty-list|function|byte|half|asciz|incbin)\b"
)


def verify_entry(
    fname: str,
    entry: list,
    *,
    jakx_covered: dict[str, set[str]],
    active_types: set[str],
    parent_kind_map: dict[str, str],
    asm_dir: Path,
    label_cache: dict[str, dict[str, dict]],
) -> tuple[str, str]:
    """Return (verdict, detail).

    verdict ∈ {"safe", *REASONS}
    """
    label = entry[0]
    typespec = entry[1] if len(entry) > 1 else ""

    # 1. SKIP — already in jakx
    if label in jakx_covered.get(fname, set()):
        return "skip_already_in_jakx", f"jakx already has {fname}/{label}"

    # 2. Type active
    head, elem = unwrap_typespec(typespec)
    inner_to_check = elem
    if (
        inner_to_check not in BUILTIN_VALUE_TYPES
        and inner_to_check not in active_types
    ):
        return "type_inactive", f"type `{inner_to_check}` not active in jakx all-types.gc"

    # The compound HEAD itself if it's a real type (e.g. `array`) must also be active.
    # `inline-array` and `pointer` are GOAL syntax forms, not types.
    if head not in COMPOUND_HEADS and head != elem:
        if head not in BUILTIN_VALUE_TYPES and head not in active_types:
            return "type_inactive", f"head type `{head}` not active in jakx all-types.gc"

    # 3. ASM exists
    if fname not in label_cache:
        asm_path = asm_dir / f"{fname}_ir2.asm"
        label_cache[fname] = scan_asm_labels(asm_path)
    labels = label_cache[fname]
    if not labels:
        return "no_asm", f"no jakx asm at decompiler_out/jakx/{fname}_ir2.asm"

    # 4. Label exists
    if label not in labels:
        return "label_absent", f"label {label} not defined in jakx {fname}_ir2.asm"

    info = labels[label]
    asm_tag: str | None = info["tag"]
    is_pair: bool = info["is_pair"]
    is_data: bool = info["is_data"]

    # 5. Code-label check — labels followed by MIPS instructions are jump
    # targets inside function bodies, not static data. The L-number happens
    # to coincide with what jak3 typed but the data isn't there.
    if not is_data:
        return (
            "code_label",
            f"{label} in jakx is a code label (jump target inside a function), "
            f"not static data — L-number coincidence",
        )

    # 6. Pair-cell check — labels with `(offset 2)` are Lisp cons cells
    # (pointer-tagged with low bits = 010). Any proposed scalar / non-pair
    # type is wrong: jak3 had a string/whatever at that L-number, jakx has
    # a quoted-list cell.
    if is_pair:
        head, _ = unwrap_typespec(typespec)
        if head not in ("pair",):
            return (
                "pair_cell_mismatch",
                f"proposed `{typespec}` but {label} is a pair cell (offset 2) "
                f"in jakx — data is a cons cell, not the proposed type",
            )

    # 7. Type-tag check
    expects_tag, expected_elem = expects_type_tag(typespec, parent_kind_map)

    if expects_tag:
        if asm_tag is None:
            return (
                "type_tag_missing",
                f"proposed `{typespec}` expects basic-tag `{expected_elem}` "
                f"but no .type directive precedes {label}",
            )
        if asm_tag != expected_elem:
            return (
                "type_tag_mismatch",
                f"proposed `{typespec}` (tag=`{expected_elem}`) "
                f"but binary tag is `{asm_tag}`",
            )
    else:
        # Doesn't expect a tag. If asm HAS a tag, the data is actually a basic of
        # that tag — the proposed scalar/pointer is wrong.
        if asm_tag is not None:
            return (
                "type_tag_mismatch",
                f"proposed `{typespec}` (no tag expected) "
                f"but binary has .type `{asm_tag}` — data is actually a basic",
            )

    return "safe", "passed all checks"


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_safe_jsonc(safe_by_file: dict[str, list[list]]) -> None:
    OUT_SAFE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "// vetted_safe.jsonc — entries that passed scripts/jakx_watch/label_types_verify.py",
        "//",
        "// Each entry has been checked for:",
        "//   1. Not already present in jakx label_types.jsonc",
        "//   2. Proposed type is ACTIVE in jakx all-types.gc",
        "//   3. The label LN: exists in decompiler_out/jakx/<file>_ir2.asm",
        "//   4. The binary type-tag (.type directive) matches the proposed type",
        "//",
        "// To apply: splice these entries into",
        "//   decompiler/config/jakx/ntsc_v1/label_types.jsonc",
        "// (merge under each filename key — DO NOT replace existing arrays).",
        "{",
    ]
    files = sorted(safe_by_file.keys())
    for i, fname in enumerate(files):
        entries = safe_by_file[fname]
        lines.append(f'  {json.dumps(fname)}: [')
        for j, e in enumerate(entries):
            entry_json = json.dumps(e, separators=(", ", ": "))
            comma = "," if j < len(entries) - 1 else ""
            lines.append(f"    {entry_json}{comma}")
        comma = "," if i < len(files) - 1 else ""
        lines.append(f"  ]{comma}")
    lines.append("}")
    OUT_SAFE.write_text("\n".join(lines) + "\n")


def write_unsafe_md(
    unsafe_by_reason: dict[str, list[tuple[str, list, str]]],
    counts: Counter,
    total_jak3: int,
    safe_count: int,
) -> None:
    OUT_UNSAFE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# vetted_unsafe.md — jak3 label_types entries rejected for jakx",
        "",
        "_source: `scripts/jakx_watch/label_types_verify.py`_",
        "",
        f"Verified {total_jak3} jak3 label_types entries against jakx's binary "
        "(via decompiler_out/jakx/*_ir2.asm) and all-types.gc.",
        "",
        "## Histogram",
        "",
        "| reason | count | meaning |",
        "|--------|------:|---------|",
        f"| **safe** | {safe_count} | passes all checks — see `vetted_safe.jsonc` |",
        f"| skip_already_in_jakx | {counts['skip_already_in_jakx']} | jakx label_types already covers this (file, label) |",
        f"| type_inactive | {counts['type_inactive']} | proposed type is not defined in jakx all-types.gc |",
        f"| no_asm | {counts['no_asm']} | jakx hasn't decompiled this file yet |",
        f"| label_absent | {counts['label_absent']} | jakx asm doesn't have that L-number — binary differs |",
        f"| code_label | {counts['code_label']} | label is a jump target inside a function, not static data |",
        f"| type_tag_mismatch | {counts['type_tag_mismatch']} | binary .type tag conflicts with proposed type |",
        f"| type_tag_missing | {counts['type_tag_missing']} | proposed type is a basic but binary has no .type tag |",
        f"| pair_cell_mismatch | {counts['pair_cell_mismatch']} | label is a Lisp pair (offset 2) but proposed type is not `pair` |",
        "",
        "---",
        "",
    ]

    # Detailed sections per reason (excluding skip — usually huge and uninteresting)
    for reason in REASONS:
        if reason == "skip_already_in_jakx":
            continue
        entries = unsafe_by_reason.get(reason, [])
        lines.append(f"## {reason} ({len(entries)})")
        lines.append("")
        if not entries:
            lines.append("_None._")
            lines.append("")
            continue
        # Limit detailed listing to keep file readable; group by file
        by_file: dict[str, list[tuple[list, str]]] = defaultdict(list)
        for fname, entry, detail in entries:
            by_file[fname].append((entry, detail))
        for fname in sorted(by_file.keys()):
            items = by_file[fname]
            lines.append(f"### `{fname}` ({len(items)})")
            lines.append("")
            for entry, detail in sorted(items, key=lambda x: int(x[0][0][1:]) if x[0][0][1:].isdigit() else 0):
                label = entry[0]
                typespec = entry[1] if len(entry) > 1 else "?"
                lines.append(f"- **{label}** `{typespec}` — {detail}")
            lines.append("")

    OUT_UNSAFE.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--decomp-out", default=None,
                    help="override decomp dir (default: .jakx_watch/decomp_out/jakx "
                         "or decompiler_out/jakx)")
    ap.add_argument("--no-write", action="store_true",
                    help="print summary only; don't write output files")
    args = ap.parse_args()

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if decomp_dir is None:
        print("ERROR: no decomp output dir with _ir2.asm files found", file=sys.stderr)
        print(f"  tried: {DECOMP_PRIMARY}", file=sys.stderr)
        print(f"  tried: {DECOMP_FALLBACK}", file=sys.stderr)
        return 1
    print(f"decomp dir:    {decomp_dir.relative_to(ROOT)}")
    print(f"jak3 cfg:      {JAK3_LABEL_TYPES.relative_to(ROOT)}")
    print(f"jakx cfg:      {JAKX_LABEL_TYPES.relative_to(ROOT)}")
    print(f"jakx all-types: {JAKX_ALLTYPES.relative_to(ROOT)}")

    jak3 = load_jsonc(JAK3_LABEL_TYPES)
    jakx = load_jsonc(JAKX_LABEL_TYPES)
    active_types, parent_kind_map = load_active_types(JAKX_ALLTYPES)

    print(f"\nloaded:")
    print(f"  jak3 entries:        {sum(len(v) for v in jak3.values())} across {len(jak3)} files")
    print(f"  jakx entries:        {sum(len(v) for v in jakx.values())} across {len(jakx)} files")
    print(f"  jakx active types:   {len(active_types)} (deftype + declare-type)")

    jakx_covered: dict[str, set[str]] = {
        fname: {e[0] for e in entries} for fname, entries in jakx.items()
    }

    safe_by_file: dict[str, list[list]] = defaultdict(list)
    unsafe_by_reason: dict[str, list[tuple[str, list, str]]] = defaultdict(list)
    label_cache: dict[str, dict[str, dict]] = {}

    counts: Counter = Counter()
    total = 0

    for fname in sorted(jak3.keys()):
        for entry in jak3[fname]:
            total += 1
            verdict, detail = verify_entry(
                fname, entry,
                jakx_covered=jakx_covered,
                active_types=active_types,
                parent_kind_map=parent_kind_map,
                asm_dir=decomp_dir,
                label_cache=label_cache,
            )
            counts[verdict] += 1
            if verdict == "safe":
                safe_by_file[fname].append(entry)
            else:
                unsafe_by_reason[verdict].append((fname, entry, detail))

    safe_count = counts["safe"]
    print(f"\nVerified {total} entries:")
    print(f"  SAFE                       : {safe_count}")
    for r in REASONS:
        print(f"  {r:<27}: {counts[r]}")

    if args.no_write:
        return 0

    write_safe_jsonc(safe_by_file)
    write_unsafe_md(unsafe_by_reason, counts, total, safe_count)
    print(f"\nwrote {OUT_SAFE.relative_to(ROOT)}  ({safe_count} safe entries across "
          f"{len(safe_by_file)} files)")
    print(f"wrote {OUT_UNSAFE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
