#!/usr/bin/env python3
"""
populate_anon_fns.py

Walk decompiler_out/jakx/*_ir2.asm, extract anonymous function type errors,
infer signatures for the top-10 namespaces, and populate
decompiler/config/jakx/ntsc_v1/anonymous_function_types.jsonc.

Preserves all existing entries; only adds new namespaces/slots.
"""

import re
import sys
import json
import glob
import os
from collections import defaultdict

# ---- Config ------------------------------------------------------------

WORKTREE = "/tmp/jakx-wt-anonfns"
IR2_GLOB = os.path.join(WORKTREE, "decompiler_out/jakx/*_ir2.asm")
CONFIG_FILE = os.path.join(
    WORKTREE,
    "decompiler/config/jakx/ntsc_v1/anonymous_function_types.jsonc"
)

# How many lines of IR2 to read after the function header for context
CONTEXT_LINES = 80

# Top-10 namespaces to process (in priority order)
TOP_10 = [
    "default-menu",
    "intro-scenes3",
    "script",
    "wvehicle-weapons-proj",
    "cam-states",
    "menu2-COMMON-GAME",
    "wvehicle-weapons",
    "nav-graph-editor",
    "wvehicle-weapons-aux",
    "generic-obs",
]

# Namespace → signature inference strategy
# "behavior" = uses s6 register (self pointer) → :behavior TYPE
# "scene-player" = pure callbacks for scene-player state transitions
# "menu-callback" = debug menu callbacks (object debug-menu-msg → object)  
# "event-handler" = process event handlers
# "generic" = use fallback
NAMESPACE_STRATEGY = {
    "default-menu": "menu-callback",
    "intro-scenes3": "scene-player",
    "script": "script-cmd",
    "wvehicle-weapons-proj": "behavior",
    "cam-states": "behavior-cam",
    "menu2-COMMON-GAME": "event-handler",
    "wvehicle-weapons": "behavior",
    "nav-graph-editor": "behavior",
    "wvehicle-weapons-aux": "behavior",
    "generic-obs": "behavior",
}

# Behavior types - what TYPE name to use for :behavior annotation
# Must be types registered in all-types.gc!
BEHAVIOR_TYPE = {
    "wvehicle-weapons-proj": "process",  # wvehicle-weapons-proj not in all-types.gc
    "cam-states": "camera-slave",         # camera-slave defined in all-types.gc
    "wvehicle-weapons": "process",        # wvehicle-weapons not in all-types.gc
    "nav-graph-editor": "nav-graph-editor",  # defined in all-types.gc
    "wvehicle-weapons-aux": "process",    # not in all-types.gc
    "generic-obs": "process",             # not in all-types.gc
}

# ---- Step 1: Collect errors from ir2 files ----------------------------

def collect_errors():
    """Return dict: namespace → sorted list of (fn_num, filepath, line_num)"""
    pattern = re.compile(
        r"^;; ERROR: Function \(anon-function (\d+) ([^\)]+)\) has unknown type"
    )
    errors = defaultdict(list)

    for filepath in sorted(glob.glob(IR2_GLOB)):
        with open(filepath, "r", errors="replace") as f:
            lines = f.readlines()
        for lineno, line in enumerate(lines):
            m = pattern.match(line.rstrip())
            if m:
                fn_num = int(m.group(1))
                ns = m.group(2)
                errors[ns].append((fn_num, filepath, lineno))

    return errors

# ---- Step 2: Read IR2 context for a function -------------------------

def read_function_context(filepath, error_lineno, num_lines=CONTEXT_LINES):
    """
    Walk backwards from error_lineno to find '; .function' header.
    Return the lines from header to header+num_lines.
    """
    with open(filepath, "r", errors="replace") as f:
        lines = f.readlines()

    # Find the '; .function' header at or before error_lineno
    start = error_lineno
    for i in range(error_lineno, max(0, error_lineno - 10), -1):
        if lines[i].startswith("; .function"):
            start = i
            break

    end = min(len(lines), start + num_lines)
    return lines[start:end]

# ---- Step 3: Infer signature from context ----------------------------

def uses_s6(context_lines):
    """True if any instruction in context uses s6 as a source/dest."""
    s6_pattern = re.compile(r"\bs6\b")
    for line in context_lines:
        if s6_pattern.search(line):
            return True
    return False

def uses_arg_register(context_lines, reg):
    """True if register (a0, a1, a2, a3) appears in context."""
    pat = re.compile(r"\b" + re.escape(reg) + r"\b")
    for line in context_lines:
        if pat.search(line):
            return True
    return False

def infer_signature(namespace, fn_num, filepath, error_lineno):
    """Return a GOAL function type string."""
    strategy = NAMESPACE_STRATEGY.get(namespace, "generic")
    context = read_function_context(filepath, error_lineno)

    if strategy == "scene-player":
        # Scene-player state callbacks: no args, called as behavior thunks
        return "(function none :behavior scene-player)"

    elif strategy == "menu-callback":
        # Debug menu callbacks: (arg0 debug-menu-msg) or similar
        # The decompiler accepts (function object object object) here
        # Some have 0 args, some have (arg0 arg1), default to object/object
        return "(function object object object)"

    elif strategy == "event-handler":
        # Process event handlers: full event signature
        return "(function process int symbol event-message-block object :behavior base-menu)"

    elif strategy == "behavior":
        btype = BEHAVIOR_TYPE.get(namespace, namespace)
        return f"(function object :behavior {btype})"

    elif strategy == "behavior-cam":
        # cam-states functions are camera-slave behaviors
        return "(function object :behavior camera-slave)"

    elif strategy == "script-cmd":
        # Script command handlers - some take args, some don't
        # Use generic fallback with single object arg
        has_a0 = uses_arg_register(context, "a0")
        if has_a0:
            return "(function object object)"
        else:
            return "(function object)"

    else:
        # generic fallback
        if uses_s6(context):
            btype = BEHAVIOR_TYPE.get(namespace, namespace)
            return f"(function object :behavior {btype})"
        else:
            return "(function object)"

# ---- Step 4: Parse existing JSONC ------------------------------------

def strip_jsonc_comments(text):
    """Strip // line comments from JSONC text."""
    result = []
    for line in text.splitlines():
        # Remove inline // comments (but not inside strings)
        # Simple approach: find first // not in a string
        stripped = re.sub(r'(?<!:)//.*$', '', line)
        result.append(stripped)
    return "\n".join(result)

def load_existing_config():
    """Return the existing config as dict: namespace → [[N, sig], ...]"""
    with open(CONFIG_FILE, "r") as f:
        text = f.read()
    cleaned = strip_jsonc_comments(text)
    return json.loads(cleaned)

# ---- Step 5: Merge and write back ------------------------------------

def merge_and_write(existing, new_entries):
    """
    Merge new_entries into existing config.
    existing: dict namespace → [[N, sig], ...]
    new_entries: dict namespace → {N: sig}
    
    Rules:
    - Preserve ALL existing entries
    - For existing namespaces, only add NEW slot numbers
    - For new namespaces, add the full block
    - Write back as clean JSON (comments not preserved)
    """
    result = dict(existing)  # shallow copy

    stats = {}
    for ns, slots in new_entries.items():
        if ns not in result:
            # New namespace
            result[ns] = [[n, sig] for n, sig in sorted(slots.items())]
            stats[ns] = len(slots)
        else:
            # Existing namespace - find which slots are new
            existing_slots = {entry[0] for entry in result[ns]}
            added = 0
            for n, sig in sorted(slots.items()):
                if n not in existing_slots:
                    result[ns].append([n, sig])
                    added += 1
            # Keep sorted
            result[ns].sort(key=lambda x: x[0])
            stats[ns] = added

    # Write back
    out = json.dumps(result, indent=2)
    with open(CONFIG_FILE, "w") as f:
        f.write(out)
        f.write("\n")

    # Validate by reloading
    with open(CONFIG_FILE, "r") as f:
        check = json.loads(f.read())
    assert check is not None, "Output file failed to parse!"

    return stats

# ---- Main ------------------------------------------------------------

def main():
    print("=== populate_anon_fns.py ===")
    print(f"IR2 glob: {IR2_GLOB}")
    print(f"Config: {CONFIG_FILE}")
    print()

    # Step 1: Collect all errors
    print("Step 1: Collecting errors from ir2 files...")
    all_errors = collect_errors()
    total = sum(len(v) for v in all_errors.values())
    print(f"  Found {total} anon-function errors across {len(all_errors)} namespaces")

    # Show top-15 by count
    sorted_ns = sorted(all_errors.items(), key=lambda x: -len(x[1]))
    print("\nTop 15 namespaces:")
    for ns, errs in sorted_ns[:15]:
        print(f"  {ns}: {len(errs)}")

    # Step 2: Load existing config
    print("\nStep 2: Loading existing config...")
    existing = load_existing_config()
    print(f"  Existing namespaces: {len(existing)}")
    existing_slots_by_ns = {
        ns: {entry[0] for entry in entries}
        for ns, entries in existing.items()
    }

    # Step 3: Process top-10 namespaces
    print(f"\nStep 3: Processing top-10 namespaces...")
    new_entries = {}  # ns → {fn_num: sig}

    for ns in TOP_10:
        if ns not in all_errors:
            print(f"  {ns}: NOT FOUND in errors (already fixed?)")
            continue

        errors_for_ns = all_errors[ns]
        existing_slots = existing_slots_by_ns.get(ns, set())
        
        new_slots = {}
        skipped = 0
        for fn_num, filepath, lineno in errors_for_ns:
            if fn_num in existing_slots:
                skipped += 1
                continue
            sig = infer_signature(ns, fn_num, filepath, lineno)
            new_slots[fn_num] = sig

        new_entries[ns] = new_slots
        print(f"  {ns}: {len(new_slots)} new slots "
              f"({skipped} already present), "
              f"strategy={NAMESPACE_STRATEGY.get(ns,'generic')}")
        if new_slots:
            # Show a sample
            sample_num = sorted(new_slots.keys())[0]
            print(f"    Sample: anon-fn {sample_num} → {new_slots[sample_num]}")

    # Step 4: Merge and write
    print("\nStep 4: Merging and writing config...")
    stats = merge_and_write(existing, new_entries)
    print("\nSlots added per namespace:")
    for ns in TOP_10:
        added = stats.get(ns, 0)
        print(f"  {ns}: +{added}")

    total_added = sum(stats.values())
    print(f"\nTotal new slots added: {total_added}")
    print("\nDone! Validate by re-running the decompiler.")

if __name__ == "__main__":
    main()
