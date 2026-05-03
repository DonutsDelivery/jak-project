#!/usr/bin/env python3
"""Mine game/mips2c/jakx_functions/*.cpp for registered function names + return type hints.

Output: .jakx_watch/research/extern_hints_from_jakx_functions.json
Format: { "fn-name": { "source_file": "...", "namespace": "...", "is_method": bool } }

Each entry is an authoritative GOAL function name (from `gLinkedFunctionTable.reg("name", ...)`)
that has a working hand-port in jakx_functions. These are gold-standard `extern_add` hints —
the function exists and has a working entry point, which means the GOAL signature must match.

Return type for execute() is always u64 (return c->gprs[v0].du64[0]) so we don't extract types.
What this provides is the AUTHORITATIVE NAME LIST — the matcher can prefer extern_add for
candidates whose name appears here.
"""
import json, re, sys
from pathlib import Path

ROOT = Path("/home/user/Programs/Jak-X/jak-project")
SRC = ROOT / "game/mips2c/jakx_functions"
OUT = ROOT / ".jakx_watch/research/extern_hints_from_jakx_functions.json"

RE_REG = re.compile(r'gLinkedFunctionTable\.reg\("([^"]+)"\s*,\s*execute\s*,\s*(\d+)\)')
RE_NAMESPACE = re.compile(r"^namespace\s+(\S+)\s*\{")

def main():
    if not SRC.exists():
        print(f"ERROR: {SRC} missing", file=sys.stderr); sys.exit(1)
    hints = {}
    for cpp in sorted(SRC.glob("*.cpp")):
        text = cpp.read_text(encoding="utf-8", errors="replace")
        # Track current namespace stack
        ns_stack = []
        for line in text.splitlines():
            m_ns = RE_NAMESPACE.match(line.strip())
            if m_ns:
                ns_stack.append(m_ns.group(1))
                continue
            if line.strip() == "}" and ns_stack:
                ns_stack.pop()
                continue
            m = RE_REG.search(line)
            if m:
                name = m.group(1)
                hints[name] = {
                    "source_file": cpp.name,
                    "namespace": ".".join(ns_stack[-2:]) if ns_stack else "",
                    "is_method": name.startswith("(method "),
                    "stack_size": int(m.group(2)),
                }
    OUT.write_text(json.dumps(hints, indent=1, sort_keys=True))
    print(f"Wrote {len(hints)} extern hints from {len(list(SRC.glob('*.cpp')))} files -> {OUT}", file=sys.stderr)
    methods = [n for n in hints if n.startswith("(method ")]
    funcs = [n for n in hints if not n.startswith("(method ")]
    print(f"  {len(funcs)} top-level functions, {len(methods)} methods", file=sys.stderr)

if __name__ == "__main__":
    main()
