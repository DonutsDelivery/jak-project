#!/usr/bin/env python3
"""Run offline-test for jakx against files that reached real-clean.

Splits the real-clean bucket into:
  - green  : offline-test passed (decomps AND goalc-compiles to matching bytecode)
  - amber  : decomps, but bytecode-diff fails → not shippable yet
  - skipped: no reference file exists (expected for early phase)

Requires a minimal jakx offline-test config at
  test/offline/config/jakx/config.jsonc
...and reference files under
  test/decompiler/reference/jakx/**/*_REF.gc

For jakx's Phase-0 state (no corpus), this script no-ops cleanly.

Pre-flight static analysis
--------------------------
Before invoking the offline-test binary this script runs three static checks
against all-types.gc that catch patterns which crash the decompiler at load
time (saving the cost of a full binary invocation):

  (a) :inline references to block-commented deftypes
      An active deftype field with :inline TYPE where TYPE is inside #|...|#
      causes "Type X is unknown" SIGABRT during decompiler startup.

  (b) Parent-type activation gaps
      An active deftype whose parent type is block-commented causes the same
      "Type X is unknown" crash — the parent must precede the child.

  (c) Method-count mismatches (declared vs compiled-binary actual)
      Detected by the runtime preflight: offline-test logs
      "Type X has N methods, but method-count-assert was set to M" when the
      :flag-assert declared in all-types.gc disagrees with the compiled object.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_TEST = ROOT / "build" / "Release" / "bin" / "offline-test"
JAKX_CONFIG = ROOT / "test" / "offline" / "config" / "jakx" / "config.jsonc"
JAKX_REFS = ROOT / "test" / "decompiler" / "reference" / "jakx"
ISO_DIR = ROOT / "iso_data"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
ALL_TYPES = ROOT / "decompiler" / "config" / "jakx" / "all-types.gc"


# ---------------------------------------------------------------------------
# Static all-types.gc scanner
# ---------------------------------------------------------------------------

def _mask_block_comments(text: str) -> tuple[str, set[str]]:
    """Replace #|...|# regions with spaces (preserving newlines).

    Returns (masked_text, commented_deftype_names).
    Preserving newlines keeps line numbers stable so error messages are accurate.
    """
    commented: set[str] = set()
    parts: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if i + 1 < n and text[i] == '#' and text[i + 1] == '|':
            end = text.find('|#', i + 2)
            if end == -1:
                parts.append(text[i:])
                break
            block = text[i:end + 2]
            for m in re.finditer(r'\(deftype\s+(\S+)', block):
                commented.add(m.group(1))
            # Replace non-newline chars with space to preserve line numbering.
            parts.append(''.join('\n' if c == '\n' else ' ' for c in block))
            i = end + 2
        else:
            parts.append(text[i])
            i += 1
    return ''.join(parts), commented


# GOAL built-in types that are always registered by the decompiler at startup.
# A deftype that inherits from one of these won't crash even if that name is
# absent from / commented in all-types.gc.
_GOAL_BUILTIN_TYPES: frozenset[str] = frozenset({
    "object", "structure", "basic", "string", "symbol",
    "array", "inline-array", "inline-array-class",
    "integer", "int", "uint",
    "int8", "int16", "int32", "int64",
    "uint8", "uint16", "uint32", "uint64", "uint128", "int128",
    "float", "number",
    "pointer", "function",
    "process", "process-tree", "dead-pool",
    "type", "link-block", "kheap",
    "none", "binteger",
})


def _scan_all_types_static(all_types_path: Path) -> list[str]:
    """Statically scan all-types.gc for patterns that crash the decompiler at load time.

    Returns a list of human-readable blocker strings (empty = no blockers found).

    Checks:
      (a) Active deftype fields that use ':inline TYPE' where TYPE is block-commented.
          Crash: "Type X is unknown" SIGABRT at decompiler startup.
      (b) Active deftypes whose parent type is block-commented.
          Crash: same "Type X is unknown" SIGABRT.
      (c) Active deftypes whose parent is active but defined LATER in the file
          (forward-reference ordering).  The GOAL reader processes the file
          top-to-bottom; a child before its parent crashes identically to (b).

    Method-count mismatches (d) require the compiled binary and are detected
    by the runtime preflight.
    """
    if not all_types_path.exists():
        return []

    text = all_types_path.read_text(errors='replace')
    active, commented = _mask_block_comments(text)
    if not commented:
        return []

    # A type that appears in BOTH a comment block AND active code is active
    # (e.g., after a reorder fix the old commented copy is still present).
    # Remove such names from the "commented" set so we don't false-positive on them.
    active_deftype_names: set[str] = {
        m.group(1) for m in re.finditer(r'\(deftype\s+(\S+)', active)
    }
    commented -= active_deftype_names
    # GOAL built-ins are always registered by the decompiler at startup; they
    # won't cause "Type X is unknown" even when absent from all-types.gc.
    commented -= _GOAL_BUILTIN_TYPES

    if not commented:
        return []

    blockers: list[str] = []
    lines = active.splitlines()

    # (b) Active deftypes with commented parent
    # Pattern: (deftype child-name (parent-name)
    parent_re = re.compile(r'\(deftype\s+(\S+)\s+\((\S+)\)')
    for lineno, line in enumerate(lines, 1):
        m = parent_re.search(line)
        if m:
            child, parent = m.group(1), m.group(2)
            if parent in commented:
                blockers.append(
                    f"[parent-gap] '{child}' active but parent '{parent}' is"
                    f" block-commented — all-types.gc:{lineno}"
                )

    # (c) Active deftypes whose parent is active but defined later (forward-ref ordering).
    # Walk active text line-by-line tracking which types have been defined so far.
    # A child that references a not-yet-defined parent crashes the same as (b).
    defined_so_far: set[str] = set(_GOAL_BUILTIN_TYPES)
    for lineno, line in enumerate(lines, 1):
        m = parent_re.search(line)
        if m:
            child, parent = m.group(1), m.group(2)
            if parent not in defined_so_far and parent not in commented:
                # parent is active (not commented) but not yet seen — forward ref
                blockers.append(
                    f"[forward-ref] '{child}' active at line {lineno} but parent"
                    f" '{parent}' defined later — add declare-type or reorder"
                )
            defined_so_far.add(child)

    # (a) Active fields with ':inline TYPE' where TYPE is block-commented.
    # Field syntax variants:
    #   (field-name TYPE :inline ...)
    #   (field-name TYPE N :inline ...)         <- inline-array shorthand
    #
    # Strategy: capture (field-name TYPE rest-until-close-paren), then check
    # whether ':inline' appears in rest.  This avoids a greedy [^)]* consuming
    # ':inline' before the end-anchor can match.
    deftype_name_re = re.compile(r'\(deftype\s+(\S+)')
    inline_field_re = re.compile(
        r'\(\s*\S+\s+'   # ( field-name
        r'(\S+)'         # TYPE (group 1)
        r'([^)]*)\)'     # rest of field until ')' (group 2)
    )
    # Also handle (inline-array TYPE N) form used in some field definitions.
    inline_array_re = re.compile(r'\(inline-array\s+(\S+)')

    current_deftype = 'unknown'
    for lineno, line in enumerate(lines, 1):
        dt_m = deftype_name_re.search(line)
        if dt_m:
            current_deftype = dt_m.group(1)

        for m in inline_field_re.finditer(line):
            field_type = m.group(1)
            rest = m.group(2)
            if ':inline' in rest and field_type in commented:
                blockers.append(
                    f"[inline-commented] '{current_deftype}' has field with"
                    f" ':inline {field_type}' but '{field_type}' is block-commented"
                    f" — all-types.gc:{lineno}"
                )

        for m in inline_array_re.finditer(line):
            arr_type = m.group(1)
            if arr_type in commented:
                blockers.append(
                    f"[inline-array-commented] '{current_deftype}' has"
                    f" '(inline-array {arr_type} ...)' but '{arr_type}' is"
                    f" block-commented — all-types.gc:{lineno}"
                )

    return blockers


def main() -> int:
    if not OFFLINE_TEST.exists():
        print("offline-test binary missing — build it:")
        print("  cmake --build build/Release --target offline-test -j")
        return 0
    if not JAKX_CONFIG.exists():
        print(f"skipped: jakx offline-test config missing at {JAKX_CONFIG.relative_to(ROOT)}")
        print("         (Phase-0 work item — create config + reference corpus)")
        return 0
    if not JAKX_REFS.exists() or not any(JAKX_REFS.rglob("*_REF.gc")):
        print(f"skipped: no jakx reference files under {JAKX_REFS.relative_to(ROOT)}")
        print("         run offline-test with --dump_current_output once, then commit "
              "cleaned _REF.gc files")
        return 0

    snap = json.loads(LATEST.read_text()) if LATEST.exists() else None
    if not snap:
        print("no latest snapshot — run measure.py first")
        return 1

    # Only check files that made it to real-clean.
    candidates = sorted(
        name for name, v in snap["per_file"].items() if v["category"] == "real-clean"
    )
    print(f"real-clean candidates: {len(candidates)}")

    # -----------------------------------------------------------------------
    # Static pre-flight: scan all-types.gc before invoking the binary.
    # Catches (a) :inline refs to commented types and (b) parent-gap activations
    # — both cause SIGABRT at decompiler startup, making the binary preflight
    # useless.  Surface them here so Agent 1/2 get a precise fix target.
    # -----------------------------------------------------------------------
    if ALL_TYPES.exists():
        static_blockers = _scan_all_types_static(ALL_TYPES)
        if static_blockers:
            blocker_text = "; ".join(static_blockers)
            print(f"STATIC BLOCKER: all-types.gc has {len(static_blockers)} issue(s)"
                  f" that crash the decompiler at load time:")
            for b in static_blockers:
                print(f"  {b}")
            snap["offline_test"] = {
                "green": [],
                "amber": [],
                "blocked": True,
                "blocker": f"static: {blocker_text}",
                "static_blockers": static_blockers,
                "candidates": len(candidates),
            }
            LATEST.write_text(json.dumps(snap, indent=2))
            return 0

    # -----------------------------------------------------------------------
    # Runtime pre-flight: run offline-test once against the first candidate
    # to detect compile-setup blockers that require the binary
    # (e.g., language-enum mismatch, method-count-assert mismatch).
    # If found, surface it and stop — no point running N files that all hit the
    # same setup failure.
    # -----------------------------------------------------------------------
    preflight = subprocess.run(
        [
            str(OFFLINE_TEST),
            "--iso_data_path", str(ISO_DIR / "jakx"),
            "--game", "jakx",
            "--file", candidates[0] if candidates else "NONE",
        ],
        capture_output=True, text=True, check=False, timeout=180,
    )
    pre_out = preflight.stdout + preflight.stderr
    setup_blocker = None
    clean_pre = re.sub(r"\x1b\[[0-9;]*m", "", pre_out)

    if "Inconsistent type definition" in pre_out:
        m = re.search(r"Type ([\w<>!?:\-\+\*/=]+) was originally", pre_out)
        tname = m.group(1) if m else "<unknown>"
        setup_blocker = (
            f"all-types.gc vs kernel-defs.gc type mismatch on '{tname}'. "
            f"Fix: reconcile the defenum/deftype in decompiler/config/jakx/all-types.gc "
            f"with goal_src/jakx/kernel-defs.gc (use the 25-entry version jak3 has)."
        )
    elif "-- Type Error! --" in pre_out or "Type Error: Type" in pre_out:
        # Usually "Type X is unknown when parsing decompiler type file:Y:Z"
        # — a dependency type missing from all-types.gc
        m = re.search(
            r"Type Error: Type ([\w<>!?:\-\+\*/=]+) is unknown[^\n]*\n[^\n]*"
            r"decompiler type file:([^\s:]+?):(\d+)[^\n]*\n\s*\(([^\n]*)",
            clean_pre,
        )
        if m:
            unk, fpath, line, form = m.group(1), m.group(2), m.group(3), m.group(4).strip()[:80]
            setup_blocker = (
                f"unknown type '{unk}' at {fpath}:{line} (in form: ({form}). "
                f"Add a deftype / declare-type / define-extern for '{unk}' in all-types.gc."
            )
        else:
            m2 = re.search(r"(Type Error: Type [\w<>!?:\-\+\*/=]+ is unknown[^\n]*)", clean_pre)
            if m2:
                setup_blocker = m2.group(1)
            else:
                # Catch remaining -- Type Error! -- variants with file context
                m3 = re.search(
                    r"-- Type Error! --\s*\n(.*?)\n.*?decompiler type file:([^\s:]+?):(\d+)",
                    clean_pre, re.DOTALL,
                )
                if m3:
                    detail = m3.group(1).strip()[:120]
                    fpath, line = m3.group(2), m3.group(3)
                    setup_blocker = f"Type Error at {fpath}:{line}: {detail}"
                else:
                    last_lines = "\n  ".join(clean_pre.strip().splitlines()[-10:])
                    setup_blocker = f"Type Error parsing all-types.gc — last output:\n  {last_lines}"
    elif "has" in pre_out and "methods, but method-count-assert" in pre_out:
        # (c) Method-count mismatch: active deftype declares the wrong count
        # vs what the compiled binary actually has.
        # Error: "Type X has N methods, but method-count-assert was set to M
        #         when parsing decompiler type file:...:LINE"
        m = re.search(
            r"Type ([\w\-]+) has (\d+) methods, but method-count-assert was set to (\d+)"
            r"[^\n]*\n[^\n]*decompiler type file:([^\s:]+?):(\d+)",
            clean_pre,
        )
        if m:
            tname, actual, declared, fpath, lineno = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            )
            # Compute correct flag-assert prefix: actual_hex << 20 combined with
            # existing size-assert.  Surface the raw numbers; agent fixes manually.
            setup_blocker = (
                f"method-count mismatch: '{tname}' :method-count-assert {declared}"
                f" but binary has {actual} methods — {fpath}:{lineno}."
                f" Update :flag-assert to #x{int(actual):04x}... in all-types.gc."
            )
        else:
            m2 = re.search(
                r"([\w\-]+ has \d+ methods, but method-count-assert[^\n]*)", clean_pre
            )
            setup_blocker = (
                m2.group(1) if m2
                else "method-count-assert mismatch (couldn't parse detail)"
            )
    elif "Tried to place field" in pre_out and "not aligned correctly" in pre_out:
        # Alignment error: "Tried to place field X at N, but it is not aligned correctly,
        # requires M-byte alignment"
        m = re.search(
            r"Tried to place field ([\w\-]+) at (\d+), but it is not aligned correctly"
            r"[^\n]*requires (\d+)-byte alignment"
            r"[^\n]*\n[^\n]*decompiler type file:([^\s:]+?):(\d+)",
            clean_pre,
        )
        if m:
            field, offset, align, fpath, line = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            )
            setup_blocker = (
                f"field '{field}' at offset {offset} is not {align}-byte aligned "
                f"at {fpath}:{line}. "
                f"Fix: use :offset {align * ((int(offset) + int(align) - 1) // int(align))} "
                f"or restructure preceding fields."
            )
        else:
            m2 = re.search(
                r"(Tried to place field [\w\-]+ at \d+, but it is not aligned[^\n]*)", clean_pre
            )
            setup_blocker = m2.group(1) if m2 else "field alignment error (couldn't parse detail)"
    elif "but offset-assert was set to" in pre_out or "but it was placed at" in pre_out:
        # Offset assertion failure: "Field X was placed at N but offset-assert was set to M"
        m = re.search(
            r"Field ([\w\-]+) was placed at (\d+) but offset-assert was set to (\d+)"
            r"[^\n]*\n[^\n]*decompiler type file:([^\s:]+?):(\d+)",
            clean_pre,
        )
        if not m:
            m = re.search(
                r"field ([\w\-]+).*?placed at (\d+).*?offset-assert.*?(\d+)"
                r".*?decompiler type file:([^\s:]+?):(\d+)",
                clean_pre, re.DOTALL,
            )
        if m:
            field, actual, expected, fpath, line = (
                m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            )
            setup_blocker = (
                f"field '{field}' placed at {actual} but offset-assert={expected} "
                f"at {fpath}:{line}. "
                f"Check preceding field sizes / alignment; adjust :offset-assert or fix field layout."
            )
        else:
            m2 = re.search(r"(Field [\w\-]+ was placed at \d+[^\n]*)", clean_pre)
            setup_blocker = m2.group(1) if m2 else "offset-assert mismatch (couldn't parse detail)"
    elif preflight.returncode not in (0, None) and "Compiler Exception" in pre_out:
        setup_blocker = (
            "offline-test compiler setup threw. Last 20 lines of output:\n  "
            + "\n  ".join(pre_out.strip().splitlines()[-20:])
        )
    elif preflight.returncode is not None and preflight.returncode < 0:
        # SIGABRT or other signal crash not caught by the patterns above.
        # Show more context — last 15 lines, stripping ANSI.
        last_lines = "\n  ".join(clean_pre.strip().splitlines()[-15:])
        setup_blocker = (
            f"offline-test crashed (signal {-preflight.returncode}). "
            f"Last output:\n  {last_lines}"
        )

    if setup_blocker:
        print(f"BLOCKER: offline-test setup fails on ALL files.")
        print(f"  {setup_blocker}")
        snap["offline_test"] = {
            "green": [],
            "amber": [],
            "blocked": True,
            "blocker": setup_blocker,
            "candidates": len(candidates),
        }
        LATEST.write_text(json.dumps(snap, indent=2))
        return 0

    results = {"green": [], "amber": [], "amber_reasons": {}}

    for name in candidates:
        r = subprocess.run(
            [
                str(OFFLINE_TEST),
                "--iso_data_path", str(ISO_DIR / "jakx"),
                "--game", "jakx",
                "--file", name,
                "--fail-on-cmp",
            ],
            capture_output=True, text=True, check=False, timeout=120,
        )
        out = r.stdout + r.stderr
        if r.returncode == 0:
            results["green"].append(name)
        elif "no reference" in out.lower():
            pass
        else:
            results["amber"].append(name)
            clean = re.sub(r"\x1b\[[0-9;]*m", "", out)
            reason = "unknown"
            form = ""
            m = re.search(r"-- Compilation Error! --\s*\n(.+?)\n", clean)
            if m:
                reason = m.group(1).strip()
            m = re.search(r"Form:\s*\n(.+?)\n", clean)
            if m:
                form = m.group(1).strip()
            elif "diff" in clean.lower() and "---" in clean:
                reason = "REF mismatch (decomp output differs from checked-in _REF.gc)"
                form = ""
            results["amber_reasons"][name] = {"reason": reason[:180], "form": form[:120]}

    print(f"green  (offline-test passing):  {len(results['green'])}")
    print(f"amber  (decomps, bytecode mismatch): {len(results['amber'])}")
    if results["green"]:
        print()
        print("GREEN files:")
        for n in results["green"]:
            print(f"  ✓ {n}")
    if results["amber"]:
        print()
        print("AMBER files (top 20):")
        for n in results["amber"][:20]:
            print(f"  ~ {n}")

    # Persist into the latest snapshot for downstream tooling.
    snap["offline_test"] = {
        "green": results["green"],
        "amber": results["amber"],
        "amber_reasons": results.get("amber_reasons", {}),
        "candidates": len(candidates),
    }
    LATEST.write_text(json.dumps(snap, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
