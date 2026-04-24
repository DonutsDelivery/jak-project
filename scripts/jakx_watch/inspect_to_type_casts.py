#!/usr/bin/env python3
"""Auto-generate type_cast entries for method-3 (inspect) struct-field loads.

For each "Could not figure out load" error in an inspect method body, look up
the field at that offset in all-types.gc and emit a type_cast entry so the
decompiler can resolve the load.

Strategy:
  * method 3 = inspect — rigid structure, low blast radius for type_casts
  * For (set! DST (LOAD (+ SRC OFFS))) failures, look up TYPE.field[OFFS]
  * Emit {"(method 3 TYPE)": [[op, "DST", field_type]]} into type_casts.jsonc

Run with --dry-run to preview without writing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"
TYPE_CASTS = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "type_casts.jsonc"
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"

# --- all-types.gc parsing ---

# Matches active (non-commented) deftype header
RE_DEFTYPE = re.compile(r"^\(deftype\s+([\w<>\-!?:\+\*/=]+)\s+\(([\w<>\-!?:\+\*/=]+)\)")
# Matches a field line with :offset or :offset-assert N
# Captures: (field-name type ... :offset[-assert] N ...)
RE_FIELD_OFFSET = re.compile(
    r"^\s*\(+\s*([\w<>\-!?:\+\*/=]+)"   # field name (handle leading ((  )
    r"\s+([\w<>\-!?:\+\*/=]+)"           # field type (first token)
    r"[^)]*?:offset(?:-assert)?\s+(\d+)" # :offset or :offset-assert N
)
# Matches a field with the legacy positional offset form: (name type N ...) but no :offset
RE_FIELD_POSITIONAL = re.compile(
    r"^\s*\(+\s*([\w<>\-!?:\+\*/=]+)"   # field name
    r"\s+([\w<>\-!?:\+\*/=]+)"           # field type
    r"\s+(\d+)"                           # N = offset (positional)
    r"(?:\s|$)"
)

# Types that are opaque byte/short arrays (no real sub-type, skip)
_OPAQUE_TYPE_RE = re.compile(r"^u?int(?:8|16|32|64)$")


def _is_opaque(field_type: str) -> bool:
    return bool(_OPAQUE_TYPE_RE.match(field_type)) or field_type in (
        "uint8", "int8", "uint16", "int16", "uint32", "int32", "uint64", "int64",
    )


def build_field_index(all_types_path: Path) -> tuple[dict, dict]:
    """Parse all-types.gc.

    Returns:
      fields  : {type_name: {offset: (field_name, field_type)}}
      parents : {type_name: parent_name}
    """
    fields: dict[str, dict[int, tuple[str, str]]] = {}
    parents: dict[str, str] = {}

    lines = all_types_path.read_text(errors="replace").splitlines()
    in_block_comment = False
    current_type: str | None = None
    in_field_block = False
    paren_depth = 0

    for line in lines:
        stripped = line.strip()

        # Track block comments  #| ... |#
        if not in_block_comment and "#|" in line:
            in_block_comment = True
        if in_block_comment:
            if "|#" in line:
                in_block_comment = False
            continue
        if stripped.startswith(";;") or stripped.startswith(";"):
            continue

        # Detect deftype start
        dm = RE_DEFTYPE.match(stripped)
        if dm:
            current_type = dm.group(1)
            parent_name = dm.group(2)
            parents[current_type] = parent_name
            fields.setdefault(current_type, {})
            in_field_block = False
            paren_depth = 0
            continue

        if current_type is None:
            continue

        # Detect field block start: the opening paren list inside the deftype
        # (before :methods or :size-assert etc.)
        if re.match(r"^\s*\(\s*\(", line) and not in_field_block:
            in_field_block = True
            paren_depth = 0

        # Closing (:methods or :size-assert etc.) ends the field block
        if in_field_block and re.match(r"^\s*:(?:method|size|flag)", stripped):
            in_field_block = False
            continue

        # Also close on (:methods
        if in_field_block and re.match(r"^\s*\(:methods", stripped):
            in_field_block = False
            continue

        # Parse field lines (whether or not we're in the explicit block)
        # Try :offset / :offset-assert form first
        fm = RE_FIELD_OFFSET.match(line)
        if fm:
            fname = fm.group(1)
            ftype = fm.group(2)
            foff = int(fm.group(3))
            if fname not in (":methods", ":fields", ":size-assert", ":flag-assert"):
                fields[current_type][foff] = (fname, ftype)
            continue

        # Try positional offset form: (name type N ...)
        fm2 = RE_FIELD_POSITIONAL.match(line)
        if fm2:
            fname = fm2.group(1)
            ftype = fm2.group(2)
            foff = int(fm2.group(3))
            # Only treat as field if it looks like an offset (< 65536) and field
            # name doesn't look like a keyword
            if (fname not in (":methods", ":fields", ":size-assert", ":flag-assert", "deftype")
                    and foff < 65536 and ftype not in ("(", ")")):
                fields[current_type].setdefault(foff, (fname, ftype))

    return fields, parents


def resolve_field_type(
    fields: dict,
    parents: dict,
    type_name: str,
    offset: int,
    depth: int = 0,
) -> str | None:
    """Walk inheritance chain to find the type of the field at offset."""
    if depth > 20 or not type_name or type_name in ("object", "none", "structure", "basic"):
        return None
    type_fields = fields.get(type_name, {})
    if offset in type_fields:
        field_name, field_type = type_fields[offset]
        if _is_opaque(field_type):
            return None  # skip opaque int/byte arrays
        return field_type
    parent = parents.get(type_name)
    if parent:
        return resolve_field_type(fields, parents, parent, offset, depth + 1)
    return None


# --- IR2 scanning ---

RE_METHOD_HEADER = re.compile(r"; \.function \(method (\d+) ([\w<>\-!?:\+\*/=]+)\)")
RE_NEXT_FUNC = re.compile(r"; \.function ")
# Failing load with struct offset: (set! DST (LOAD (+ SRC OFFS)))
RE_LOAD_STRUCT = re.compile(
    r";; ERROR: failed type prop at (\d+): Could not figure out load: "
    r"\(set! (\S+) \((l\.\w+) \(\+ (\S+) (-?\d+)\)\)\)"
)

# For method 3 (inspect): accept gp or a0 as this-pointer source.
# For all other methods: only accept a0 (first argument = this).
# gp in non-inspect methods is the MIPS global-pointer and is unreliable as this.
_M3_THIS_REGS = {"gp", "a0"}
_OTHER_THIS_REGS = {"a0"}


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def scan_method_field_loads(
    decomp_dir: Path,
    fields: dict,
    parents: dict,
) -> dict[str, list[list]]:
    """
    Scan all IR2 files for method bodies with failing struct-offset loads where
    the source register is the this-pointer (a0 for any method, also gp for method-3).

    For each failure `(set! DST (l.xx (+ THIS OFFS)))` in `(method N TYPE)`:
      - look up the field type at OFFS in TYPE (via inheritance chain)
      - emit a type_cast entry [op, DST, field_type]

    Returns {function_key: [cast_entries]}.
    """
    casts: dict[str, list[list]] = {}

    for fp in sorted(decomp_dir.glob("*_ir2.asm")):
        text = fp.read_text(errors="replace")

        for mhdr in RE_METHOD_HEADER.finditer(text):
            method_num = int(mhdr.group(1))
            type_name = mhdr.group(2)
            body_start = mhdr.end()

            # Find where the next function starts
            next_fn = RE_NEXT_FUNC.search(text, body_start)
            body_end = next_fn.start() if next_fn else body_start + 20000
            body = text[body_start:body_end]

            this_regs = _M3_THIS_REGS if method_num == 3 else _OTHER_THIS_REGS

            for err in RE_LOAD_STRUCT.finditer(body):
                op_num = int(err.group(1))
                dst_reg = err.group(2)
                src_reg = err.group(4)
                offset = int(err.group(5))

                # Only handle positive offsets (struct field accesses)
                if offset <= 0:
                    continue

                # Only handle loads where source is the this-pointer
                if src_reg not in this_regs:
                    continue

                # Look up field type at this offset in the type hierarchy
                field_type = resolve_field_type(fields, parents, type_name, offset)
                if field_type is None:
                    continue

                # Skip generic/opaque types (not useful as cast targets)
                if field_type in ("object", "none", "basic", "structure"):
                    continue

                fn_key = f"(method {method_num} {type_name})"
                cast_entry = [op_num, dst_reg, field_type]
                casts.setdefault(fn_key, [])
                existing = {(e[0], e[1]) for e in casts[fn_key]}
                if (op_num, dst_reg) not in existing:
                    casts[fn_key].append(cast_entry)

    return casts


# Keep old name as alias for backward compatibility
def scan_inspect_methods(decomp_dir, fields, parents):
    return scan_method_field_loads(decomp_dir, fields, parents)


# --- type_casts.jsonc merge ---

def load_type_casts(path: Path) -> dict:
    """Load type_casts.jsonc, stripping // comments."""
    text = path.read_text(errors="replace")
    # Strip // line comments
    lines = []
    for line in text.splitlines():
        comment_pos = line.find("//")
        if comment_pos != -1:
            line = line[:comment_pos]
        lines.append(line)
    clean = "\n".join(lines)
    return json.loads(clean)


def merge_casts(existing: dict, new_casts: dict) -> tuple[dict, int]:
    """Merge new_casts into existing. Returns (merged, count_added)."""
    added = 0
    merged = dict(existing)  # shallow copy
    for fn_key, entries in new_casts.items():
        if fn_key not in merged:
            merged[fn_key] = []
        existing_ops = {
            (e[0], e[1]) if isinstance(e[0], int) else (tuple(e[0]), e[1])
            for e in merged[fn_key]
        }
        for entry in entries:
            key = (entry[0], entry[1])
            if key not in existing_ops:
                merged[fn_key].append(entry)
                existing_ops.add(key)
                added += 1
    return merged, added


def _format_entry(entry: list) -> str:
    """Format a single cast entry as a compact one-liner: [op, "reg", "type"]."""
    e0 = json.dumps(entry[0]) if isinstance(entry[0], list) else str(entry[0])
    return f"    [{e0}, {json.dumps(entry[1])}, {json.dumps(entry[2])}]"


def write_type_casts(path: Path, new_keys: dict) -> None:
    """Surgically append new keys to type_casts.jsonc without touching existing content.

    Reads the raw file, finds the closing }, adds a trailing comma to the last
    existing entry, then inserts new key blocks before the closing brace.
    Existing content (including // comments and formatting) is preserved.
    """
    raw = path.read_text(errors="replace")
    # Find the last closing brace (the top-level JSON object close)
    rstrip = raw.rstrip()
    if not rstrip.endswith("}"):
        raise ValueError(f"{path}: expected file to end with '}}', got: {rstrip[-20:]!r}")

    # Everything before the closing }
    body = rstrip[:-1].rstrip()

    # Ensure body ends with a comma so we can append new entries
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
        # No comma after last new key (it becomes the new last entry)
        parts.append("  ]" + ("," if not is_last else ""))

    parts.append("}")
    path.write_text("\n".join(parts) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print proposed entries without writing")
    ap.add_argument("--decomp-out", help="Override decomp output directory")
    ap.add_argument("--all-types", help="Override all-types.gc path")
    ap.add_argument("--type-casts", help="Override type_casts.jsonc path")
    args = ap.parse_args()

    all_types_path = Path(args.all_types) if args.all_types else ALL_TYPES
    type_casts_path = Path(args.type_casts) if args.type_casts else TYPE_CASTS
    decomp_dir = Path(args.decomp_out) if args.decomp_out else pick_decomp_dir()

    if not all_types_path.exists():
        print(f"ERROR: all-types.gc not found: {all_types_path}", file=sys.stderr)
        return 1
    if not decomp_dir.exists():
        print(f"ERROR: decomp output dir not found: {decomp_dir}", file=sys.stderr)
        return 1

    print(f"Building field index from {all_types_path.name}...", file=sys.stderr)
    fields, parents = build_field_index(all_types_path)
    type_count = len(fields)
    field_count = sum(len(v) for v in fields.values())
    print(f"  {type_count} types, {field_count} field entries indexed", file=sys.stderr)

    print(f"Scanning method bodies in {decomp_dir.name}/...", file=sys.stderr)
    new_casts = scan_method_field_loads(decomp_dir, fields, parents)

    total_new = sum(len(v) for v in new_casts.values())
    print(f"  {total_new} candidate type_cast entries across {len(new_casts)} method functions")
    print()

    if total_new == 0:
        print("Nothing to add.")
        return 0

    print("Proposed entries:")
    for fn_key, entries in sorted(new_casts.items()):
        print(f"  {fn_key}:")
        for e in entries:
            print(f"    op={e[0]:4d}  reg={e[1]:6s}  type={e[2]}")

    if args.dry_run:
        print("\n--dry-run: not writing.")
        return 0

    if not type_casts_path.exists():
        print(f"ERROR: type_casts.jsonc not found: {type_casts_path}", file=sys.stderr)
        return 1

    existing = load_type_casts(type_casts_path)
    _, added = merge_casts(existing, new_casts)

    if added == 0:
        print("\nAll entries already present — nothing to add.")
        return 0

    # Build dict of only brand-new keys (not already in file) for surgical append.
    # Keys that already exist are skipped — they require in-place editing (not yet supported).
    new_keys_only: dict[str, list] = {}
    skipped_keys = []
    for fn_key, entries in new_casts.items():
        if fn_key not in existing:
            new_keys_only[fn_key] = entries
        else:
            existing_ops = {
                (e[0], e[1]) if isinstance(e[0], int) else (tuple(e[0]), e[1])
                for e in existing[fn_key]
            }
            truly_new = [e for e in entries if (e[0], e[1]) not in existing_ops]
            if truly_new:
                skipped_keys.append(fn_key)
                print(f"  SKIP (key exists, in-place edit not yet supported): {fn_key}")

    if not new_keys_only:
        print("\nAll new entries belong to existing keys — nothing to append.")
        return 0

    print(f"\nAppending {sum(len(v) for v in new_keys_only.values())} entries "
          f"across {len(new_keys_only)} new keys to {type_casts_path.name}...", end="")
    write_type_casts(type_casts_path, new_keys_only)
    print(" done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
