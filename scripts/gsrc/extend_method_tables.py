#!/usr/bin/env python3
"""
extend_method_tables.py - Extend method tables in all-types.gc to eliminate decompiler errors.

Walks decompiler_out/jakx/*_ir2.asm, collects every
    ;; ERROR: Function (method N TYPE) has unknown type
line, then for each TYPE, adds stub method declarations for any slot not already
declared in that type's deftype block in decompiler/config/jakx/all-types.gc.

If max-error-slot >= method-count-assert for a type, also bumps method-count-assert
and flag-assert to max-error-slot + 1.

Usage:
    python3 scripts/gsrc/extend_method_tables.py [--dry-run] [--worktree /path]

Flags:
    --dry-run     Print changes but don't write all-types.gc
    --worktree    Path to the jak-project worktree (default: current directory)
"""

import argparse
import glob
import re
import sys
from collections import defaultdict
from pathlib import Path


def collect_errors(ir2_dir: Path) -> dict[str, set[int]]:
    """Walk ir2.asm files and collect method-type errors per type."""
    error_map: dict[str, set[int]] = defaultdict(set)
    pattern = re.compile(
        r'^;; ERROR: Function \(method (\d+) ([^\)]+)\) has unknown type'
    )
    ir2_files = sorted(ir2_dir.glob('*_ir2.asm'))
    if not ir2_files:
        print(f"WARNING: No *_ir2.asm files found in {ir2_dir}", file=sys.stderr)
    for f in ir2_files:
        with open(f, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = pattern.match(line)
                if m:
                    method_n = int(m.group(1))
                    typename = m.group(2)
                    error_map[typename].add(method_n)
    return dict(error_map)


def parse_all_types(all_types_path: Path) -> tuple[str, list[tuple[int, str, int, str | None]]]:
    """
    Parse all-types.gc and return (full_content, deftype_spans).
    deftype_spans: list of (start_offset, typename, end_offset, parent_typename)
    End offset is the character position just after the closing ')' of the deftype.
    parent_typename may be None if not parseable.
    """
    with open(all_types_path, encoding='utf-8') as f:
        content = f.read()

    # Find all deftype start positions, EXCLUDING commented-out deftypes.
    # A deftype is "commented out" if the "(deftype" token appears after ";;" on the same line,
    # meaning it's in a line comment and should not be parsed as a real type definition.
    deftype_re = re.compile(r'\(deftype\s+(\S+)\s+\((\S+)\)')
    starts = []
    for m in deftype_re.finditer(content):
        # Find the start of the current line
        line_start = content.rfind('\n', 0, m.start()) + 1
        line_text = content[line_start:m.start()]
        # If there's a ";;" before the "(deftype" on this line, it's a comment — skip it.
        if ';;' in line_text:
            continue
        # Also skip if inside a block comment (#| ... |#).
        # Simple heuristic: count #| and |# before this position.
        before = content[:m.start()]
        block_opens = before.count('#|')
        block_closes = before.count('|#')
        if block_opens > block_closes:
            continue
        starts.append((m.start(), m.group(1), m.group(2)))

    spans = []
    for i, (start, typename, parent) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(content)
        spans.append((start, typename, end, parent))

    return content, spans


def get_declared_slots(block: str) -> set[int]:
    """
    Extract all declared method slot numbers from a deftype block.
    Looks for ;; N patterns used to annotate method declarations.
    Handles trailing ')' in case a closing paren got merged into the comment line.
    """
    declared = set()
    # Match ";; N" followed by whitespace, end of line, dash, or closing paren
    for m in re.finditer(r';;\s*(\d+)(?:\s|\)|-|$)', block):
        declared.add(int(m.group(1)))
    return declared


def get_mca(block: str) -> int | None:
    """Extract :method-count-assert value from a deftype block."""
    m = re.search(r':method-count-assert\s+(\d+)', block)
    return int(m.group(1)) if m else None


def get_flag_assert(block: str) -> tuple[str, int] | tuple[None, None]:
    """Return (raw_hex_string, int_value) of :flag-assert from block."""
    m = re.search(r':flag-assert\s+(#x[0-9a-fA-F]+)', block)
    if not m:
        return None, None
    raw = m.group(1)
    # Strip the #x prefix for int conversion
    hex_val = raw[2:]  # remove '#x'
    return raw, int(hex_val, 16)


def update_flag_assert(old_flag: int, new_mca: int) -> str:
    """
    Update the MCA portion of flag-assert.
    Format: (mca << 32) | (lower 32 bits unchanged)
    The upper byte of the 40-bit value is the MCA.
    """
    lower = old_flag & 0x00FFFFFFFF
    new_flag = (new_mca << 32) | lower
    return f"#x{new_flag:x}"


def find_last_methods_block_end(block: str) -> int | None:
    """
    Find the character offset within `block` of the closing ')' of the
    LAST (:methods ...) block in this deftype. Returns None if no :methods block.

    We look for the last occurrence of '(:methods' and find its matching close paren.
    """
    # Find all (:methods occurrences
    positions = [m.start() for m in re.finditer(r'\(:methods\b', block)]
    if not positions:
        return None

    # Use the last one
    start = positions[-1]

    # Find matching close paren by counting parens
    depth = 0
    for i in range(start, len(block)):
        if block[i] == '(':
            depth += 1
        elif block[i] == ')':
            depth -= 1
            if depth == 0:
                return i  # position of the closing ) of the (:methods block

    return None


def find_deftype_body_end(block: str) -> int | None:
    """
    Find the character offset of the closing ')' of the entire deftype block.
    This is the OUTERMOST closing paren.
    The block starts with '(deftype ...'.
    """
    depth = 0
    for i in range(len(block)):
        if block[i] == '(':
            depth += 1
        elif block[i] == ')':
            depth -= 1
            if depth == 0:
                return i
    return None


def generate_stubs(typename: str, missing_slots: list[int]) -> str:
    """Generate stub method declarations for the given slots."""
    lines = []
    for slot in sorted(missing_slots):
        stub_name = f"{typename}-method-{slot}"
        lines.append(f"    ({stub_name} () none) ;; {slot}")
    return '\n'.join(lines)


def update_mca_only(
    content: str,
    block_start: int,
    block_end: int,
    old_mca: int,
    new_mca: int,
    old_flag_raw: str | None,
    old_flag_int: int | None,
    dry_run: bool,
    typename: str = '',
) -> str:
    """
    Update only the :method-count-assert and :flag-assert for a type,
    without adding any stub methods. Used for cascading MCA updates when
    a parent type's MCA was bumped.

    Uses content-search (not fixed offsets) to handle shifts from prior edits.
    Searches for the deftype block by looking for the deftype header near block_start,
    then replacing within a window around it.
    """
    # Find the actual current position of this type's deftype in the (possibly shifted) content.
    # We search for a unique anchor: "(deftype TYPENAME " near the expected position,
    # allowing for up to 5000 chars of shift from prior insertions.
    anchor = f'(deftype {typename} '
    search_start = max(0, block_start - 5000)
    search_end = min(len(content), block_end + 5000)
    window = content[search_start:search_end]
    anchor_idx = window.find(anchor)

    if anchor_idx == -1:
        print(f"  WARNING: Cannot find '{anchor}' near offset {block_start}, skipping", file=sys.stderr)
        return content

    # The actual block start in content
    actual_block_start = search_start + anchor_idx
    # Use a generous window for the block
    actual_window = content[actual_block_start:actual_block_start + (block_end - block_start) + 5000]

    old_mca_str = f':method-count-assert {old_mca}'
    new_mca_str = f':method-count-assert {new_mca}'
    if dry_run:
        print(f"  Would update mca: {old_mca} -> {new_mca}")
    else:
        idx = actual_window.find(old_mca_str)
        if idx != -1:
            abs_idx = actual_block_start + idx
            content = (
                content[:abs_idx]
                + new_mca_str
                + content[abs_idx + len(old_mca_str):]
            )
            # Recompute window after content modification
            actual_window = content[actual_block_start:actual_block_start + (block_end - block_start) + 5000]

    if old_flag_raw and old_flag_int is not None:
        new_flag_str = update_flag_assert(old_flag_int, new_mca)
        if dry_run:
            print(f"  Would update flag-assert: {old_flag_raw} -> {new_flag_str}")
        else:
            fa_idx = actual_window.find(f':flag-assert         {old_flag_raw}')
            if fa_idx == -1:
                fa_idx = actual_window.find(f':flag-assert {old_flag_raw}')
            if fa_idx != -1:
                abs_fa_start = actual_block_start + fa_idx + actual_window[fa_idx:].find(old_flag_raw)
                content = (
                    content[:abs_fa_start]
                    + new_flag_str
                    + content[abs_fa_start + len(old_flag_raw):]
                )

    return content


def apply_type_fix(
    content: str,
    block_start: int,
    block_end: int,
    typename: str,
    missing_slots: list[int],
    old_mca: int | None,
    new_mca: int | None,
    old_flag_raw: str | None,
    old_flag_int: int | None,
    dry_run: bool,
) -> str:
    """
    Apply fixes to `content` for one type.
    Returns the updated content string.
    """
    block = content[block_start:block_end]

    stubs_text = generate_stubs(typename, missing_slots)

    # Find where to insert stubs (inside last :methods block, or new block before deftype end)
    last_methods_end = find_last_methods_block_end(block)

    if last_methods_end is not None:
        # Insert stubs before the closing ) of the last :methods block.
        # IMPORTANT: add trailing '\n' so the closing ) lands on its own line,
        # not appended to the last stub line (which would corrupt the ;; N comment).
        abs_insert = block_start + last_methods_end
        insert_text = '\n' + stubs_text + '\n'
        if dry_run:
            print(f"  Would insert {len(missing_slots)} stubs before (:methods) close at offset {abs_insert}")
        else:
            content = content[:abs_insert] + insert_text + content[abs_insert:]
    else:
        # No :methods block exists - insert a new one before the deftype's closing )
        deftype_end = find_deftype_body_end(block)
        if deftype_end is None:
            print(f"  ERROR: Cannot find deftype body end for {typename}", file=sys.stderr)
            return content
        abs_insert = block_start + deftype_end
        # IMPORTANT: add trailing '\n' after the closing ) of the new :methods block
        # so it lands on its own line, not merged with the deftype's closing ).
        insert_text = (
            f"\n  (:methods\n"
            f"{stubs_text}\n"
            f"    )\n"
        )
        if dry_run:
            print(f"  Would insert new (:methods) block with {len(missing_slots)} stubs at offset {abs_insert}")
        else:
            content = content[:abs_insert] + insert_text + content[abs_insert:]

    # Update method-count-assert if needed
    if new_mca is not None and old_mca is not None and new_mca > old_mca:
        old_mca_str = f':method-count-assert {old_mca}'
        new_mca_str = f':method-count-assert {new_mca}'
        if dry_run:
            print(f"  Would update mca: {old_mca} -> {new_mca}")
        else:
            # Only replace the first occurrence in the block (after potential insertion)
            # Find the position in the now-modified content
            block_in_content = content[block_start:block_start + len(block) + 200]
            idx = block_in_content.find(old_mca_str)
            if idx != -1:
                abs_idx = block_start + idx
                content = (
                    content[:abs_idx]
                    + new_mca_str
                    + content[abs_idx + len(old_mca_str):]
                )

        # Update flag-assert: find within the SPECIFIC BLOCK, not globally,
        # to avoid accidentally replacing the same hex value in another type's deftype.
        if old_flag_raw and old_flag_int is not None:
            new_flag_str = update_flag_assert(old_flag_int, new_mca)
            if dry_run:
                print(f"  Would update flag-assert: {old_flag_raw} -> {new_flag_str}")
            else:
                # Find the flag-assert in the block region (after mca update, so block may have shifted)
                # We search for the flag-assert pattern within a window around block_start
                block_window = content[block_start:block_start + len(block) + 400]
                fa_idx = block_window.find(f':flag-assert         {old_flag_raw}')
                if fa_idx == -1:
                    fa_idx = block_window.find(f':flag-assert {old_flag_raw}')
                if fa_idx != -1:
                    abs_fa_start = block_start + fa_idx + block_window[fa_idx:].find(old_flag_raw)
                    content = (
                        content[:abs_fa_start]
                        + new_flag_str
                        + content[abs_fa_start + len(old_flag_raw):]
                    )

    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Print changes, do not write')
    parser.add_argument('--worktree', default='.', help='Path to jak-project worktree')
    args = parser.parse_args()

    worktree = Path(args.worktree).resolve()
    ir2_dir = worktree / 'decompiler_out' / 'jakx'
    all_types_path = worktree / 'decompiler' / 'config' / 'jakx' / 'all-types.gc'

    print(f"Worktree: {worktree}")
    print(f"IR2 dir: {ir2_dir}")
    print(f"all-types.gc: {all_types_path}")
    print()

    # Step 1: Collect errors
    print("Step 1: Collecting errors from ir2.asm files...")
    error_map = collect_errors(ir2_dir)
    total_error_types = len(error_map)
    total_error_slots = sum(len(v) for v in error_map.values())
    print(f"  Found {total_error_types} types with {total_error_slots} distinct error slots")
    print()

    # Step 2: Parse all-types.gc
    print("Step 2: Parsing all-types.gc...")
    content, spans = parse_all_types(all_types_path)
    print(f"  Found {len(spans)} deftype entries, file size {len(content)} chars")
    print()

    # Build type -> span index and parent mapping
    type_to_span: dict[str, tuple[int, int]] = {}
    type_to_parent: dict[str, str | None] = {}
    type_to_mca: dict[str, int | None] = {}
    for start, typename, end, parent in spans:
        # Use last occurrence if duplicate (some types appear commented-out then real)
        type_to_span[typename] = (start, end)
        type_to_parent[typename] = parent

    # Pre-compute MCA for all known types (needed for parent lookup)
    for start, typename, end, parent in spans:
        block = content[start:end]
        type_to_mca[typename] = get_mca(block)

    # Build ancestor chain helper
    def get_ancestors(typename: str) -> list[str]:
        """Return list of ancestor type names from immediate parent upward."""
        result = []
        t = type_to_parent.get(typename)
        while t and t != 'object' and t != 'structure' and t != 'basic':
            result.append(t)
            t = type_to_parent.get(t)
        return result

    # Step 3: Determine fixes needed
    print("Step 3: Computing required fixes...")
    not_found = []
    already_ok = []
    to_fix = []  # (typename, missing_slots, old_mca, new_mca, old_flag_raw, old_flag_int)

    for typename, error_slots in sorted(error_map.items()):
        if typename not in type_to_span:
            not_found.append((typename, sorted(error_slots)))
            continue

        span_start, span_end = type_to_span[typename]
        block = content[span_start:span_end]

        declared = get_declared_slots(block)
        mca = get_mca(block)
        flag_raw, flag_int = get_flag_assert(block)

        # Determine the first sequential slot available in this type.
        # GOAL assigns method IDs sequentially starting from parent_mca.
        # If the parent's MCA is X, this type's first new slot gets ID X.
        # We must fill ALL slots from parent_mca up to max_error_slot (exclusive of
        # already-declared slots) so the sequential numbering aligns with the binary.
        parent_name = type_to_parent.get(typename)
        parent_mca = type_to_mca.get(parent_name) if parent_name else None

        # Slots covered by an ANCESTOR type that is ALSO getting fixed:
        # If ancestor A will receive a stub for slot X, this type inherits it and
        # must NOT declare its own stub for X (that would push it to slot X+1).
        ancestors_in_error_map = [a for a in get_ancestors(typename) if a in error_map]
        ancestor_covered_slots: set[int] = set()
        for anc in ancestors_in_error_map:
            # All slots the ancestor will cover (its error slots + any gap fills)
            anc_errors = error_map[anc]
            anc_parent = type_to_parent.get(anc)
            anc_parent_mca = type_to_mca.get(anc_parent) if anc_parent else None
            if anc_parent_mca is not None:
                anc_max = max(anc_errors)
                ancestor_covered_slots |= set(range(anc_parent_mca, anc_max + 1))
            else:
                ancestor_covered_slots |= anc_errors

        # Build the full set of slots that need stubs.
        # This includes: (a) error slots not yet declared, not covered by ancestors, and
        # (b) any gap slots between parent_mca and the lowest error slot.
        # Exclude slots already covered by ancestor fixes (inheritance will handle them).
        effective_error_slots = error_slots - ancestor_covered_slots
        if not effective_error_slots:
            # All errors covered by ancestors; only need MCA cascade (handled in step 4b)
            # But we still need to ensure the MCA assertion passes. We'll handle in cascade.
            already_ok.append(typename)
            if ancestors_in_error_map:
                print(f"  NOTE: {typename} errors covered by ancestor(s) {ancestors_in_error_map}")
            continue

        max_err = max(effective_error_slots)

        if parent_mca is not None:
            full_needed = set(range(parent_mca, max_err + 1)) - declared - ancestor_covered_slots
            min_err = min(effective_error_slots)
            if min_err > parent_mca:
                gap_slots = set(range(parent_mca, min_err)) - declared - ancestor_covered_slots
                if gap_slots:
                    print(f"  NOTE: {typename} has gap slots {sorted(gap_slots)} (parent {parent_name} MCA={parent_mca}, errors start at {min_err})")
                missing_set = full_needed
            else:
                missing_set = effective_error_slots - declared
        else:
            missing_set = effective_error_slots - declared

        missing = sorted(missing_set)
        if not missing:
            already_ok.append(typename)
            continue

        new_mca = None
        if mca is not None and max_err >= mca:
            new_mca = max_err + 1

        to_fix.append((typename, missing, mca, new_mca, flag_raw, flag_int))

    print(f"  Types NOT found in all-types.gc (skipped): {len(not_found)}")
    for t, slots in not_found:
        print(f"    {t}: slots {slots}")
    print(f"  Types already fully declared (no action needed): {len(already_ok)}")
    print(f"  Types needing fixes: {len(to_fix)}")
    print()

    # Step 4: Apply fixes (sort by span_start DESCENDING so offsets don't shift)
    # We process from end of file to beginning so earlier offsets remain valid
    to_fix_with_pos = []
    for typename, missing, old_mca, new_mca, flag_raw, flag_int in to_fix:
        span_start, span_end = type_to_span[typename]
        to_fix_with_pos.append(
            (span_start, typename, missing, old_mca, new_mca, flag_raw, flag_int)
        )

    # Sort by start position DESCENDING (process from end of file first)
    to_fix_with_pos.sort(key=lambda x: -x[0])

    print(f"Step 4: Applying fixes {'(DRY RUN)' if args.dry_run else ''}...")
    fixed_count = 0
    total_stubs_added = 0
    mca_updated_count = 0
    types_extended = []
    types_mca_bumped = []

    for span_start, typename, missing, old_mca, new_mca, flag_raw, flag_int in to_fix_with_pos:
        span_end = type_to_span[typename][1]

        if not args.dry_run or True:  # always print summary
            stub_count = len(missing)
            mca_note = f" (mca {old_mca}->{new_mca})" if new_mca else ""
            print(f"  {typename}: +{stub_count} stubs{mca_note}")

        content = apply_type_fix(
            content,
            span_start,
            span_end,
            typename,
            missing,
            old_mca,
            new_mca,
            flag_raw,
            flag_int,
            dry_run=args.dry_run,
        )
        fixed_count += 1
        total_stubs_added += len(missing)
        types_extended.append(typename)
        if new_mca:
            mca_updated_count += 1
            types_mca_bumped.append(typename)

    print()
    print(f"Summary:")
    print(f"  Types extended: {fixed_count}")
    print(f"  Total stubs added: {total_stubs_added}")
    print(f"  Types with mca bumped: {mca_updated_count} -> {types_mca_bumped}")
    print(f"  Types skipped (not found): {len(not_found)}")
    print()

    # Step 4b: Cascade MCA updates to subclasses of types whose MCA was bumped.
    # When a parent's MCA increases, all descendants that inherit from it must also
    # have their method-count-assert updated to at least the new parent MCA.
    # (The GOAL type system enforces: child MCA >= parent MCA.)
    #
    # IMPORTANT: After step 4 modifies content (inserting stubs), the span offsets
    # in type_to_span are stale. We re-parse the modified content to get fresh positions.
    if not args.dry_run and types_mca_bumped:
        print("Step 4b: Cascading MCA updates to subclasses...")

        # Re-parse the modified content to get fresh positions and MCAs
        _, fresh_spans = parse_all_types(all_types_path)
        # Wait - we haven't written the file yet. Parse from in-memory content instead.
        # We'll use a helper that works on the in-memory string.
        fresh_type_to_span: dict[str, tuple[int, int]] = {}
        fresh_type_to_parent: dict[str, str | None] = {}
        fresh_type_to_mca: dict[str, int | None] = {}
        deftype_re2 = re.compile(r'\(deftype\s+(\S+)\s+\((\S+)\)')
        fresh_starts = []
        for m in deftype_re2.finditer(content):
            line_start2 = content.rfind('\n', 0, m.start()) + 1
            line_text2 = content[line_start2:m.start()]
            if ';;' in line_text2:
                continue
            before2 = content[:m.start()]
            if before2.count('#|') > before2.count('|#'):
                continue
            fresh_starts.append((m.start(), m.group(1), m.group(2)))
        for i, (start2, tn2, parent2) in enumerate(fresh_starts):
            end2 = fresh_starts[i + 1][0] if i + 1 < len(fresh_starts) else len(content)
            fresh_type_to_span[tn2] = (start2, end2)
            fresh_type_to_parent[tn2] = parent2
            blk2 = content[start2:end2]
            fresh_type_to_mca[tn2] = get_mca(blk2)

        # Track effective MCA for each type (starts from what we just set)
        effective_mca: dict[str, int] = {}
        for t in types_mca_bumped:
            for span_start_t, tn, missing_t, old_mca_t, new_mca_t, _, _ in to_fix_with_pos:
                if tn == t and new_mca_t:
                    effective_mca[t] = new_mca_t
                    break

        # Build children map from fresh parse
        children_map: dict[str, list[str]] = defaultdict(list)
        for child, parent in fresh_type_to_parent.items():
            if parent:
                children_map[parent].append(child)

        # BFS: find all descendants of bumped types and check their MCA
        cascade_fixes = []  # (typename, old_mca, new_mca, old_flag_raw, old_flag_int, span_start, span_end)
        visited = set(types_mca_bumped)
        queue = list(types_mca_bumped)
        while queue:
            parent = queue.pop(0)
            parent_mca = effective_mca.get(parent, fresh_type_to_mca.get(parent))
            if parent_mca is None:
                continue
            for child in children_map.get(parent, []):
                if child in visited:
                    continue
                visited.add(child)
                if child not in fresh_type_to_span:
                    continue
                span_start, span_end = fresh_type_to_span[child]
                block = content[span_start:span_end]
                child_mca = get_mca(block)
                child_flag_raw, child_flag_int = get_flag_assert(block)
                if child_mca is not None and child_mca < parent_mca:
                    # This child's MCA must be updated to parent_mca
                    cascade_fixes.append(
                        (child, child_mca, parent_mca, child_flag_raw, child_flag_int, span_start, span_end)
                    )
                    effective_mca[child] = parent_mca
                    queue.append(child)  # continue cascade to grandchildren
                elif child_mca is not None:
                    effective_mca[child] = child_mca
                    queue.append(child)  # still need to check its children

        if cascade_fixes:
            # Sort descending by position (end of file first) so offsets don't shift
            cascade_fixes.sort(key=lambda x: -x[5])
            cascade_count = 0
            for child, old_mca, new_mca, flag_raw, flag_int, span_start, span_end in cascade_fixes:
                print(f"  {child}: mca {old_mca} -> {new_mca} (cascade from parent)")
                content = update_mca_only(
                    content, span_start, span_end,
                    old_mca, new_mca, flag_raw, flag_int,
                    dry_run=False,
                    typename=child,
                )
                cascade_count += 1
            print(f"  Cascaded MCA update to {cascade_count} subclasses")
        else:
            print("  No subclasses need MCA cascade")
        print()

    # Step 5: Sanity check - paren balance
    if not args.dry_run:
        orig_open = sum(1 for c in open(all_types_path).read() if c == '(')
        orig_close = sum(1 for c in open(all_types_path).read() if c == ')')
        new_open = content.count('(')
        new_close = content.count(')')

        added_open = new_open - orig_open
        added_close = new_close - orig_close

        print(f"Paren check:")
        print(f"  Original: {orig_open} open, {orig_close} close (balance: {orig_open - orig_close})")
        print(f"  New:      {new_open} open, {new_close} close (balance: {new_open - new_close})")
        print(f"  Delta:    +{added_open} open, +{added_close} close")

        if (new_open - new_close) != (orig_open - orig_close):
            print("  WARNING: Paren balance changed! Check output carefully.")
        else:
            print("  OK: Paren balance unchanged")

        # Each stub line "(typename-method-N () none) ;; N" contributes 2 open and 2 close parens
        expected_added = 2 * total_stubs_added
        # Plus N new (:methods ...) blocks contributed (1 open + 1 close each)
        # Those are balanced so net is 0
        # Actually each (:methods block is 1 open paren matched by 1 close -> balanced
        # So total_stubs * 2 open + total_stubs * 2 close should be the net change from stubs
        print(f"  Expected: +{expected_added} open, +{expected_added} close (from {total_stubs_added} stubs)")
        print()

    # Step 6: Write the file
    if not args.dry_run:
        print(f"Writing {all_types_path}...")
        with open(all_types_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Done! {all_types_path} updated.")
    else:
        print("DRY RUN: File not written.")

    print()
    print("Types NOT found in all-types.gc (need separate handling):")
    for t, slots in not_found:
        print(f"  {t}: error slots {slots}")

    print()
    print("Types extended:")
    for t in sorted(types_extended):
        print(f"  {t}")


if __name__ == '__main__':
    main()
