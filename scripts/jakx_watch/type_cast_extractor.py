#!/usr/bin/env python3
"""Emit type_casts.jsonc entries for unresolved "Could not figure out load" errors.

The decompiler emits

    ;; ERROR: failed type prop at N: Could not figure out load: (set! DST (LOAD (+ SRC OFFS)))

when it cannot infer the type of SRC. The fix is a line in
``decompiler/config/jakx/ntsc_v1/type_casts.jsonc`` of the form::

    "caller-name": [
      [op_N, "src_reg", "cast-type"],
      ...
    ]

This script scans the decomp output for those errors and proposes cast entries
using two conservative heuristics:

  * **offs=-4 → basic**         `(l.wu (+ REG -4))` reads the type tag. Cast
    REG to ``basic``. Per ``gotchas.md`` #9 this is the top error cluster and
    the safest single-register cast.
  * **jak3 port**               If jak3's type_casts.jsonc has an entry for the
    same (caller, op, reg) triple, port the cast literally. Many jakx files
    are line-for-line ports from jak3 so the same cast applies.

Entries are deduped against the current jakx type_casts.jsonc (including
range-form entries ``[[lo, hi], reg, type]``) before being written.

Edits are gated via ``apply_guard.run_with_guard()`` — the decompiler is
re-run after applying and any regression reverts the edit. Use ``--commit`` to
auto-commit on pass.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from apply_guard import run_with_guard  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DECOMP_OUT_PRIMARY = ROOT / ".jakx_watch" / "decomp_out" / "jakx"
DECOMP_OUT_FALLBACK = ROOT / "decompiler_out" / "jakx"
TYPE_CASTS_JAKX = ROOT / "decompiler" / "config" / "jakx" / "ntsc_v1" / "type_casts.jsonc"
TYPE_CASTS_JAK3 = ROOT / "decompiler" / "config" / "jak3" / "ntsc_v1" / "type_casts.jsonc"


# --- error parsing (mirrors load_offset_scan.py) --------------------------

RE_LOAD_ERR = re.compile(
    r"^;; ERROR: failed type prop at (\d+): "
    r"Could not figure out load: \(set! (\S+) \((l\.\w+) (\([^\n]+\)|\S+)\)\)$",
    re.MULTILINE,
)
RE_DEF_METHOD = re.compile(
    r"^;; definition for method (\d+) of type ([\w<>!?:\-\+\*/=]+)",
    re.MULTILINE,
)
RE_DEF_FUNCTION = re.compile(
    r"^;; definition for function ([\w<>!?:\-\+\*/=]+)",
    re.MULTILINE,
)
RE_LOAD_WITH_OFFS = re.compile(r"^\(\+\s+(\S+)\s+(-?\d+)\)$")


# --- jsonc parsing --------------------------------------------------------

def load_jsonc(path: Path) -> dict:
    """Parse a jsonc file (JSON with // line comments)."""
    text = path.read_text(errors="replace")
    clean_lines = []
    for line in text.splitlines():
        # Strip // comments but leave // inside strings alone (very rare here)
        # Simple heuristic: if the // is after an odd number of "s it's in a
        # string — but none of the existing files use strings containing //.
        idx = line.find("//")
        if idx != -1:
            line = line[:idx]
        clean_lines.append(line)
    return json.loads("\n".join(clean_lines))


def entry_covers_op(entry: list, op_num: int) -> bool:
    """Does this type_casts entry's op-range cover op_num?"""
    op_spec = entry[0]
    if isinstance(op_spec, int):
        return op_spec == op_num
    if isinstance(op_spec, list) and len(op_spec) == 2:
        lo, hi = op_spec
        return lo <= op_num <= hi
    return False


def existing_covers(existing_casts: dict, fn_key: str, op_num: int, reg: str) -> bool:
    """Is there already an entry for (fn_key, op_num, reg)?"""
    entries = existing_casts.get(fn_key, [])
    for e in entries:
        if len(e) < 3:
            continue
        if e[1] != reg:
            continue
        if entry_covers_op(e, op_num):
            return True
    return False


# --- caller classification -----------------------------------------------

def classify_caller(text: str, err_pos: int) -> str | None:
    """Walk backward from err_pos to find enclosing defmethod/defun label.

    Returns a string compatible with the type_casts.jsonc keys:
      * ``"fn-name"`` for functions
      * ``"(method N type)"`` for methods
    """
    window_start = max(0, err_pos - 4000)
    window = text[window_start:err_pos]
    last_method = None
    for m in RE_DEF_METHOD.finditer(window):
        last_method = (int(m.group(1)), m.group(2), m.start())
    last_function = None
    for m in RE_DEF_FUNCTION.finditer(window):
        last_function = (m.group(1), m.start())
    candidates = []
    if last_method:
        candidates.append(("method", last_method))
    if last_function:
        candidates.append(("function", last_function))
    if not candidates:
        return None
    candidates.sort(key=lambda c: -c[1][-1])
    kind, payload = candidates[0]
    if kind == "method":
        return f"(method {payload[0]} {payload[1]})"
    return payload[0]


# --- error scanning -------------------------------------------------------

def scan_errors(decomp_dir: Path) -> list[tuple[str, str, int, str, str, int | None]]:
    """Return list of (file_stem, caller, op_num, dst_reg, src_reg, offs|None)."""
    out = []
    for fp in sorted(decomp_dir.glob("*_disasm.gc")):
        try:
            text = fp.read_text(errors="replace")
        except OSError:
            continue
        stem = fp.name[: -len("_disasm.gc")]
        for m in RE_LOAD_ERR.finditer(text):
            op_num = int(m.group(1))
            dst_reg = m.group(2)
            # op_name = m.group(3)  # currently unused — reg-type does not depend on load width
            tail = m.group(4)
            caller = classify_caller(text, m.start())
            if caller is None:
                continue
            offs = None
            src_reg = tail
            mm = RE_LOAD_WITH_OFFS.match(tail)
            if mm:
                src_reg = mm.group(1)
                offs = int(mm.group(2))
            out.append((stem, caller, op_num, dst_reg, src_reg, offs))
    return out


def pick_decomp_dir() -> Path:
    return DECOMP_OUT_PRIMARY if DECOMP_OUT_PRIMARY.exists() else DECOMP_OUT_FALLBACK


# --- jak3 port lookup -----------------------------------------------------

def jak3_lookup(jak3_casts: dict, fn_key: str, op_num: int, reg: str) -> str | None:
    """Return the jak3 cast type for (fn, op, reg) if present, else None."""
    for e in jak3_casts.get(fn_key, []):
        if len(e) < 3:
            continue
        if e[1] != reg:
            continue
        if entry_covers_op(e, op_num):
            return e[2]
    return None


def jak3_fuzzy_lookup(jak3_casts: dict, fn_key: str, reg: str) -> str | None:
    """Return the jak3 cast type for (fn, reg) only when unambiguous.

    Looser match: if jak3's same function has entries for the same register
    and ALL of them agree on a single cast-type, apply that type here. Skip
    if the jak3 function uses the same reg for multiple different types
    (e.g. v1 at op 5 is ``pair`` but v1 at op 50 is ``symbol``).

    Useful because jakx op numbers drift from jak3 due to basic-block
    reordering, so exact (op, reg) lookup misses ports that an author
    would clearly apply by hand.
    """
    reg_types = set()
    for e in jak3_casts.get(fn_key, []):
        if len(e) < 3 or e[1] != reg:
            continue
        reg_types.add(e[2])
    if len(reg_types) == 1:
        return next(iter(reg_types))
    return None


# --- heuristics -----------------------------------------------------------

def propose_cast(
    err: tuple,
    existing_casts: dict,
    jak3_casts: dict,
    enable_fuzzy: bool = False,
) -> tuple[str, str] | None:
    """Return (cast_type, heuristic_name) for this error, or None if skipped."""
    stem, caller, op_num, dst_reg, src_reg, offs = err

    # Already covered? Skip.
    if existing_covers(existing_casts, caller, op_num, src_reg):
        return None

    # Heuristic D — jak3 port (strict match).
    ported = jak3_lookup(jak3_casts, caller, op_num, src_reg)
    if ported is not None:
        return (ported, "jak3-port")

    # Heuristic A — type-header read via offs=-4.
    if offs == -4:
        # Skip if src is the gp/sp/fp global-pointer — those aren't basics.
        if src_reg not in ("gp", "fp", "sp"):
            return ("basic", "neg4-basic")

    # Heuristic E — fuzzy jak3 port (only if --fuzzy enabled).
    if enable_fuzzy:
        fuzzy = jak3_fuzzy_lookup(jak3_casts, caller, src_reg)
        if fuzzy is not None:
            return (fuzzy, "jak3-port-fuzzy")

    return None


# --- jsonc writing --------------------------------------------------------

def _format_entry(entry: list) -> str:
    """Compact one-liner: [op, "reg", "type"]."""
    e0 = json.dumps(entry[0]) if isinstance(entry[0], list) else str(entry[0])
    return f"    [{e0}, {json.dumps(entry[1])}, {json.dumps(entry[2])}]"


def append_new_keys(path: Path, new_keys: dict[str, list[list]]) -> None:
    """Append *brand-new* top-level keys to jsonc without parsing-and-rewriting.

    Preserves existing formatting + // comments. Keys that already exist in
    the file are NOT supported here — the caller must filter those out.
    """
    raw = path.read_text(errors="replace")
    rstrip = raw.rstrip()
    if not rstrip.endswith("}"):
        raise ValueError(f"{path}: expected file to end with '}}'")

    body = rstrip[:-1].rstrip()
    if not body.endswith(","):
        body = body + ","

    parts = [body]
    keys = sorted(new_keys.keys())
    for i, key in enumerate(keys):
        entries = new_keys[key]
        is_last = i == len(keys) - 1
        parts.append(f"  {json.dumps(key)}: [")
        for j, entry in enumerate(entries):
            ecomma = "," if j < len(entries) - 1 else ""
            parts.append(f"{_format_entry(entry)}{ecomma}")
        parts.append("  ]" + ("," if not is_last else ""))

    parts.append("}")
    path.write_text("\n".join(parts) + "\n")


def extend_existing_key(path: Path, key: str, new_entries: list[list]) -> bool:
    """Insert new_entries into the existing array for ``key``.

    Textual surgery: find the line ``"key": [``, walk to its closing ``]``,
    ensure the previous line ends with a comma, insert new entries (one per
    line) before the ``]``.
    """
    raw = path.read_text(errors="replace")
    lines = raw.splitlines(keepends=True)

    key_pat = re.compile(
        r'^\s*' + re.escape(json.dumps(key)) + r'\s*:\s*\['
    )

    start_idx = -1
    for i, line in enumerate(lines):
        if key_pat.match(line):
            start_idx = i
            break
    if start_idx < 0:
        return False

    # Find matching close ] by bracket depth starting at the '[' on this line.
    depth = 0
    end_idx = -1
    for i in range(start_idx, len(lines)):
        line = lines[i]
        # Strip comments for depth count so // doesn't confuse us.
        stripped = line.split("//", 1)[0]
        for ch in stripped:
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx >= 0:
            break
    if end_idx < 0:
        return False

    # Find last non-empty line inside; ensure it ends with a comma (before any
    # trailing whitespace/newline). Walk backward from end_idx - 1.
    last_content_idx = -1
    for i in range(end_idx - 1, start_idx, -1):
        content = lines[i].split("//", 1)[0].strip()
        if content:
            last_content_idx = i
            break

    if last_content_idx >= 0:
        # Need to append "," to this line before the newline
        line = lines[last_content_idx]
        # Strip trailing whitespace/newline, add comma, restore newline
        m = re.match(r"^(.*?)(\s*)$", line, re.DOTALL)
        body_part = m.group(1)
        trail = m.group(2)
        # Split body into code + trailing-comment
        cm = body_part.find("//")
        if cm != -1:
            code = body_part[:cm].rstrip()
            comment = body_part[cm:]
            if not code.endswith(","):
                code = code + ","
            lines[last_content_idx] = code + " " + comment + trail
        else:
            code = body_part.rstrip()
            if not code.endswith(","):
                code = code + ","
            lines[last_content_idx] = code + trail

    insertion = []
    for j, entry in enumerate(new_entries):
        ecomma = "," if j < len(new_entries) - 1 else ""
        insertion.append(f"{_format_entry(entry)}{ecomma}\n")

    lines[end_idx:end_idx] = insertion
    path.write_text("".join(lines))
    return True


# --- main -----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="Print proposed entries without writing (default)")
    ap.add_argument("--apply", action="store_true",
                    help="Write type_casts.jsonc and run regression guard")
    ap.add_argument("--batch-size", type=int, default=0,
                    help="Cap entries at N (0 = unlimited)")
    ap.add_argument("--decomp-out", default=None,
                    help="Override decomp output dir")
    ap.add_argument("--commit", action="store_true",
                    help="Auto-commit if guard passes")
    ap.add_argument("--only-heuristic",
                    choices=["jak3-port", "neg4-basic", "jak3-port-fuzzy"],
                    default=None, help="Restrict to one heuristic")
    ap.add_argument("--fuzzy", action="store_true",
                    help="Also apply jak3-port-fuzzy (same fn+reg, unambiguous)")
    ap.add_argument("--err-slack", type=int, default=0,
                    help="Allow this many new errors before veto. Bump for "
                         "noisy environments where decompiler crashes vary the "
                         "pre-state file count (default 0 = strict).")
    args = ap.parse_args()

    if args.apply:
        args.dry_run = False

    decomp_dir = Path(args.decomp_out) if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"ERROR: decomp_out not found: {decomp_dir}", file=sys.stderr)
        return 1

    print(f"decomp_out:     {decomp_dir}")
    print(f"type_casts:     {TYPE_CASTS_JAKX.relative_to(ROOT)}")
    print(f"jak3 ref casts: {TYPE_CASTS_JAK3.relative_to(ROOT)}")

    print("Loading existing jakx type_casts ...", end=" ", flush=True)
    existing_casts = load_jsonc(TYPE_CASTS_JAKX)
    print(f"{len(existing_casts)} keys, "
          f"{sum(len(v) for v in existing_casts.values())} entries")

    print("Loading jak3 type_casts reference ...", end=" ", flush=True)
    jak3_casts = load_jsonc(TYPE_CASTS_JAK3)
    print(f"{len(jak3_casts)} keys, "
          f"{sum(len(v) for v in jak3_casts.values())} entries")

    print("Scanning decomp output for load errors ...", flush=True)
    errors = scan_errors(decomp_dir)
    print(f"  {len(errors)} 'Could not figure out load' errors across "
          f"{len({e[0] for e in errors})} files")

    # Propose casts, dedup by (fn_key, op_num, reg) within this batch too.
    proposed: dict[str, list[list]] = {}
    heuristic_counts = {"jak3-port": 0, "neg4-basic": 0, "jak3-port-fuzzy": 0}
    skipped_already = 0
    skipped_no_heur = 0
    seen_keys: set[tuple[str, int, str]] = set()

    for err in errors:
        stem, caller, op_num, dst_reg, src_reg, offs = err
        dedup_key = (caller, op_num, src_reg)
        if dedup_key in seen_keys:
            continue
        proposal = propose_cast(err, existing_casts, jak3_casts,
                                enable_fuzzy=args.fuzzy)
        if proposal is None:
            # Figure out *why* we skipped for stats.
            if existing_covers(existing_casts, caller, op_num, src_reg):
                skipped_already += 1
            else:
                skipped_no_heur += 1
            continue
        if args.only_heuristic and proposal[1] != args.only_heuristic:
            continue
        cast_type, heur = proposal
        heuristic_counts[heur] += 1
        seen_keys.add(dedup_key)
        proposed.setdefault(caller, []).append([op_num, src_reg, cast_type])

    total_proposed = sum(len(v) for v in proposed.values())
    print(f"\nProposals: {total_proposed} entries across {len(proposed)} fns")
    for h, c in heuristic_counts.items():
        print(f"  {h:12s}: {c}")
    print(f"  skipped (already covered): {skipped_already}")
    print(f"  skipped (no heuristic):    {skipped_no_heur}")

    if total_proposed == 0:
        print("Nothing to add.")
        return 0

    def _heur_for(fn: str, op_num: int, reg: str) -> str:
        """Best-effort reconstruction of which heuristic produced this entry."""
        if jak3_lookup(jak3_casts, fn, op_num, reg) is not None:
            return "jak3-port"
        if args.fuzzy and jak3_fuzzy_lookup(jak3_casts, fn, reg) is not None:
            return "jak3-port-fuzzy"
        return "neg4-basic"

    # Apply batch cap *after* dedup so repeat-heavy batches don't starve jak3
    # ports (the most trusted heuristic). Sort strict ports first, then
    # fuzzy, then -4 basics.
    if args.batch_size > 0 and total_proposed > args.batch_size:
        priority = {"jak3-port": 0, "neg4-basic": 1, "jak3-port-fuzzy": 2}
        flat: list[tuple[str, list, int]] = []
        for fn, entries in proposed.items():
            for e in entries:
                op_num = e[0] if isinstance(e[0], int) else e[0][0]
                flat.append((fn, e, priority[_heur_for(fn, op_num, e[1])]))
        flat.sort(key=lambda t: t[2])
        flat = flat[: args.batch_size]
        proposed = {}
        for fn, e, _ in flat:
            proposed.setdefault(fn, []).append(e)
        total_proposed = sum(len(v) for v in proposed.values())
        print(f"  batch cap applied: now {total_proposed} entries "
              f"across {len(proposed)} fns")

    # Print a preview
    print("\nPreview:")
    shown = 0
    for fn, entries in sorted(proposed.items()):
        entries.sort(key=lambda e: (e[0] if isinstance(e[0], int) else e[0][0]))
        print(f"  {fn}:")
        for e in entries:
            op_num = e[0] if isinstance(e[0], int) else e[0][0]
            marker = f" ({_heur_for(fn, op_num, e[1])})"
            print(f"    [{e[0]}, {e[1]!r}, {e[2]!r}]{marker}")
            shown += 1
            if shown >= 60 and args.dry_run:
                break
        if shown >= 60 and args.dry_run:
            print(f"  ... (preview truncated; {total_proposed - shown} more)")
            break

    if args.dry_run:
        print("\n--dry-run: pass --apply to write and gate.")
        return 0

    # --- apply via guard ---
    def do_apply() -> list[Path]:
        # Split proposed into (new keys) and (extend existing).
        brand_new: dict[str, list[list]] = {}
        to_extend: dict[str, list[list]] = {}
        for fn, entries in proposed.items():
            if fn in existing_casts:
                to_extend[fn] = entries
            else:
                brand_new[fn] = entries

        # Extend existing keys first (in-place text edits, independent of each other).
        for fn, entries in sorted(to_extend.items()):
            entries.sort(key=lambda e: (e[0] if isinstance(e[0], int) else e[0][0]))
            ok = extend_existing_key(TYPE_CASTS_JAKX, fn, entries)
            if not ok:
                print(f"WARN: failed to extend existing key {fn!r}", file=sys.stderr)

        # Then append brand-new keys.
        if brand_new:
            append_new_keys(TYPE_CASTS_JAKX, brand_new)

        return [TYPE_CASTS_JAKX]

    n = total_proposed
    commit_msg = (
        f"fix(jakx/type-casts): extract {n} casts from unresolved loads\n\n"
        f"Heuristics: jak3-port={heuristic_counts['jak3-port']}  "
        f"neg4-basic={heuristic_counts['neg4-basic']}.  "
        f"Gated via apply_guard (err_slack=0, warn_slack=5).\n\n"
        f"Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    print(f"\nApplying {n} entries via apply_guard (err_slack={args.err_slack}) ...")
    result = run_with_guard(
        do_apply,
        label=f"type-cast-extract/{n}-entries",
        err_slack=args.err_slack,
        warn_slack=max(5, args.err_slack),
        commit_on_pass=args.commit,
        commit_message=commit_msg,
    )

    if not result.passed:
        print(f"FAIL: {result.reason}", file=sys.stderr)
        return 1

    print(f"PASS: Δerr={result.delta_err:+d}  Δwarn={result.delta_warn:+d}")
    if args.commit and result.commit_sha:
        print(f"  committed as {result.commit_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
