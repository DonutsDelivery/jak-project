#!/usr/bin/env python3
"""
jakx_stack16_classify.py

Mine "Failed to guess stack use for 16" errors out of decompiler_out/jakx/*_ir2.asm,
classify each function by safety tier, and propose [16,"vector"] entries to
inject into decompiler/config/jakx/ntsc_v1/stack_structures.jsonc.

Usage:
    python3 scripts/jakx_stack16_classify.py            # report only
    python3 scripts/jakx_stack16_classify.py --apply    # write tier1+tier2 to config
    python3 scripts/jakx_stack16_classify.py --apply --tier 1   # tier1 only

Tiers
-----
tier1 SAFE          : ;stack_vars: 16 bytes at 16   AND  err_offsets == [16]
tier2 LIKELY-SAFE   : err_offsets == [16]  AND  sv_at == 16  AND  the only sp-base
                      derived inside the function body is sp+16 (no sp+32, sp+48, ...).
                      The stack_vars header may report >16 bytes due to
                      compiler padding/alignment, but no other slot is actually
                      addressed.
tier3 MULTI-OFFSET  : everything else (do not auto-emit; needs hand review).
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ASM_GLOB    = REPO / "decompiler_out/jakx/*_ir2.asm"
JAKX_CFG    = REPO / "decompiler/config/jakx/ntsc_v1/stack_structures.jsonc"
JAK3_CFG    = REPO / "decompiler/config/jak3/ntsc_v1/stack_structures.jsonc"

FUNC_HDR_RE = re.compile(r'^; \.function (.+?)$', re.M)
SV_RE       = re.compile(r';stack_vars:\s*(\d+)\s*bytes at\s*(\d+)')
SP_TOTAL_RE = re.compile(r'daddiu sp, sp, -(\d+)')
ERR_RE      = re.compile(r'Failed to guess stack use for (\d+) in')
SP_REF_RE   = re.compile(r'\b(-?\d+)\(sp\)')
SP_BASE_RE  = re.compile(r'daddiu\s+\S+,\s*sp,\s*(\d+)')
EXISTING_KEY_RE = re.compile(r'^\s*"((?:[^"\\]|\\.)+)":', re.M)


def analyze_block(block: str) -> dict | None:
    sv = SV_RE.search(block)
    sp_total = SP_TOTAL_RE.search(block)
    if not (sv and sp_total):
        return None
    sv_size = int(sv.group(1))
    sv_at   = int(sv.group(2))
    sp_total_v = int(sp_total.group(1))
    err_offs = sorted({int(x) for x in ERR_RE.findall(block)})
    if not err_offs:
        return None
    # sp+N references used as memory operand
    sp_refs = sorted({int(m.group(1)) for m in SP_REF_RE.finditer(block)
                      if 0 < int(m.group(1)) < sp_total_v - 16})
    # explicit address-of sp+N (reveals stack-var bases)
    sp_bases = sorted({int(m.group(1)) for m in SP_BASE_RE.finditer(block)
                       if int(m.group(1)) > 0})
    return dict(sv_size=sv_size, sv_at=sv_at, sp_total=sp_total_v,
                err_offs=err_offs, sp_refs=sp_refs, sp_bases=sp_bases)


def collect_functions() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in glob.glob(str(ASM_GLOB)):
        txt = open(path, errors='ignore').read()
        hdrs = list(FUNC_HDR_RE.finditer(txt))
        for i, m in enumerate(hdrs):
            name = m.group(1).strip()
            start = m.start()
            end = hdrs[i + 1].start() if i + 1 < len(hdrs) else len(txt)
            block = txt[start:end]
            if 'Failed to guess stack use' not in block:
                continue
            info = analyze_block(block)
            if info is None:
                continue
            info['file'] = os.path.basename(path)
            out[name] = info
    return out


def classify(funcs: dict[str, dict]) -> dict[str, list[str]]:
    tier1, tier2, tier3 = [], [], []
    for n, r in funcs.items():
        meaningful_bases = tuple(b for b in r['sp_bases']
                                 if 16 <= b < r['sp_total'] - 16)
        if r['sv_size'] == 16 and r['sv_at'] == 16 and r['err_offs'] == [16]:
            tier1.append(n)
        elif (r['err_offs'] == [16]
              and r['sv_at'] == 16
              and meaningful_bases == (16,)
              and r['sv_size'] <= 32):
            # Constrain to small slots (<=32 bytes). Larger single-base
            # allocations are almost always buffers/struct-pointers being
            # passed to a callee — labelling them "vector" would mislead.
            tier2.append(n)
        else:
            tier3.append(n)
    return dict(tier1=tier1, tier2=tier2, tier3=tier3)


def existing_keys(cfg_path: Path) -> set[str]:
    return set(EXISTING_KEY_RE.findall(cfg_path.read_text()))


def render_entry(name: str) -> str:
    # Match the existing pretty-printed style in jakx config:
    #   "name": [
    #     [
    #       16,
    #       "vector"
    #     ]
    #   ]
    return (f'  {json.dumps(name)}: [\n'
            f'    [\n'
            f'      16,\n'
            f'      "vector"\n'
            f'    ]\n'
            f'  ]')


def insert_entries(cfg_path: Path, names: list[str]) -> int:
    """Append entries before the trailing '}' of the JSONC file. Skips names
    already present. Returns count actually inserted."""
    text = cfg_path.read_text()
    have = existing_keys(cfg_path)
    new_names = [n for n in names if n not in have]
    if not new_names:
        return 0
    # find the LAST '}' (top-level close)
    close = text.rstrip().rfind('}')
    if close < 0:
        raise RuntimeError("Couldn't find closing brace in config")
    head = text[:close].rstrip()
    # ensure the previous entry ends with a comma
    if not head.endswith(','):
        head = head + ','
    body = ',\n'.join(render_entry(n) for n in new_names)
    new_text = head + '\n' + body + '\n}\n'
    cfg_path.write_text(new_text)
    return len(new_names)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true',
                    help='write entries into stack_structures.jsonc')
    ap.add_argument('--tier', type=int, default=2,
                    help='max tier to apply (1=safest, 2=likely-safe). default 2')
    ap.add_argument('--dump-json', metavar='PATH',
                    help='also dump full classification to JSON for inspection')
    args = ap.parse_args()

    funcs = collect_functions()
    tiers = classify(funcs)
    have = existing_keys(JAKX_CFG)

    print(f'Functions with stack-guess errors:  {len(funcs)}')
    print(f'  tier1 SAFE          (sv==16, err==[16]):        {len(tiers["tier1"]):4d}')
    print(f'  tier2 LIKELY-SAFE   (single sp+16 base only):   {len(tiers["tier2"]):4d}')
    print(f'  tier3 MULTI-OFFSET  (needs hand review):        {len(tiers["tier3"]):4d}')

    err_offset_dist = Counter()
    for r in funcs.values():
        for o in r['err_offs']:
            err_offset_dist[o] += 1
    print(f'\nError-offset distribution: {sorted(err_offset_dist.items())}')

    candidates = tiers['tier1'] + (tiers['tier2'] if args.tier >= 2 else [])
    new_only = [n for n in candidates if n not in have]
    print(f'\nProposed new entries (tier<= {args.tier}, novel): {len(new_only)}')
    for n in new_only:
        r = funcs[n]
        print(f'  {n}    sv={r["sv_size"]}  sp_total={r["sp_total"]}  file={r["file"]}')

    if args.dump_json:
        payload = {n: dict(funcs[n], tier=(1 if n in tiers['tier1']
                                           else 2 if n in tiers['tier2']
                                           else 3))
                   for n in funcs}
        Path(args.dump_json).write_text(json.dumps(payload, indent=1))
        print(f'\nDumped detail to {args.dump_json}')

    if args.apply:
        n = insert_entries(JAKX_CFG, new_only)
        print(f'\nInserted {n} entries into {JAKX_CFG}')
    else:
        print('\n(dry run — pass --apply to write)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
