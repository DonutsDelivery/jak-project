#!/usr/bin/env python3
"""Categorize amber (real-clean but bytecode-mismatching) files.

For each amber file from the latest snapshot, run offline-test with
--fail-on-cmp and classify the failure into one of:

  label-method-set  — decompiler emitted raw label LNN in (method-set! ...) for
                      a vtable entry (usually the `new` method pointer).
                      Fix: add label_types.jsonc entry for the label.

  static-ref        — (top-level-login) failed to decode a static data label.
                      Subtypes: enum-missing, object-unknown, struct-unknown-data.
                      Fix: label_types.jsonc or type_casts.jsonc hint.

  typecheck         — goalc type-check failure compiling the output.
                      Fix: type annotation / declare-type in all-types.gc.

  crash             — SIGABRT or signal crash during per-file test.

  pass              — file has become green since snapshot was written.

  other             — does not match the above patterns.

Output: .jakx_watch/amber_categorized.md  (human-readable table + per-file detail)
Also augments latest.json with snap["amber_categories"].
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_TEST = ROOT / "build" / "Release" / "bin" / "offline-test"
ISO_DIR = ROOT / "iso_data"
LATEST = ROOT / ".jakx_watch" / "history" / "latest.json"
OUT_MD = ROOT / ".jakx_watch" / "amber_categorized.md"


def strip_ansi(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def _run_offline_test(name: str) -> tuple[int, str]:
    r = subprocess.run(
        [
            str(OFFLINE_TEST),
            "--iso_data_path", str(ISO_DIR / "jakx"),
            "--game", "jakx",
            "--file", name,
            "--fail-on-cmp",
        ],
        capture_output=True, text=True, check=False, timeout=180,
    )
    return r.returncode, strip_ansi(r.stdout + r.stderr)


def _classify(name: str, rc: int, out: str) -> dict:
    """Return {category, detail, fix_hint}."""

    if rc == 0:
        return {
            "category": "pass",
            "detail": "now passing — REF matches current output",
            "fix_hint": "re-run seed_refs.py --force and retire from amber list",
        }

    if rc < 0:
        # Signal crash
        last = "\n".join(out.strip().splitlines()[-4:])
        return {
            "category": "crash",
            "detail": f"signal {-rc}: {last[:200]}",
            "fix_hint": "investigate SIGABRT; likely a type-load error not caught by preflight",
        }

    # --- label-method-set: (method-set! (the-as type TYPE) N LNN) ---
    m = re.search(
        r"The symbol (L\d+) was looked up as a global variable.*?"
        r"\(method-set! \(the-as type ([\w\-]+)\) (\d+) (L\d+)\)",
        out, re.DOTALL
    )
    if m:
        label, tname, method_idx, label2 = m.group(1), m.group(2), m.group(3), m.group(4)
        return {
            "category": "label-method-set",
            "detail": f"unresolved label {label} in (method-set! (the-as type {tname}) {method_idx} {label})",
            "type": tname,
            "method_idx": int(method_idx),
            "label": label,
            "fix_hint": (
                f"Add label_types.jsonc entry for {label} pointing to the function at that label "
                f"(method {method_idx} of {tname}). Check the _disasm.gc for the label address."
            ),
        }

    # --- static-ref: decompile_at_label failure ---
    m_sr = re.search(
        r"failed static ref: (Unable to 'decompile_at_label' [^\n]+|Unimplemented decompile_at_label[^\n]+)",
        out
    )
    if m_sr:
        reason = m_sr.group(1)
        subtype = "object-unknown"
        if "Failed to decompile integer enum" in out:
            em = re.search(r"Value (\d+) \(0x[0-9a-f]+\) wasn't found in enum ([\w\-]+)", out)
            subtype = f"enum-missing: value {em.group(1)} not in {em.group(2)}" if em else "enum-missing"
        elif "unknown data" in out or "offset" in reason:
            subtype = "struct-unknown-data"
        return {
            "category": "static-ref",
            "subtype": subtype,
            "detail": reason[:200],
            "fix_hint": (
                "Add label_types.jsonc entry to give the decompiler the correct type at the label, "
                "or fix the type definition so struct layout matches the binary."
            ),
        }

    # --- typecheck: goalc type-check failure ---
    m_tc = re.search(r"Typecheck failed\. ([^\n]+)", out)
    if m_tc:
        return {
            "category": "typecheck",
            "detail": m_tc.group(1),
            "fix_hint": (
                "Check the method signature in all-types.gc or add a type-cast in type_casts.jsonc "
                "to satisfy the type checker."
            ),
        }

    # --- any remaining compilation error ---
    if "Compilation Error" in out:
        lines = [l for l in out.splitlines() if l.strip() and not l.startswith("[") and ":" not in l[:3]]
        first_err = next((l for l in lines if l.strip() and not l.startswith(" ")), "")
        return {
            "category": "other",
            "detail": first_err[:200] or "Compilation Error (detail not parsed)",
            "fix_hint": "Inspect offline-test output manually",
        }

    return {
        "category": "other",
        "detail": out.splitlines()[-1][:200] if out.strip() else "no output",
        "fix_hint": "Inspect offline-test output manually",
    }


_CAT_ICON = {
    "pass": "✓",
    "label-method-set": "⚡",
    "static-ref": "⚠",
    "typecheck": "⊗",
    "crash": "💥",
    "other": "?",
}

_CAT_PRIORITY = {
    "label-method-set": 1,
    "static-ref": 2,
    "typecheck": 3,
    "crash": 4,
    "pass": 5,
    "other": 6,
}


def main() -> int:
    if not OFFLINE_TEST.exists():
        print("offline-test binary missing")
        return 1
    if not LATEST.exists():
        print("no latest snapshot — run measure.py first")
        return 1

    snap = json.loads(LATEST.read_text())
    amber = sorted(snap.get("offline_test", {}).get("amber", []))
    if not amber:
        print("no amber files in snapshot — run offline_test_pass.py first")
        return 1

    print(f"categorizing {len(amber)} amber files…")
    results: dict[str, dict] = {}
    for name in amber:
        print(f"  {name}…", end="", flush=True)
        try:
            rc, out = _run_offline_test(name)
        except subprocess.TimeoutExpired:
            results[name] = {"category": "crash", "detail": "timeout", "fix_hint": "timed out"}
            print(" timeout")
            continue
        results[name] = _classify(name, rc, out)
        cat = results[name]["category"]
        print(f" [{cat}]")

    # Sort by priority then name
    ordered = sorted(results.items(), key=lambda kv: (_CAT_PRIORITY.get(kv[1]["category"], 9), kv[0]))

    # --- Write Markdown ---
    lines: list[str] = [
        "# Amber file categorization",
        "",
        f"Generated from {len(amber)} amber files in latest snapshot.",
        "",
        "## Summary table",
        "",
        "| File | Category | Detail |",
        "|------|----------|--------|",
    ]
    for name, info in ordered:
        icon = _CAT_ICON.get(info["category"], "?")
        cat = info["category"]
        detail = info.get("detail", "")[:80].replace("|", "\\|")
        lines.append(f"| `{name}` | {icon} {cat} | {detail} |")

    lines += [
        "",
        "## Fix hints by category",
        "",
    ]

    # Group by category
    by_cat: dict[str, list[tuple[str, dict]]] = {}
    for name, info in ordered:
        by_cat.setdefault(info["category"], []).append((name, info))

    cat_descriptions = {
        "label-method-set": (
            "### ⚡ label-method-set  (unresolved vtable function pointer)\n\n"
            "Root cause: the decompiler emitted a raw label `LNN` instead of a function "
            "reference in a `(method-set! ...)` call. This happens when the label_types.jsonc "
            "file lacks an entry telling the decompiler what type the function at that label has.\n\n"
            "**Fix**: add an entry to `decompiler/config/jakx/label_types.jsonc`:\n"
            "```jsonc\n"
            '  "<object-name>": {"<LNN>": "function"}\n'
            "```\n"
            "Then re-run the decompiler and seed_refs.py --force."
        ),
        "static-ref": (
            "### ⚠ static-ref  (failed to decode static data)\n\n"
            "Root cause: the decompiler's `decompile_at_label` walk failed on a static data "
            "label — either an enum value is missing from a `defenum`, or a struct has unrecognized "
            "bytes at a known offset.\n\n"
            "**Fix**: either add the missing enum entry to all-types.gc, or add a `label_types.jsonc` "
            "hint so the decompiler uses the correct type when walking the data."
        ),
        "typecheck": (
            "### ⊗ typecheck  (goalc type-check failure)\n\n"
            "Root cause: the decompiler output type-checks against the wrong type — "
            "usually a method argument declared as `object` that should be a specific type.\n\n"
            "**Fix**: correct the method signature in all-types.gc, or add a type_casts.jsonc entry."
        ),
        "crash": (
            "### 💥 crash  (SIGABRT / signal during per-file test)\n\n"
            "Root cause: offline-test crashed while processing the file. "
            "Usually a type-load error not caught by the static preflight."
        ),
        "pass": (
            "### ✓ pass  (now green)\n\n"
            "These files have become green since the snapshot was written. "
            "Re-run offline_test_pass.py and seed_refs.py --force to retire them."
        ),
        "other": (
            "### ? other  (unclassified)\n\n"
            "Inspect offline-test output manually."
        ),
    }

    for cat, items in by_cat.items():
        lines.append(cat_descriptions.get(cat, f"### {cat}"))
        lines.append("")
        lines.append("Files:")
        for name, info in items:
            detail = info.get("detail", "")
            hint = info.get("fix_hint", "")
            type_info = ""
            if "type" in info:
                type_info = f"  — type `{info['type']}`, method {info['method_idx']}, label `{info['label']}`"
            lines.append(f"- **`{name}`**{type_info}")
            if detail:
                lines.append(f"  - error: `{detail}`")
            if hint and cat not in ("pass",):
                lines.append(f"  - fix: {hint}")
        lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT_MD.relative_to(ROOT)}")

    # Augment snapshot
    snap["amber_categories"] = {name: info for name, info in results.items()}
    LATEST.write_text(json.dumps(snap, indent=2))

    # Print counts
    cat_counts: dict[str, int] = {}
    for info in results.values():
        cat_counts[info["category"]] = cat_counts.get(info["category"], 0) + 1
    print("\nCategory breakdown:")
    for cat in sorted(cat_counts, key=lambda c: _CAT_PRIORITY.get(c, 9)):
        print(f"  {_CAT_ICON.get(cat, '?')} {cat}: {cat_counts[cat]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
