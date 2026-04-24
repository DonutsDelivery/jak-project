#!/usr/bin/env python3
"""Add 'function was not converted to expressions' functions to mips2c_functions_by_name.

The decompiler's only mechanism to suppress "function was not converted to
expressions. Cannot decompile." errors is to have the function in
mips2c_functions_by_name in hacks.jsonc.  When present, run_mips2c() is
called on the MIPS bytecode, sets func.mips2c_output, and the decompiler
emits INFO + a rough C++ translation instead of the ERROR marker.

asm_functions_by_name does NOT suppress this error (172 entries, all still
ERROR) — only mips2c_functions_by_name works.

VU-crash risk: functions with vsqi/viaddi/vlqi/viand opcodes will crash
run_mips2c.  Only ripple.gc contains those in this build; those functions
are skipped automatically.

Usage:
    python3 scripts/jakx_watch/asm_func_apply.py --dry-run
    python3 scripts/jakx_watch/asm_func_apply.py --apply
    python3 scripts/jakx_watch/asm_func_apply.py --apply --batch-size 50

Options:
    --dry-run      Print candidates without modifying hacks.jsonc (default)
    --apply        Write candidates to mips2c_functions_by_name
    --batch-size N Cap the number of new entries added (default: all)
    --skip-asm     Skip functions already in asm_functions_by_name (more cautious)
    --only-asm     Only process functions already in asm_functions_by_name
    --decomp-out   Override decomp_out directory
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
HACKS_JSONC = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "hacks.jsonc"

# VU opcodes that crash run_mips2c — skip any file containing these
VU_CRASH_OPCODES = re.compile(r"\b(vsqi|viaddi|vlqi|viand|vmtirx)\b")

RE_DEF_FUNCTION = re.compile(r"^;; definition for function ([\w<>!?:\-\+\*/=]+)")
RE_DEF_METHOD = re.compile(r"^;; definition for method (\d+) of type ([\w<>!?:\-\+\*/=]+)")
RE_NOT_CONVERTED = re.compile(r"^;; ERROR: function was not converted to expressions\.")


def pick_decomp_dir(override: str | None) -> Path:
    if override:
        return Path(override)
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


def scan_vu_files(decomp_dir: Path) -> set[str]:
    """Return set of source file basenames (no extension) that contain VU opcodes."""
    vu_files: set[str] = set()
    for ir2_asm in decomp_dir.glob("*_ir2.asm"):
        try:
            text = ir2_asm.read_text(errors="replace")
        except OSError:
            continue
        if VU_CRASH_OPCODES.search(text):
            # Extract the source file name (strip _ir2.asm suffix)
            stem = ir2_asm.name[: -len("_ir2.asm")]
            vu_files.add(stem)
    return vu_files


def parse_not_converted(decomp_dir: Path, vu_files: set[str]) -> list[tuple[str, str]]:
    """Parse disasm files and return list of (mips2c_key, source_file) for not-converted fns.

    mips2c_key format:
      - plain function: "function-name"
      - method: "(method N typename)"
    """
    results: list[tuple[str, str]] = []

    for disasm_gc in sorted(decomp_dir.glob("*_disasm.gc")):
        stem = disasm_gc.name[: -len("_disasm.gc")]
        if stem in vu_files:
            continue  # skip VU-crash files

        try:
            text = disasm_gc.read_text(errors="replace")
        except OSError:
            continue

        lines = text.splitlines()
        last_def: str | None = None
        last_def_line = -1

        for lineno, line in enumerate(lines):
            m_fn = RE_DEF_FUNCTION.match(line)
            if m_fn:
                last_def = m_fn.group(1)
                last_def_line = lineno
                continue

            m_mt = RE_DEF_METHOD.match(line)
            if m_mt:
                method_id = int(m_mt.group(1))
                type_name = m_mt.group(2)
                last_def = f"(method {method_id} {type_name})"
                last_def_line = lineno
                continue

            if RE_NOT_CONVERTED.match(line):
                if last_def is not None and (lineno - last_def_line) <= 6:
                    results.append((last_def, stem))
                last_def = None
                last_def_line = -1

    return results


def load_existing_mips2c(hacks_text: str) -> set[str]:
    """Extract currently-listed function names from mips2c_functions_by_name."""
    in_block = False
    entries: set[str] = set()
    for line in hacks_text.splitlines():
        stripped = line.strip()
        if '"mips2c_functions_by_name"' in stripped:
            in_block = True
            continue
        if in_block:
            if stripped.startswith("]"):
                break
            if stripped.startswith("//"):
                continue
            m = re.match(r'^"([^"]+)"', stripped)
            if m:
                entries.add(m.group(1))
    return entries


def load_existing_asm(hacks_text: str) -> set[str]:
    """Extract currently-listed function names from asm_functions_by_name."""
    in_block = False
    entries: set[str] = set()
    for line in hacks_text.splitlines():
        stripped = line.strip()
        if '"asm_functions_by_name"' in stripped:
            in_block = True
            continue
        if in_block:
            if stripped.startswith("]"):
                break
            if stripped.startswith("//"):
                continue
            m = re.match(r'^"([^"]+)"', stripped)
            if m:
                entries.add(m.group(1))
    return entries


def apply_to_hacks(hacks_text: str, new_entries: list[tuple[str, str]]) -> str:
    """Insert new entries into mips2c_functions_by_name and return modified text.

    Strategy: find the last real (non-comment) entry before the closing ']',
    add a comma after it, then append the new entries with a comment header.
    """
    lines = hacks_text.splitlines(keepends=True)

    # Find the mips2c_functions_by_name block end (closing ']')
    mips2c_start = -1
    for i, line in enumerate(lines):
        if '"mips2c_functions_by_name"' in line:
            mips2c_start = i
            break
    if mips2c_start < 0:
        raise ValueError("mips2c_functions_by_name not found in hacks.jsonc")

    # Find closing ']' after mips2c_start
    close_bracket_line = -1
    for i in range(mips2c_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("]"):
            close_bracket_line = i
            break
    if close_bracket_line < 0:
        raise ValueError("Could not find closing ] for mips2c_functions_by_name")

    # Find the last non-comment, non-empty entry before close_bracket_line
    last_entry_line = -1
    for i in range(close_bracket_line - 1, mips2c_start, -1):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
            # Check if this line contains a quoted string (actual entry)
            if re.search(r'"[^"]+"', stripped):
                last_entry_line = i
                break

    if last_entry_line >= 0:
        # Ensure the last entry has a comma
        last_line = lines[last_entry_line].rstrip("\n\r")
        if not last_line.rstrip().endswith(","):
            lines[last_entry_line] = last_line.rstrip() + ",\n"

    # Build new lines to insert before the closing bracket
    timestamp = __import__("datetime").date.today().isoformat()
    new_lines = [f"    // asm-func: auto-added by asm_func_apply.py {timestamp}\n"]

    # Group by source file for readable output
    by_file: dict[str, list[str]] = {}
    for key, src in new_entries:
        by_file.setdefault(src, []).append(key)

    entries_written = 0
    for src in sorted(by_file):
        new_lines.append(f"    // source: {src}\n")
        for key in sorted(by_file[src]):
            entries_written += 1
            new_lines.append(f'    "{key}",\n')

    # Remove trailing comma on the very last added entry (keep JSON valid)
    if new_lines:
        last_new = new_lines[-1].rstrip()
        if last_new.endswith(","):
            new_lines[-1] = last_new[:-1] + "\n"

    # Insert before closing bracket
    lines[close_bracket_line:close_bracket_line] = new_lines

    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Print candidates without modifying hacks.jsonc (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Write candidates to mips2c_functions_by_name")
    parser.add_argument("--batch-size", type=int, default=0,
                        help="Cap new entries at N (0 = unlimited)")
    parser.add_argument("--skip-asm", action="store_true",
                        help="Skip functions already in asm_functions_by_name")
    parser.add_argument("--only-asm", action="store_true",
                        help="Only process functions already in asm_functions_by_name")
    parser.add_argument("--decomp-out", default=None,
                        help="Override decomp_out directory path")
    args = parser.parse_args()

    if args.apply:
        args.dry_run = False

    decomp_dir = pick_decomp_dir(args.decomp_out)
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out dir not found: {decomp_dir}", file=sys.stderr)
        return 1

    if not HACKS_JSONC.exists():
        print(f"ERROR: hacks.jsonc not found: {HACKS_JSONC}", file=sys.stderr)
        return 1

    print(f"decomp_out: {decomp_dir}")

    # Step 1: identify VU-crash files
    vu_files = scan_vu_files(decomp_dir)
    if vu_files:
        print(f"VU-crash files (skipped): {sorted(vu_files)}")

    # Step 2: parse 'not converted' functions from disasm files
    candidates = parse_not_converted(decomp_dir, vu_files)
    print(f"Total 'not converted' candidates: {len(candidates)}")

    # Step 3: load existing sets from hacks.jsonc
    hacks_text = HACKS_JSONC.read_text()
    existing_mips2c = load_existing_mips2c(hacks_text)
    existing_asm = load_existing_asm(hacks_text)

    print(f"Already in mips2c_functions_by_name: {len(existing_mips2c)}")
    print(f"Currently in asm_functions_by_name: {len(existing_asm)}")

    # Step 4: filter
    new_entries: list[tuple[str, str]] = []
    skipped_mips2c = 0
    skipped_asm_filter = 0

    for key, src in candidates:
        if key in existing_mips2c:
            skipped_mips2c += 1
            continue
        is_asm = key in existing_asm
        if args.skip_asm and is_asm:
            skipped_asm_filter += 1
            continue
        if args.only_asm and not is_asm:
            continue
        new_entries.append((key, src))

    print(f"Skipped (already mips2c): {skipped_mips2c}")
    if args.skip_asm:
        print(f"Skipped (in asm_functions_by_name, --skip-asm): {skipped_asm_filter}")
    print(f"New candidates to add: {len(new_entries)}")

    # Step 5: apply batch size cap
    if args.batch_size > 0 and len(new_entries) > args.batch_size:
        print(f"Capping at --batch-size {args.batch_size}")
        new_entries = new_entries[: args.batch_size]

    if not new_entries:
        print("Nothing to add.")
        return 0

    # Step 6: print or apply
    print()
    print(f"{'DRY-RUN: would add' if args.dry_run else 'Adding'} {len(new_entries)} entries:")
    by_file: dict[str, list[str]] = {}
    for key, src in new_entries:
        by_file.setdefault(src, []).append(key)
    for src in sorted(by_file):
        print(f"  [{src}]")
        for key in sorted(by_file[src]):
            marker = "(asm)" if key in existing_asm else ""
            print(f"    {key!r}  {marker}")

    if args.dry_run:
        print()
        print("Run with --apply to write to hacks.jsonc.")
        return 0

    # Apply
    new_text = apply_to_hacks(hacks_text, new_entries)
    HACKS_JSONC.write_text(new_text)
    print()
    print(f"Written {len(new_entries)} new entries to {HACKS_JSONC.relative_to(ROOT)}")
    print("Next: JAKX_WATCH_WAIT=1 bash scripts/jakx_watch/run.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
