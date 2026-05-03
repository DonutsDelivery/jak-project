#!/usr/bin/env python3
"""Scan REF files in test/decompiler/reference/{jak1,jak2,jak3} for validated function/method names.

Output: .jakx_watch/research/ref_validated_fns.json
Format: { "jak1": ["fn1", "(method N type)", ...], "jak2": [...], "jak3": [...] }

A function is "REF-validated" when it has a passing offline-test reference file containing
its definition. This is stronger ground truth than "real-clean filter" (which is just
"no error markers in regen output").
"""
import json, os, re, sys
from pathlib import Path

ROOT = Path("/home/user/Programs/Jak-X/jak-project")
REF_BASE = ROOT / "test/decompiler/reference"
OUT = ROOT / ".jakx_watch/research/ref_validated_fns.json"

# Match top-level definitions in REF .gc files
# (defun NAME ...), (defbehavior NAME ...), (defmethod NAME ...), (defmethod TYPE METHOD-IDX ...)
RE_DEFUN = re.compile(r"^\((defun|defbehavior|defun-debug)\s+(\S+)\b")
RE_DEFMETHOD_IDX = re.compile(r"^\(defmethod\s+(\d+)\s+(\S+)\b")  # newer form
RE_DEFMETHOD_NAME = re.compile(r"^\(defmethod\s+(\S+)\s+(\S+)\b")  # older form: (defmethod TYPE METHOD-NAME ...)

def scan_ref_dir(game):
    base = REF_BASE / game
    if not base.exists():
        return []
    fns = set()
    for ref in base.rglob("*_REF.gc"):
        try:
            text = ref.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for line in text.splitlines():
            m = RE_DEFUN.match(line)
            if m:
                fns.add(m.group(2))
                continue
            m = RE_DEFMETHOD_IDX.match(line)
            if m:
                idx, typ = m.group(1), m.group(2)
                fns.add(f"(method {idx} {typ})")
                continue
            m = RE_DEFMETHOD_NAME.match(line)
            if m:
                # name-form defmethod: (defmethod TYPE METHOD ...)  e.g. (defmethod print process)
                # We can't easily get the slot; record as name+type
                typ, mname = m.group(1), m.group(2)
                fns.add(f"(method-named {mname} {typ})")
    return sorted(fns)

def main():
    out = {}
    total = 0
    for game in ("jak1", "jak2", "jak3"):
        names = scan_ref_dir(game)
        out[game] = names
        total += len(names)
        print(f"{game}: {len(names)} REF-validated names", file=sys.stderr)
    OUT.write_text(json.dumps(out, indent=1))
    print(f"\nTotal: {total} entries -> {OUT}", file=sys.stderr)

if __name__ == "__main__":
    main()
