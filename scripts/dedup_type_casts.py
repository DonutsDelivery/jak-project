#!/usr/bin/env python3
"""Deduplicate function-name keys in type_casts.jsonc.

Merges all cast entries from duplicate keys into a single entry,
keeping unique entries (no duplicate cast triples), at the last
occurrence's position.

IMPORTANT: When entries conflict (same op+reg, different type), the
entry from the LAST occurrence wins (preserving pre-merge behavior).
"""

import re
import json
from collections import OrderedDict


def find_block_end(lines, start_lineno):
    depth = 0
    for i in range(start_lineno, len(lines)):
        for ch in lines[i]:
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    return i
    return len(lines) - 1


def extract_entries(text):
    entries = []
    i = 0
    while i < len(text):
        idx = text.find('[', i)
        if idx == -1:
            break
        depth = 0
        for j in range(idx, len(text)):
            if text[j] == '[':
                depth += 1
            elif text[j] == ']':
                depth -= 1
                if depth == 0:
                    entry_text = text[idx:j + 1]
                    try:
                        parsed = json.loads(entry_text)
                        if isinstance(parsed, list) and len(parsed) == 3:
                            entries.append(parsed)
                    except (ValueError, json.JSONDecodeError):
                        pass
                    i = j + 1
                    break
        else:
            break
    return entries


def serialize_entry(entry, is_last=False):
    comma = '' if is_last else ','
    ops, reg, typ = entry
    if isinstance(ops, str) and ops == '_stack_':
        return f"    [\"_stack_\", {reg}, \"{typ}\"]{comma}\n"
    if isinstance(ops, list):
        return f"    [[{ops[0]},{ops[1]}], \"{reg}\", \"{typ}\"]{comma}\n"
    else:
        return f"    [{ops}, \"{reg}\", \"{typ}\"]{comma}\n"


def entry_sort_key(entry):
    ops, reg, typ = entry
    if isinstance(ops, str):
        return (-1, 0, reg, typ)
    if isinstance(ops, list):
        return (ops[0], 1, str(ops), reg, typ)
    return (ops, 2, reg, typ)


def entry_identity(entry):
    """Identity tuple for conflict detection: (op_repr, reg)"""
    ops, reg, typ = entry
    if isinstance(ops, list):
        op_repr = f"[{ops[0]},{ops[1]}]"
    else:
        op_repr = str(ops)
    return (op_repr, reg)


def main():
    path = 'decompiler/config/jakx/ntsc_v1/type_casts.jsonc'
    with open(path, 'r') as f:
        lines = f.readlines()

    blocks = []
    i = 0
    while i < len(lines):
        comment_lines = []
        j = i
        while j < len(lines) and lines[j].strip().startswith('//'):
            comment_lines.append(j)
            j += 1

        if j < len(lines) and re.match(r'^\s{2}"[^"]+"\s*:\s*\[$', lines[j]):
            key_match = re.match(r'^\s{2}"([^"]+)"\s*:\s*\[$', lines[j])
            if key_match:
                key = key_match.group(1)
                key_lineno = j
                end_lineno = find_block_end(lines, j)
                block_text = ''.join(lines[j + 1:end_lineno])
                entries = extract_entries(block_text)
                blocks.append({
                    'key': key,
                    'key_lineno': key_lineno,
                    'end_lineno': end_lineno,
                    'comment_lines': comment_lines,
                    'entries': entries,
                    'lines_slice': (comment_lines[0] if comment_lines else key_lineno,
                                    end_lineno + 1)
                })
                i = end_lineno + 1
                continue
        if not comment_lines:
            i += 1
        else:
            i = comment_lines[-1] + 1

    print(f"Parsed {len(blocks)} blocks")

    key_to_blocks = OrderedDict()
    for blk in blocks:
        key_to_blocks.setdefault(blk['key'], []).append(blk)

    dups = {k: v for k, v in key_to_blocks.items() if len(v) > 1}
    print(f"Duplicate keys: {len(dups)}")

    if not dups:
        print("No duplicates found.")
        return

    # Report lost entries AND conflicts
    total_conflicts = 0
    for key, blks in sorted(dups.items()):
        entry_sets = [set(tuple(map(str, e)) for e in blk['entries']) for blk in blks]
        last_set = entry_sets[-1]
        for idx, eset in enumerate(entry_sets[:-1]):
            lost = eset - last_set
            if lost:
                print(f"\n  '{key}' (occ {idx+1}) loses {len(lost)} entries:")
                for e in sorted(lost):
                    print(f"    - {e}")

        # Detect conflicts: same op+reg, different type
        seen = {}
        for blk in blks:
            for e in blk['entries']:
                eid = entry_identity(e)
                if eid in seen and seen[eid] != list(e):
                    total_conflicts += 1
                    if total_conflicts <= 5:
                        print(f"  CONFLICT in '{key}': {eid} → '{seen[eid][2]}' vs '{e[2]}'")
                seen[eid] = list(e)

    if total_conflicts:
        print(f"\n  Total conflicts: {total_conflicts}")

    # Mark lines to remove
    remove_set = set()
    for key, blks in dups.items():
        for blk in blks[:-1]:
            start, end_excl = blk['lines_slice']
            for x in range(start, end_excl):
                remove_set.add(x)

    # Merge entries: for each (op, reg) pair, prefer the LAST block's type
    for key, blks in dups.items():
        # Merge in order: previous blocks first, then last block
        # (last block's entries overwrite conflicts)
        merged = OrderedDict()
        for blk in blks:
            for entry in blk['entries']:
                eid = entry_identity(entry)
                merged[eid] = list(entry)

        sorted_entries = sorted(merged.values(), key=entry_sort_key)
        blks[-1]['merged_entries'] = sorted_entries

    # Build output
    new_lines = []
    replaced_keys = set()
    i = 0
    while i < len(lines):
        if i in remove_set:
            i += 1
            continue
        replaced = False
        for key, blks in dups.items():
            last_blk = blks[-1]
            if i == last_blk['key_lineno'] and key not in replaced_keys:
                replaced_keys.add(key)
                replaced = True
                for cl in last_blk['comment_lines']:
                    if cl not in remove_set:
                        new_lines.append(lines[cl])
                new_lines.append(lines[i])
                entries = last_blk['merged_entries']
                for idx, entry in enumerate(entries):
                    is_last = (idx == len(entries) - 1)
                    new_lines.append(serialize_entry(entry, is_last))
                new_lines.append(lines[last_blk['end_lineno']])
                i = last_blk['end_lineno'] + 1
                break
        if not replaced:
            new_lines.append(lines[i])
            i += 1

    out_path = path + '.new'
    with open(out_path, 'w') as f:
        f.writelines(new_lines)

    import os
    os.rename(out_path, path)
    print(f"\nFile updated")
    print(f"Removed {len(remove_set)} lines, {len(dups)} keys merged")

    # Verify no remaining duplicates
    with open(path) as f:
        content = f.read()
    rem_dups = 0
    for key in dups:
        matches = list(re.finditer(r'^\s{2}"' + re.escape(key) + r'"\s*:', content, re.MULTILINE))
        if len(matches) > 1:
            rem_dups += 1
            print(f"  WARNING: '{key}' still has {len(matches)} occurrences!")
    if rem_dups == 0:
        print("All duplicates resolved.")


if __name__ == '__main__':
    main()
