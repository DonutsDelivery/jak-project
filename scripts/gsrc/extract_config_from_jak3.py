#!/usr/bin/env python3
"""extract_config_from_jak3.py — backport decompiler config from jak3 to jakx.

USAGE
-----
  # Dry-run (default): show what would be ported
  python3 scripts/gsrc/extract_config_from_jak3.py --functions "(method 12 blit-displays-work)" "(method 27 ocean)"

  # Show unified diff of proposed changes
  python3 scripts/gsrc/extract_config_from_jak3.py --functions-file fns.txt --dry-run-diff

  # Apply changes to jakx config files
  python3 scripts/gsrc/extract_config_from_jak3.py --functions-file fns.txt --apply

  # Port label_types by file name (not function name)
  python3 scripts/gsrc/extract_config_from_jak3.py --files "blit-displays" "ocean-transition"

  # Port all missing label_types entries (bulk mode)
  python3 scripts/gsrc/extract_config_from_jak3.py --port-all-label-types [--apply]

  # Port all missing define-extern signatures from jak3 all-types.gc (bulk mode)
  python3 scripts/gsrc/extract_config_from_jak3.py --port-define-externs [--apply]

Run from the repo root (same convention as update-from-decomp.py).

OUTPUT FORMAT (grep-friendly)
------
  STATUS|LANE|KEY|DETAIL
  PORTED|type_casts|(method 12 blit-displays-work)|copied from jak3
  SKIPPED-EXISTS|stack_structures|(method 28 ocean)|jakx already has non-empty entry
  NOT-IN-JAK3|type_casts|my-jakx-only-fn|no jak3 entry
  EMPTY-OVERWRITE|stack_structures|(method 28 ocean)|jakx had [] — replaced with jak3 value

JSONC HANDLING
--------------
Standard json module is used after stripping `//` line-comments. Comments in the
existing file content are PRESERVED: when applying changes we splice new entries
directly into the raw file text (insert before the closing `}`) rather than
reserializing the whole file. This keeps all existing `//` comments intact.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------
REPO = Path(__file__).parent.parent.parent
JAK3_CFG = REPO / "decompiler/config/jak3/ntsc_v1"
JAKX_CFG = REPO / "decompiler/config/jakx/ntsc_v1"
JAK3_ALLTYPES = REPO / "decompiler/config/jak3/all-types.gc"
JAKX_ALLTYPES = REPO / "decompiler/config/jakx/all-types.gc"

CONFIG_FILES = [
    ("type_casts",      "type_casts.jsonc"),
    ("stack_structures","stack_structures.jsonc"),
    ("label_types",     "label_types.jsonc"),
]


# ---------------------------------------------------------------------------
# JSONC helpers
# ---------------------------------------------------------------------------

def _strip_line_comments(text: str) -> str:
    """Strip // line comments from JSONC text (does not touch strings)."""
    out = []
    for line in text.splitlines():
        # Naive: strip from // not inside a string.  Good enough for these files.
        # We handle the common case: the comment is the only thing on the line
        # or appears after a value.  String values in these files don't contain //.
        result = []
        in_str = False
        i = 0
        while i < len(line):
            c = line[i]
            if c == '"' and (i == 0 or line[i-1] != '\\'):
                in_str = not in_str
            if not in_str and c == '/' and i + 1 < len(line) and line[i+1] == '/':
                break
            result.append(c)
            i += 1
        out.append(''.join(result).rstrip())
    return '\n'.join(out)


def load_jsonc(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding='utf-8', errors='replace')
    stripped = _strip_line_comments(text)
    return json.loads(stripped)


def _is_empty_value(val: Any) -> bool:
    """Return True if the value is an empty list/dict (placeholder)."""
    if isinstance(val, list) and len(val) == 0:
        return True
    if isinstance(val, dict) and len(val) == 0:
        return True
    return False


# ---------------------------------------------------------------------------
# File-patching (comment-preserving insert)
# ---------------------------------------------------------------------------

def _format_new_entry(key: str, value: Any) -> str:
    """Format a single key-value pair as a compact JSON entry string (no trailing comma)."""
    key_json = json.dumps(key)
    value_json = json.dumps(value, separators=(', ', ': '))
    # For readability, use the compact single-line format jak3 uses:
    return f'  {key_json}: {value_json}'


def _splice_entries_into_file(file_path: Path, new_entries: List[Tuple[str, Any]]) -> Tuple[str, str]:
    """
    Insert new_entries into a JSONC file before its closing `}`.
    Returns (original_text, new_text).
    Raises ValueError if the file doesn't end with `}`.
    """
    original = file_path.read_text(encoding='utf-8', errors='replace')
    # Find the last `}` in the file (the closing brace of the top-level object)
    rpos = original.rfind('}')
    if rpos == -1:
        raise ValueError(f"No closing `}}` found in {file_path}")

    # Everything before the last }
    before = original[:rpos]

    # The last non-whitespace character before `}` — we need to add a comma after it
    # if the file currently ends with a value (not already has trailing comma).
    stripped_before = before.rstrip()
    if not stripped_before.endswith(','):
        # Add trailing comma to last entry
        # Find where stripped_before ends in `before`
        insert_comma_at = len(stripped_before)
        before = before[:insert_comma_at] + ',' + before[insert_comma_at:]

    # Build the new entries block
    entry_lines = []
    for i, (k, v) in enumerate(new_entries):
        line = _format_new_entry(k, v)
        if i < len(new_entries) - 1:
            line += ','
        entry_lines.append(line)
    entries_block = '\n'.join(entry_lines)

    new_text = before + '\n' + entries_block + '\n}'
    return original, new_text


# ---------------------------------------------------------------------------
# Core lookup / comparison logic
# ---------------------------------------------------------------------------

def check_key(
    lane: str,
    key: str,
    j3_data: Dict,
    jx_data: Dict,
) -> Tuple[str, Any]:
    """
    Compare jak3 vs jakx for a single key in a config lane.
    Returns (status, value_to_port) where status is one of:
      PORTED            — jak3 has it, jakx doesn't (or jakx has empty [])
      EMPTY-OVERWRITE   — jakx had an empty value; will replace
      SKIPPED-EXISTS    — jakx already has a non-empty value
      NOT-IN-JAK3       — key not found in jak3
    value_to_port is the jak3 value (or None if NOT-IN-JAK3 / SKIPPED-EXISTS).
    """
    if key not in j3_data:
        return ('NOT-IN-JAK3', None)
    j3_val = j3_data[key]
    if key not in jx_data:
        return ('PORTED', j3_val)
    jx_val = jx_data[key]
    if _is_empty_value(jx_val):
        return ('EMPTY-OVERWRITE', j3_val)
    return ('SKIPPED-EXISTS', None)


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------

def process_keys(
    lane: str,
    config_file: str,
    keys: List[str],
    apply: bool,
    dry_run_diff: bool,
) -> List[Tuple[str, str, str, str]]:
    """
    Process a list of keys for one config lane (type_casts, stack_structures, label_types).
    Returns list of (status, lane, key, detail) tuples.
    """
    j3_path = JAK3_CFG / config_file
    jx_path = JAKX_CFG / config_file

    if not j3_path.exists():
        return [('ERROR', lane, k, f'jak3 file not found: {j3_path}') for k in keys]
    if not jx_path.exists():
        return [('ERROR', lane, k, f'jakx file not found: {jx_path}') for k in keys]

    j3_data = load_jsonc(j3_path)
    jx_data = load_jsonc(jx_path)

    results = []
    to_insert: List[Tuple[str, Any]] = []  # (key, value) to add to jakx

    for key in keys:
        status, value = check_key(lane, key, j3_data, jx_data)
        detail = {
            'PORTED': 'copied from jak3',
            'EMPTY-OVERWRITE': 'jakx had [] — replaced with jak3 value',
            'SKIPPED-EXISTS': 'jakx already has non-empty entry',
            'NOT-IN-JAK3': 'no jak3 entry',
        }.get(status, '')
        results.append((status, lane, key, detail))
        if status in ('PORTED', 'EMPTY-OVERWRITE') and value is not None:
            to_insert.append((key, value))

    if not to_insert:
        return results

    if dry_run_diff or apply:
        original, new_text = _splice_entries_into_file(jx_path, to_insert)
        if dry_run_diff:
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f'a/{jx_path.relative_to(REPO)}',
                tofile=f'b/{jx_path.relative_to(REPO)}',
            )
            sys.stdout.writelines(diff)
        if apply:
            jx_path.write_text(new_text, encoding='utf-8')

    return results


# ---------------------------------------------------------------------------
# define-extern porting (all-types.gc)
# ---------------------------------------------------------------------------

def parse_define_externs(path: Path) -> Dict[str, str]:
    """Parse (define-extern NAME TYPE) lines from an all-types.gc file.
    Returns {name: type_sig_string}.
    The outer parens of `(define-extern NAME TYPE)` are stripped; TYPE is returned as-is.
    """
    result = {}
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip()
            # Match: (define-extern NAME TYPE) with optional trailing ;; comment
            # The closing ) is the define-extern's own closing paren.
            m = re.match(r'^\(define-extern\s+(\S+)\s+(.+)\)\s*(?:;;.*)?$', line.strip())
            if m:
                name = m.group(1)
                type_sig = m.group(2).strip()
                result[name] = type_sig
    return result


def port_define_externs(apply: bool, dry_run_diff: bool) -> List[Tuple[str, str, str, str]]:
    """
    Port define-extern function signatures from jak3 all-types.gc to jakx,
    where jakx has a placeholder `(function none)` and jak3 has a real signature.
    """
    j3_de = parse_define_externs(JAK3_ALLTYPES)
    jx_de = parse_define_externs(JAKX_ALLTYPES)

    results = []
    replacements: List[Tuple[str, str, str]] = []  # (name, old_line, new_line)

    for name, j3_sig in sorted(j3_de.items()):
        if name not in jx_de:
            results.append(('NOT-IN-JAKX', 'define-extern', name, 'not in jakx all-types.gc'))
            continue
        jx_sig = jx_de[name]
        # Only port if jak3 has a real function sig and jakx has a placeholder
        if not j3_sig.startswith('(function'):
            continue
        if j3_sig == '(function none)':
            continue
        if jx_sig == '(function none)' or jx_sig == 'object':
            replacements.append((name, jx_sig, j3_sig))
            results.append(('PORTED', 'define-extern', name,
                             f'jak3={j3_sig}  jakx_was={jx_sig}'))
        else:
            results.append(('SKIPPED-EXISTS', 'define-extern', name,
                             f'jakx has real sig: {jx_sig}'))

    if not replacements:
        return results

    if dry_run_diff or apply:
        original = JAKX_ALLTYPES.read_text(encoding='utf-8', errors='replace')
        new_text = original
        for name, old_sig, new_sig in replacements:
            # Replace the first occurrence of `(define-extern NAME old_sig)` line.
            # Format in file: (define-extern NAME TYPE)
            # parse_define_externs strips the outer ) so old_sig/new_sig don't include it.
            # Replacement: keep `(define-extern NAME `, insert new type, close with `)`.
            # Group 1 = `(define-extern NAME `, group 2 = trailing comment or EOL.
            old_pat = re.compile(
                r'^(\(define-extern\s+' + re.escape(name) + r'\s+)' +
                re.escape(old_sig) + r'\)(\s*(?:;;.*)?)$',
                re.MULTILINE
            )
            new_line_repl = r'\g<1>' + new_sig + r')\g<2>'
            new_text, n = old_pat.subn(new_line_repl, new_text, count=1)
            if n == 0:
                # Try matching with 'object' placeholder (no parens, no extra closing))
                old_pat2 = re.compile(
                    r'^(\(define-extern\s+' + re.escape(name) + r'\s+)object\)(\s*(?:;;.*)?)$',
                    re.MULTILINE
                )
                new_text, n2 = old_pat2.subn(new_line_repl, new_text, count=1)

        if dry_run_diff:
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f'a/decompiler/config/jakx/all-types.gc',
                tofile=f'b/decompiler/config/jakx/all-types.gc',
            )
            sys.stdout.writelines(diff)
        if apply:
            JAKX_ALLTYPES.write_text(new_text, encoding='utf-8')

    return results


# ---------------------------------------------------------------------------
# Bulk label_types porting
# ---------------------------------------------------------------------------

def port_all_label_types(apply: bool, dry_run_diff: bool) -> List[Tuple[str, str, str, str]]:
    """Port ALL missing label_types entries from jak3 to jakx (bulk mode)."""
    j3_path = JAK3_CFG / "label_types.jsonc"
    jx_path = JAKX_CFG / "label_types.jsonc"
    j3_data = load_jsonc(j3_path)
    jx_data = load_jsonc(jx_path)

    keys_to_port = [k for k in j3_data if k not in jx_data]
    results = []
    for k in keys_to_port:
        results.append(('PORTED', 'label_types', k, f'{len(j3_data[k])} label entries'))
    for k in jx_data:
        if k in j3_data:
            results.append(('SKIPPED-EXISTS', 'label_types', k, 'already in jakx'))

    to_insert = [(k, j3_data[k]) for k in keys_to_port]
    if to_insert and (apply or dry_run_diff):
        original, new_text = _splice_entries_into_file(jx_path, to_insert)
        if dry_run_diff:
            diff = difflib.unified_diff(
                original.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f'a/{jx_path.relative_to(REPO)}',
                tofile=f'b/{jx_path.relative_to(REPO)}',
            )
            sys.stdout.writelines(diff)
        if apply:
            jx_path.write_text(new_text, encoding='utf-8')

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Backport jak3 decompiler config entries to jakx."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--functions', nargs='+', metavar='FN',
                       help='Function names to look up (e.g. "(method 12 blit-displays-work)")')
    group.add_argument('--functions-file', metavar='PATH',
                       help='File with one function name per line')

    group2 = parser.add_mutually_exclusive_group()
    group2.add_argument('--files', nargs='+', metavar='FILE',
                        help='File/label_types keys to look up (e.g. "blit-displays")')
    group2.add_argument('--files-file', metavar='PATH',
                        help='File with one file name per line')

    parser.add_argument('--apply', action='store_true',
                        help='Write changes to jakx config files (default: dry-run)')
    parser.add_argument('--dry-run-diff', action='store_true',
                        help='Show unified diff of proposed changes')
    parser.add_argument('--port-all-label-types', action='store_true',
                        help='Bulk-port ALL missing label_types entries from jak3')
    parser.add_argument('--port-define-externs', action='store_true',
                        help='Port define-extern function signatures from jak3 all-types.gc')

    args = parser.parse_args()

    all_results = []

    # --- Bulk modes ---
    if args.port_all_label_types:
        results = port_all_label_types(apply=args.apply, dry_run_diff=args.dry_run_diff)
        all_results.extend(results)

    if args.port_define_externs:
        results = port_define_externs(apply=args.apply, dry_run_diff=args.dry_run_diff)
        all_results.extend(results)

    # --- Function-based lookup ---
    functions: List[str] = []
    if args.functions:
        functions = args.functions
    elif args.functions_file:
        functions = [l.strip() for l in Path(args.functions_file).read_text().splitlines()
                     if l.strip() and not l.startswith('#')]

    if functions:
        for lane, config_file in CONFIG_FILES:
            # label_types is keyed by file name (no parens). Functions with parens
            # won't match label_types — skip to avoid spurious NOT-IN-JAK3 noise.
            if lane == 'label_types':
                continue
            results = process_keys(lane, config_file, functions, args.apply, args.dry_run_diff)
            all_results.extend(results)

    # --- File/label_types lookup ---
    file_names: List[str] = []
    if args.files:
        file_names = args.files
    elif args.files_file:
        file_names = [l.strip() for l in Path(args.files_file).read_text().splitlines()
                      if l.strip() and not l.startswith('#')]

    if file_names:
        results = process_keys('label_types', 'label_types.jsonc', file_names,
                               args.apply, args.dry_run_diff)
        all_results.extend(results)

    # --- Report ---
    if not all_results:
        print("No keys to process. Use --functions, --files, --port-all-label-types, or --port-define-externs.")
        return

    for status, lane, key, detail in all_results:
        print(f'{status}|{lane}|{key}|{detail}')

    # Summary counters
    from collections import Counter
    counts = Counter(status for status, _, _, _ in all_results)
    print()
    print(f'# SUMMARY: PORTED={counts["PORTED"]} EMPTY-OVERWRITE={counts["EMPTY-OVERWRITE"]} '
          f'SKIPPED-EXISTS={counts["SKIPPED-EXISTS"]} NOT-IN-JAK3={counts["NOT-IN-JAK3"]} '
          f'ERROR={counts["ERROR"]} NOT-IN-JAKX={counts["NOT-IN-JAKX"]}')
    if args.apply:
        print('# Changes written to jakx config.')
    elif not args.dry_run_diff:
        print('# DRY-RUN: pass --apply to write changes.')


if __name__ == '__main__':
    main()
