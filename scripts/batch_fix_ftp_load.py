#!/usr/bin/env python3
"""
batch_fix_ftp_load.py — automated type cast generator for 'Could not figure out load' errors.

Classifies each error into three buckets per the discriminator spec:
  LOCAL CAST       — register typed wrong locally; cast at load site is safe.
  UPSTREAM SIG     — arg signature wrong upstream; skip, flag for review.
  MASK-BUG         — missing type def, deref-kind mismatch, VU issue, decompiler bug; skip.

Prioritizes racing-critical files.
Skips known items: kras-pump-break method 45, bsp-header.birth.

Usage:
  python3 scripts/batch_fix_ftp_load.py [--apply] [--focus TYPE]
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

IR_DIR = '/home/user/Programs/Jak-X/jak-project/decompiler_out/jakx'
TYPE_CASTS_PATH = '/home/user/Programs/Jak-X/jak-project/decompiler/config/jakx/ntsc_v1/type_casts.jsonc'

PRIMITIVE_TYPES = {
    'uint', 'int', 'uint8', 'int8', 'uint16', 'int16', 'uint32', 'int32',
    'uint64', 'int64', '<uninitialized>', 'none', 'float',
    '<integer', '<value',
}

RACING_PATTERNS = [
    'wvehicle', 'vehicle', 'race-', 'nav-', 'pilot', 'target-pilot', 'entity'
]

SKIP_FUNCS = {
    '(method 45 kras-pump-break-proxy)',
    'bsp-header.birth',
}


def is_primitive(t):
    t = t.strip()
    for p in PRIMITIVE_TYPES:
        if t.startswith(p):
            return True
    return False


def is_concrete_struct(t):
    t = t.strip()
    if not t:
        return False
    if is_primitive(t):
        return False
    if t.startswith('<') or t.startswith('#') or t.startswith("'"):
        return False
    if t in ('object', 'pointer', 'basic', 'structure', '_var_', ''):
        return False
    if re.match(r'^[a-z][a-z0-9_-]*$', t):
        return True
    return False


def ir_file_priority(basename):
    name = basename.replace('_ir2.asm', '')
    for i, pat in enumerate(RACING_PATTERNS):
        if name.startswith(pat):
            return len(RACING_PATTERNS) - i
    return 0


# ─── Discriminator ────────────────────────────────────────────────────

def classify(err):
    """
    Return (bucket, reason, inferred_type_or_None)
    """
    curr = err['curr_type'].strip()
    src = err['src_reg']
    func = err['func_name']
    mt = err['method_type']
    load_kind = err['load_kind']
    op = err['op']
    best_ancestor = err.get('best_ancestor_type', '')
    is_method = mt is not None

    # 1. Known skip
    if func in SKIP_FUNCS:
        return ('MASK-BUG', 'known skip', None)

    # 2. l.q — VU-related, skip
    if load_kind == 'q':
        return ('MASK-BUG', 'l.q VU access', None)

    # 3. Source already has concrete struct → MASK-BUG
    if is_concrete_struct(curr):
        return ('MASK-BUG', f'src is {curr}, need field def or deref-kind fix', None)

    # 4. s6 → LOCAL CAST (always safe)
    if src == 's6':
        return ('LOCAL CAST', 's6 is process', 'process')

    # 5. l.hu on struct-typed register at offset 0 → MASK-BUG
    if load_kind == 'hu' and err['offset'] == 0 and is_concrete_struct(curr):
        return ('MASK-BUG', 'l.hu deref-kind mismatch at offset 0', None)

    # 6. l.d on register (8-byte load) where source had 'object' parameter → UPSTREAM SIG
    if src in ('a0', 'a1', 'a2', 'a3') and curr == 'object':
        if is_method:
            return ('UPSTREAM SIG', f'param {src} is object, caller-side fix', None)
        return ('UPSTREAM SIG', f'top-level param {src} is object', None)

    # 7. a0 in method, early ops → LOCAL CAST to method type
    if src == 'a0' and is_method and is_primitive(curr) and op <= 3:
        return ('LOCAL CAST', f'a0 is this ({mt})', mt)

    # 8. gp in method → LOCAL CAST to method type
    if src == 'gp' and is_method and is_primitive(curr):
        return ('LOCAL CAST', f'gp is this ({mt})', mt)

    # 9. Saved register (s5/s4 etc) that traces from a0 in method → LOCAL CAST
    saved_from_a0 = err.get('saved_regs', {}).get(src) == 'a0'
    if saved_from_a0 and is_method and is_primitive(curr):
        return ('LOCAL CAST', f'{src} = a0 = this ({mt})', mt)

    # 10. Register had good ancestor type → LOCAL CAST using ancestor
    if best_ancestor and is_concrete_struct(best_ancestor):
        return ('LOCAL CAST', f'{src} lost type {best_ancestor}', best_ancestor)

    # 11. uint/<uninitialized>/none on non-param registers → LOCAL CAST to pointer
    if src not in ('a0', 'a1', 'a2', 'a3') and curr in ('uint', '<uninitialized>', 'none', ''):
        return ('LOCAL CAST', f'{src} is {curr or "?"}, needs pointer', 'pointer')

    # 12. a0/a1/a2/a3 with uint after handle extraction → LOCAL CAST to pointer
    if src in ('a0', 'a1', 'a2', 'a3') and curr in ('uint', '<uninitialized>', 'none', ''):
        return ('LOCAL CAST', f'{src} has {curr}, handle→pointer', 'pointer')

    # 13. Everything else → UPSTREAM SIG
    return ('UPSTREAM SIG', f'unhandled: {src}={curr}', None)


# ─── IR Parsing ────────────────────────────────────────────────────────

def trace_ancestor_type(op, src_reg, op_annotations, max_lookback=20):
    best_type = ''
    best_op = -1
    for sop in range(op - 1, max(op - max_lookback - 1, -1), -1):
        if sop in op_annotations and src_reg in op_annotations[sop]:
            t = op_annotations[sop][src_reg].strip()
            if is_concrete_struct(t):
                return (sop, t)
            if not best_type and not is_primitive(t) and t:
                best_type = t
                best_op = sop
    return (best_op, best_type)


def parse_method_func(func_name):
    m = re.match(r'\(method (\d+) ([^)]+)\)', func_name)
    if m:
        return int(m.group(1)), m.group(2)
    return None, None


def collect_load_errors(ir_files):
    errors = []
    for fpath in ir_files:
        with open(fpath, errors='ignore') as f:
            content = f.read()

        func_parts = re.split(
            r'\n(?=;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;\n; \.function )',
            content
        )

        for part in func_parts:
            if 'Could not figure out load' not in part:
                continue

            mf = re.search(r'; \.function\s+(.+?)\s*$', part, re.MULTILINE)
            if not mf:
                continue
            func_name = mf.group(1).strip()
            method_num, method_type = parse_method_func(func_name)

            # gprs
            gprs = set()
            mg = re.search(r';gprs:\s*(.+)', part)
            if mg:
                gprs = set(mg.group(1).strip().split())

            # saved register assignments
            saved_regs = {}
            for line in part.split('\n'):
                m2 = re.search(
                    r'or\s+(\S+),\s+(\S+),\s+r0\s+.*\[\s*\d+\]',
                    line.strip()
                )
                if m2:
                    dst, src = m2.group(1), m2.group(2)
                    if dst in gprs and src in ('a0', 'a1', 'a2', 'a3'):
                        saved_regs[dst] = src

            # op→{reg→type} annotations
            op_annotations = {}
            for line in part.split('\n'):
                m2 = re.search(r';;\s*\[\s*(\d+)\].*\[([^\]]*)\]\s*->', line)
                if m2:
                    op = int(m2.group(1))
                    ts = m2.group(2)
                    rt = {}
                    for te in re.finditer(r'(\S+):\s*([^,\]]+)', ts):
                        rt[te.group(1)] = te.group(2).strip()
                    op_annotations[op] = rt

            # Parse each load error
            for merr in re.finditer(
                    r'ERROR: failed type prop at (\d+): Could not figure out load: '
                    r'\(set! (\S+) \(l\.(\w+) (.+?)\)\)',
                    part):
                op = int(merr.group(1))
                dest_reg = merr.group(2)
                load_kind = merr.group(3)
                src_expr = merr.group(4)

                src_m = re.match(r'\((\+ (\S+) (\d+))\)?', src_expr)
                if src_m:
                    offset = int(src_m.group(3))
                    src_reg = src_m.group(2)
                else:
                    offset = 0
                    src_reg = src_expr

                curr_type = ''
                if op in op_annotations and src_reg in op_annotations[op]:
                    curr_type = op_annotations[op][src_reg]
                else:
                    for sop in range(op - 1, max(op - 10, -1), -1):
                        if sop in op_annotations and src_reg in op_annotations[sop]:
                            curr_type = op_annotations[sop][src_reg]
                            break

                ancestor_op, best_ancestor_type = trace_ancestor_type(
                    op, src_reg, op_annotations
                )

                err = {
                    'func_name': func_name,
                    'op': op,
                    'dest_reg': dest_reg,
                    'load_kind': load_kind,
                    'src_reg': src_reg,
                    'offset': offset,
                    'curr_type': curr_type,
                    'method_type': method_type,
                    'is_offset0': offset == 0,
                    'saved_regs': saved_regs,
                    'best_ancestor_type': best_ancestor_type,
                    'ancestor_op': ancestor_op,
                }

                bucket, reason, inferred = classify(err)
                err['bucket'] = bucket
                err['bucket_reason'] = reason
                err['inferred_type'] = inferred
                errors.append(err)

    return errors


def load_type_casts():
    if not os.path.exists(TYPE_CASTS_PATH):
        return {}
    with open(TYPE_CASTS_PATH) as f:
        return json.load(f)


def save_type_casts(casts, path):
    with open(path, 'w') as f:
        json.dump(casts, f, indent=2)
        f.write('\n')


def deduplicate_new_casts(fn_casts, existing_casts):
    new_casts = defaultdict(list)
    for fn, casts in fn_casts.items():
        existing_list = existing_casts.get(fn, [])
        if not isinstance(existing_list, list):
            existing_list = []
        already = set()
        for existing in existing_list:
            if not isinstance(existing, list) or len(existing) < 3:
                continue
            eop = existing[0]
            if isinstance(eop, list):
                for op_in_range in range(eop[0], eop[1] + 1):
                    already.add((op_in_range, existing[1]))
            else:
                already.add((eop, existing[1]))
        for cast in casts:
            key = (cast[0], cast[1])
            if key not in already:
                new_casts[fn].append(list(cast))
                already.add(key)
    return dict(new_casts)


def main():
    parser = argparse.ArgumentParser(
        description='Batch fix FTP load errors with type casts'
    )
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument(
        '--focus',
        choices=['all', 'offset0', 'fixed-offset', 'racing'],
        default='racing',
    )
    parser.add_argument('--min-casts-per-func', type=int, default=0)
    args = parser.parse_args()

    if args.apply:
        args.dry_run = False

    ir_files = sorted([
        os.path.join(IR_DIR, f)
        for f in os.listdir(IR_DIR)
        if f.endswith('_ir2.asm')
    ])
    print(f"Found {len(ir_files)} IR files", file=sys.stderr)

    # Collect
    all_errors = collect_load_errors(ir_files)
    print(f"Total load errors: {len(all_errors)}", file=sys.stderr)

    # Bucket summary
    by_bucket = defaultdict(int)
    by_reason = defaultdict(lambda: defaultdict(int))
    for e in all_errors:
        by_bucket[e['bucket']] += 1
        by_reason[e['bucket']][e['bucket_reason']] += 1

    print(f"\n=== Bucket Distribution ===")
    for b in ['LOCAL CAST', 'UPSTREAM SIG', 'MASK-BUG']:
        cnt = by_bucket.get(b, 0)
        pct = 100 * cnt / len(all_errors) if len(all_errors) > 0 else 0
        print(f"  {b}: {cnt} ({pct:.1f}%)")
        if cnt > 0:
            print(f"    Top reasons:")
            for r, c in sorted(by_reason[b].items(), key=lambda x: -x[1])[:5]:
                print(f"      {r}: {c}")

    # Filter to LOCAL CAST only
    cast_errors = [e for e in all_errors if e['bucket'] == 'LOCAL CAST' and e['inferred_type']]
    print(f"\nLOCAL CAST candidates: {len(cast_errors)}")

    # Map functions to IR files for priority
    fn_file_map = {}
    for fpath in ir_files:
        bname = os.path.basename(fpath)
        with open(fpath, errors='ignore') as f:
            content = f.read()
        for m in re.finditer(r'; \.function\s+(.+?)\s*$', content, re.MULTILINE):
            fn = m.group(1).strip()
            fn_file_map[fn] = (fpath, bname)

    # Apply focus
    if args.focus == 'offset0':
        cast_errors = [e for e in cast_errors if e['is_offset0']]
    elif args.focus == 'fixed-offset':
        cast_errors = [e for e in cast_errors if not e['is_offset0']]
    elif args.focus == 'racing':
        cast_errors = [
            e for e in cast_errors
            if e['func_name'] in fn_file_map
            and ir_file_priority(fn_file_map[e['func_name']][1]) > 0
        ]

    print(f"After focus '{args.focus}': {len(cast_errors)} errors")

    # Group by function, score by priority
    fn_to_errors = defaultdict(list)
    for e in cast_errors:
        fn_to_errors[e['func_name']].append(e)

    scored = []
    for fn, errs in fn_to_errors.items():
        prio = 0
        if fn in fn_file_map:
            prio = ir_file_priority(fn_file_map[fn][1])
        scored.append((-prio, fn, errs))
    scored.sort()

    # Report
    print(f"\n{'='*70}")
    print(f"LOCAL CAST by Function (priority sorted)")
    print(f"{'='*70}")
    local_total = 0
    racing_total = 0
    for neg_prio, fn, errs in scored:
        prio = -neg_prio
        if args.min_casts_per_func > 0 and len(errs) < args.min_casts_per_func:
            continue
        tag = 'RACING' if prio > 0 else '     '
        local_total += len(errs)
        if prio > 0:
            racing_total += len(errs)
        print(f"  {tag}  {fn}: {len(errs)} casts")

    print(f"\n  Racing-critical: {racing_total}")
    print(f"  Total:           {local_total}")

    # Inferred type distribution
    by_inferred = defaultdict(int)
    for e in cast_errors:
        by_inferred[e['inferred_type']] += 1
    print(f"\n=== Inferred Type Distribution ===")
    for t, cnt in sorted(by_inferred.items(), key=lambda x: -x[1]):
        print(f"  {t}: {cnt}")

    # UPSTREAM SIG report
    up_errors = [e for e in all_errors if e['bucket'] == 'UPSTREAM SIG']
    if up_errors:
        up_fns = defaultdict(list)
        for e in up_errors:
            up_fns[e['func_name']].append(e)
        print(f"\n=== UPSTREAM SIG (flag for review) ===")
        for fn, errs in sorted(up_fns.items(), key=lambda x: -len(x[1])):
            print(f"  {fn}: {len(errs)}")
            for e in errs[:2]:
                print(f"    op {e['op']}: {e['src_reg']}={e['curr_type']} ({e['bucket_reason']})")

    # Generate cast entries
    fn_casts = defaultdict(list)
    for e in cast_errors:
        fn_casts[e['func_name']].append((e['op'], e['src_reg'], e['inferred_type']))

    existing_casts = load_type_casts()
    print(f"\nExisting type_casts.jsonc: {len(existing_casts)} entries", file=sys.stderr)
    new_casts = deduplicate_new_casts(fn_casts, existing_casts)
    total_new = sum(len(v) for v in new_casts.values())
    print(f"New unique casts after dedup: {total_new}", file=sys.stderr)

    if args.apply and new_casts:
        for fn, casts in new_casts.items():
            existing = existing_casts.get(fn, [])
            if not isinstance(existing, list):
                existing = []
            for ce in casts:
                existing.append(ce)
            existing_casts[fn] = existing
        save_type_casts(existing_casts, TYPE_CASTS_PATH)
        print(f"\nWritten {total_new} new casts to {TYPE_CASTS_PATH}", file=sys.stderr)
        print(f"Total entries: {len(existing_casts)}", file=sys.stderr)
    elif args.dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN — use --apply to write")
        offset0_cnt = sum(1 for e in cast_errors if e['is_offset0'])
        fixed_cnt = len(cast_errors) - offset0_cnt
        print(f"New casts: {total_new} ({offset0_cnt} offset-0, {fixed_cnt} fixed-offset)")
        print(f"Upstream SIG total: {len(up_errors)}")


if __name__ == '__main__':
    main()
