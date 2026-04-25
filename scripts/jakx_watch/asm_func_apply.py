#!/usr/bin/env python3
"""Add 'function was not converted to expressions' functions to mips2c_functions_by_name.

The decompiler's only mechanism to suppress "function was not converted to
expressions. Cannot decompile." errors is to have the function in
mips2c_functions_by_name in hacks.jsonc.  When present, run_mips2c() is
called on the MIPS bytecode, sets func.mips2c_output, and the decompiler
emits INFO + a rough C++ translation instead of the ERROR marker.

asm_functions_by_name does NOT suppress this error — only mips2c_functions_by_name works.

VU-crash risk: functions with vsqi/viaddi/vlqi/viand/vmtirx/mtlo1/mflo1/
mula.s/madda.s/madd.s opcodes will crash run_mips2c via an InstructionAtom::get_imm
assertion. The scanner checks per-function (not per-file) so only the specific
function bodies containing crash opcodes are skipped — safe functions in VU-heavy
files are still candidates.

Gate: apply_guard.run_with_guard() runs the full decompiler after applying and
reverts hacks.jsonc if total errors increase. Use --commit to auto-commit on pass.

Usage:
    python3 scripts/jakx_watch/asm_func_apply.py --dry-run
    python3 scripts/jakx_watch/asm_func_apply.py --apply
    python3 scripts/jakx_watch/asm_func_apply.py --apply --batch-size 50 --commit
    python3 scripts/jakx_watch/asm_func_apply.py --apply --skip-asm

Options:
    --dry-run        Print candidates without modifying hacks.jsonc (default)
    --apply          Write candidates to mips2c_functions_by_name and run guard
    --batch-size N   Cap the number of new entries added (default: all)
    --skip-asm       Skip functions already in asm_functions_by_name (more cautious)
    --only-asm       Only process functions already in asm_functions_by_name
    --decomp-out     Override decomp_out directory
    --commit         Auto-commit if guard passes (no errors added)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
HACKS_JSONC = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "hacks.jsonc"

# Opcodes that crash run_mips2c — skip any FUNCTION body containing these.
# VU integer/control: vsqi/viaddi/vlqi/viand/vmtirx
# PS2 extended FPU/MAC: mtlo1/mflo1 (extended accumulator), mula.s/madda.s/madd.s
# Label-immediate forms (lui/ori/ld with `L<n>` operand): the mips2c emitter
# calls InstructionAtom::get_imm() expecting an IMM atom but finds a LABEL,
# tripping the same assertion at decompiler/Disasm/Instruction.cpp:118.
# VU float broadcast forms (`v<op>.<bcst>` and `v<op>x[yzw]…`) — same get_imm()
# assertion, observed in race-obs (race-banner-init-by-other → vaddx.w /
# vmaddw.xyz / vmulax.xyzw) and qmtc2.i (interlocked COP2 move).
# Observed crash sites: (method 99 net-player-race) [`lui v1, L914`],
# (method 57 net-game-mgr-deathmatch), race-banner-init-by-other.
VU_CRASH_OPCODES = re.compile(
    r"\b(vsqi|viaddi|vlqi|viand|vmtirx|mtlo1|mflo1|mula\.s|madda\.s|madd\.s)\b"
    r"|\b(lui|ori|ld)\b[^\n]*\bL\d+\b"
    r"|\bv\w*\.(?:x|y|z|w|xy|xz|xw|yz|yw|zw|xyz|xyw|xzw|yzw|xyzw)\b"
    r"|\bqmtc2\.i\b"
)

RE_DEF_FUNCTION = re.compile(r"^;; definition for function ([\w<>!?:\-\+\*/=]+)")
RE_DEF_METHOD = re.compile(r"^;; definition for method (\d+) of type ([\w<>!?:\-\+\*/=]+)")
RE_NOT_CONVERTED = re.compile(r"^;; ERROR: function was not converted to expressions\.")
RE_IR2_FUNC_HEADER = re.compile(r"^; \.function\s+(.+)")


def pick_decomp_dir(override: str | None) -> Path:
    if override:
        return Path(override)
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


# ---------------------------------------------------------------------------
# Per-function VU crash opcode scanner
# ---------------------------------------------------------------------------


def scan_vu_functions(decomp_dir: Path) -> dict[str, set[str]]:
    """Return {file_stem: {fn_key, ...}} for functions containing VU crash opcodes.

    Checks each function body individually rather than skipping entire files.
    fn_key format matches parse_not_converted output:
      - plain function: "function-name"
      - method: "(method N typename)"
    """
    result: dict[str, set[str]] = {}

    for ir2_asm in sorted(decomp_dir.glob("*_ir2.asm")):
        stem = ir2_asm.name[: -len("_ir2.asm")]
        text = ir2_asm.read_text(errors="replace")
        lines = text.splitlines()

        vu_fns: set[str] = set()
        current_fn: str | None = None
        current_body: list[str] = []

        def _flush() -> None:
            if current_fn and VU_CRASH_OPCODES.search("\n".join(current_body)):
                vu_fns.add(current_fn)

        for line in lines:
            m = RE_IR2_FUNC_HEADER.match(line)
            if m:
                _flush()
                label = m.group(1).strip()
                # Only track plain functions and (method N type) — skip (top-level-login …)
                if label.startswith("(method ") or not label.startswith("("):
                    current_fn = label
                else:
                    current_fn = None
                current_body = []
            elif current_fn is not None:
                current_body.append(line)

        _flush()

        if vu_fns:
            result[stem] = vu_fns

    return result


# ---------------------------------------------------------------------------
# Not-converted candidate scanner
# ---------------------------------------------------------------------------


def parse_not_converted(
    decomp_dir: Path,
    vu_functions: dict[str, set[str]],
) -> list[tuple[str, str]]:
    """Parse disasm files and return list of (mips2c_key, source_file).

    Skips only functions whose specific body contains VU crash opcodes,
    NOT entire files that happen to contain any VU opcode anywhere.
    """
    results: list[tuple[str, str]] = []

    for disasm_gc in sorted(decomp_dir.glob("*_disasm.gc")):
        stem = disasm_gc.name[: -len("_disasm.gc")]
        vu_in_file = vu_functions.get(stem, set())

        try:
            text = disasm_gc.read_text(errors="replace")
        except OSError:
            continue

        lines = text.splitlines()
        last_def: str | None = None
        last_def_line = -1

        for lineno, line in enumerate(lines):
            m_fn = RE_DEF_FUNCTION.match(line)
            if m_fn:
                last_def = m_fn.group(1)
                last_def_line = lineno
                continue

            m_mt = RE_DEF_METHOD.match(line)
            if m_mt:
                method_id = int(m_mt.group(1))
                type_name = m_mt.group(2)
                last_def = f"(method {method_id} {type_name})"
                last_def_line = lineno
                continue

            if RE_NOT_CONVERTED.match(line):
                if last_def is not None and (lineno - last_def_line) <= 6:
                    if last_def not in vu_in_file:
                        results.append((last_def, stem))
                last_def = None
                last_def_line = -1

    return results


# ---------------------------------------------------------------------------
# hacks.jsonc parsers
# ---------------------------------------------------------------------------


def load_existing_mips2c(hacks_text: str) -> set[str]:
    """Extract currently-listed function names from mips2c_functions_by_name."""
    in_block = False
    entries: set[str] = set()
    for line in hacks_text.splitlines():
        stripped = line.strip()
        if '"mips2c_functions_by_name"' in stripped:
            in_block = True
            continue
        if in_block:
            if stripped.startswith("]"):
                break
            if stripped.startswith("//"):
                continue
            m = re.match(r'^"([^"]+)"', stripped)
            if m:
                entries.add(m.group(1))
    return entries


def load_existing_asm(hacks_text: str) -> set[str]:
    """Extract currently-listed function names from asm_functions_by_name."""
    in_block = False
    entries: set[str] = set()
    for line in hacks_text.splitlines():
        stripped = line.strip()
        if '"asm_functions_by_name"' in stripped:
            in_block = True
            continue
        if in_block:
            if stripped.startswith("]"):
                break
            if stripped.startswith("//"):
                continue
            m = re.match(r'^"([^"]+)"', stripped)
            if m:
                entries.add(m.group(1))
    return entries


# ---------------------------------------------------------------------------
# hacks.jsonc writer
# ---------------------------------------------------------------------------


def apply_to_hacks(hacks_text: str, new_entries: list[tuple[str, str]]) -> str:
    """Insert new entries into mips2c_functions_by_name and return modified text."""
    lines = hacks_text.splitlines(keepends=True)

    mips2c_start = -1
    for i, line in enumerate(lines):
        if '"mips2c_functions_by_name"' in line:
            mips2c_start = i
            break
    if mips2c_start < 0:
        raise ValueError("mips2c_functions_by_name not found in hacks.jsonc")

    close_bracket_line = -1
    for i in range(mips2c_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("]"):
            close_bracket_line = i
            break
    if close_bracket_line < 0:
        raise ValueError("Could not find closing ] for mips2c_functions_by_name")

    last_entry_line = -1
    for i in range(close_bracket_line - 1, mips2c_start, -1):
        stripped = lines[i].strip()
        if stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
            if re.search(r'"[^"]+"', stripped):
                last_entry_line = i
                break

    if last_entry_line >= 0:
        last_line = lines[last_entry_line].rstrip("\n\r")
        if not last_line.rstrip().endswith(","):
            lines[last_entry_line] = last_line.rstrip() + ",\n"

    timestamp = __import__("datetime").date.today().isoformat()
    new_lines = [f"    // asm-func: auto-added by asm_func_apply.py {timestamp}\n"]

    by_file: dict[str, list[str]] = {}
    for key, src in new_entries:
        by_file.setdefault(src, []).append(key)

    for src in sorted(by_file):
        new_lines.append(f"    // source: {src}\n")
        for key in sorted(by_file[src]):
            new_lines.append(f'    "{key}",\n')

    if new_lines:
        last_new = new_lines[-1].rstrip()
        if last_new.endswith(","):
            new_lines[-1] = last_new[:-1] + "\n"

    lines[close_bracket_line:close_bracket_line] = new_lines

    return "".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Print candidates without modifying hacks.jsonc (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Write candidates to mips2c_functions_by_name and run guard")
    parser.add_argument("--batch-size", type=int, default=0,
                        help="Cap new entries at N (0 = unlimited)")
    parser.add_argument("--skip-asm", action="store_true",
                        help="Skip functions already in asm_functions_by_name")
    parser.add_argument("--only-asm", action="store_true",
                        help="Only process functions already in asm_functions_by_name")
    parser.add_argument("--decomp-out", default=None,
                        help="Override decomp_out directory path")
    parser.add_argument("--commit", action="store_true",
                        help="Auto-commit if guard passes (no errors added)")
    parser.add_argument("--skip-file", default=None,
                        help="Path to a file of candidate keys to exclude "
                             "(one key per line, e.g. 'draw-node-cull' or "
                             "'(method 9 collide-cache)'). Used for known-bad "
                             "entries that crash the decompiler.")
    args = parser.parse_args()

    if args.apply:
        args.dry_run = False

    decomp_dir = pick_decomp_dir(args.decomp_out)
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out dir not found: {decomp_dir}", file=sys.stderr)
        return 1

    if not HACKS_JSONC.exists():
        print(f"ERROR: hacks.jsonc not found: {HACKS_JSONC}", file=sys.stderr)
        return 1

    print(f"decomp_out: {decomp_dir}")

    # Step 1: per-function VU crash opcode scan
    print("Scanning for VU crash opcodes per function ...")
    vu_functions = scan_vu_functions(decomp_dir)
    total_vu_fns = sum(len(v) for v in vu_functions.values())
    print(f"  {total_vu_fns} functions with VU opcodes across {len(vu_functions)} files (skipped)")

    # Step 2: parse 'not converted' functions
    candidates = parse_not_converted(decomp_dir, vu_functions)
    print(f"  {len(candidates)} 'not converted' candidates (VU-safe)")

    # Step 3: load existing sets from hacks.jsonc
    hacks_text = HACKS_JSONC.read_text()
    existing_mips2c = load_existing_mips2c(hacks_text)
    existing_asm = load_existing_asm(hacks_text)

    print(f"  Already in mips2c_functions_by_name: {len(existing_mips2c)}")
    print(f"  Currently in asm_functions_by_name:  {len(existing_asm)}")

    # Step 4a: load skip-file (known-bad candidates)
    skip_keys: set[str] = set()
    if args.skip_file:
        skip_path = Path(args.skip_file)
        if skip_path.exists():
            for line in skip_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    skip_keys.add(line)
            print(f"  Loaded {len(skip_keys)} skip-file entries from {skip_path}")

    # Step 4b: filter
    new_entries: list[tuple[str, str]] = []
    skipped_by_file = 0
    for key, src in candidates:
        if key in existing_mips2c:
            continue
        if key in skip_keys:
            skipped_by_file += 1
            continue
        is_asm = key in existing_asm
        if args.skip_asm and is_asm:
            continue
        if args.only_asm and not is_asm:
            continue
        new_entries.append((key, src))

    already_mips2c = len(candidates) - len(new_entries) - skipped_by_file
    print(f"  Skipped (already mips2c): {already_mips2c}")
    if skipped_by_file:
        print(f"  Skipped (skip-file):      {skipped_by_file}")
    print(f"  New candidates to add:    {len(new_entries)}")

    # Step 5: apply batch size cap
    if args.batch_size > 0 and len(new_entries) > args.batch_size:
        print(f"  Capping at --batch-size {args.batch_size}")
        new_entries = new_entries[: args.batch_size]

    if not new_entries:
        print("Nothing to add.")
        return 0

    # Step 6: print candidates
    print()
    print(f"{'DRY-RUN: would add' if args.dry_run else 'Adding'} {len(new_entries)} entries:")
    by_file: dict[str, list[str]] = {}
    for key, src in new_entries:
        by_file.setdefault(src, []).append(key)
    for src in sorted(by_file):
        print(f"  [{src}]")
        for key in sorted(by_file[src]):
            marker = " (asm)" if key in existing_asm else ""
            print(f"    {key!r}{marker}")

    if args.dry_run:
        print()
        print("Run with --apply to write to hacks.jsonc and gate via apply_guard.")
        return 0

    # Step 7: apply via guard
    n = len(new_entries)
    commit_msg = (
        f"fix(jakx/hacks): mips2c-suppress {n} not-converted fns\n\n"
        f"Per-function VU opcode filter; {n} entries added.\n\n"
        f"Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
    )

    def do_apply() -> list[Path]:
        new_text = apply_to_hacks(hacks_text, new_entries)
        HACKS_JSONC.write_text(new_text)
        return [HACKS_JSONC]

    print(f"\nApplying {n} entries via apply_guard ...")
    result = run_with_guard(
        do_apply,
        label=f"asm-func/{n}-entries",
        err_slack=0,
        warn_slack=5,
        commit_on_pass=args.commit,
        commit_message=commit_msg,
    )

    if not result.passed:
        print(f"✗ Guard failed: {result.reason}", file=sys.stderr)
        return 1

    print(f"✓ Δerr={result.delta_err:+d}  Δwarn={result.delta_warn:+d}")
    if args.commit:
        if result.commit_sha:
            print(f"  Committed as {result.commit_sha}.")
        else:
            print("  (commit_sha not available)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
