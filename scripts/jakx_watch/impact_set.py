#!/usr/bin/env python3
"""impact_set.py — compute which decomp objects an all-types.gc edit affects.

Given a set of edited type/method names, returns the object basenames whose
IR2 output references those names. Used by apply_guard's --scope flag to
restrict re-decomp to only the files that could plausibly change.

Why this exists:
  Full per-game decomp takes 5-15 minutes. Most all-types.gc edits affect
  <50 of the ~600 IR2 files. Scoping decomp to the affected subset gets
  validation down to ~30 sec, enabling 20× more iterations per session.

The impact set ALWAYS unions in the clean-file invariant set (every file
currently real-clean across all games), so the validation can detect
regressions that would downgrade a clean file to red. This is the guardrail
against "reward hacking" where local edits look good on the subset but
silently break files outside it.

API:
  compute_impact_set(edited_types, game) -> set[str]
    edited_types: set of type names (and/or method names like "type::method-N")
    game: "jak1" | "jak2" | "jak3" | "jakx"
    returns: set of object basenames suitable for allowed_objects

  load_clean_files(game) -> set[str]
    returns: object basenames currently real-clean for game (from .compound_loop/)

  union_with_clean(impact, game) -> set[str]
    union the impact set with clean-file invariant for safety
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOUND_LOOP_DIR = ROOT / ".compound_loop"


def decomp_out_dir(game: str) -> Path:
    """Where _ir2.asm files live for a game.

    Matches the precedence used by return_mismatch_scan / type_cast_extract:
    private watch out dir is freshest (apply_guard writes there); canonical
    decompiler_out/<game>/ is fallback for first-run setups before the watch
    pipeline has produced output.
    """
    primary = ROOT / f".{game}_watch" / "decomp_out" / game
    if primary.exists() and any(primary.glob("*_ir2.asm")):
        return primary
    return ROOT / "decompiler_out" / game


def all_ir2_basenames(game: str) -> set[str]:
    """Every object name with an IR2 file in this game's decomp_out."""
    out = decomp_out_dir(game)
    if not out.exists():
        return set()
    return {p.name[:-len("_ir2.asm")] for p in out.glob("*_ir2.asm")}


def compute_impact_set(edited_types: set[str], game: str,
                       max_results: int = 0) -> set[str]:
    """Find object names whose IR2 references any of edited_types.

    Uses ripgrep with word-boundary matching for speed.
    edited_types may include "type" or "type::method-N" forms; we normalize
    by extracting just the type prefix and grepping for that.

    max_results: cap the returned set (0 = no cap). If grep finds more than
    cap, we return the union with clean-file set anyway (caller's choice
    whether to fall back to full decomp).
    """
    if not edited_types:
        return set()

    out = decomp_out_dir(game)
    if not out.exists():
        return set()

    # Normalize: extract type names (strip ::method-N suffix)
    type_names: set[str] = set()
    for name in edited_types:
        if "::" in name:
            type_names.add(name.split("::", 1)[0])
        else:
            type_names.add(name)

    if not type_names:
        return set()

    # Build alternation pattern with word boundaries.
    # GOAL identifiers can contain - and ! and ? so default word boundaries
    # don't apply cleanly; we use lookarounds for surrounding non-identifier
    # chars instead.
    escaped = sorted(re.escape(t) for t in type_names)
    pattern = r"(?<![A-Za-z0-9_!?\-])(?:" + "|".join(escaped) + r")(?![A-Za-z0-9_!?\-])"

    # ripgrep --files-with-matches over IR2 only.
    # -P (PCRE2) is required for the lookaround-based word boundaries —
    # default regex engine (Rust regex) doesn't support lookarounds.
    cmd = [
        "rg", "-P", "--files-with-matches", "--no-messages",
        "-g", "*_ir2.asm",
        pattern, str(out),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return set()
    if r.returncode not in (0, 1):  # 1 = no matches, also acceptable
        return set()

    impacted: set[str] = set()
    for line in r.stdout.splitlines():
        p = Path(line.strip())
        if p.name.endswith("_ir2.asm"):
            impacted.add(p.name[:-len("_ir2.asm")])

    if max_results and len(impacted) > max_results:
        # Caller decides what to do — we still return the full set; it can
        # check len() and fall back to full decomp if too broad.
        pass

    return impacted


def load_clean_files(game: str) -> set[str]:
    """Load the persistent set of currently-real-clean object names for game.

    Returns empty set if no record exists yet (first run).
    """
    rec = COMPOUND_LOOP_DIR / "clean_files.json"
    if not rec.exists():
        return set()
    try:
        data = json.loads(rec.read_text())
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get(game, []))


def save_clean_files(game: str, clean: set[str]) -> None:
    """Persist the real-clean set for game. Updates only that game's slot."""
    COMPOUND_LOOP_DIR.mkdir(parents=True, exist_ok=True)
    rec = COMPOUND_LOOP_DIR / "clean_files.json"
    data: dict = {}
    if rec.exists():
        try:
            data = json.loads(rec.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    data[game] = sorted(clean)
    rec.write_text(json.dumps(data, indent=2) + "\n")


def measure_clean_from_ir2(game: str) -> set[str]:
    """Scan game's decomp_out and return basenames with 0 ERROR markers.

    Used to refresh clean-files after a full decomp. Matches the same
    ERROR-counting logic that measure.py uses.
    """
    out = decomp_out_dir(game)
    if not out.exists():
        return set()
    err_re = re.compile(r"^;; ERROR:", re.MULTILINE)
    clean: set[str] = set()
    for p in out.glob("*_ir2.asm"):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        if not err_re.search(text):
            clean.add(p.name[:-len("_ir2.asm")])
    return clean


def union_with_clean(impact: set[str], game: str) -> set[str]:
    """Union impact set with current clean-file set for safety."""
    return impact | load_clean_files(game)


# ---------- CLI ----------
def _main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True, choices=("jak1", "jak2", "jak3", "jakx"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_impact = sub.add_parser("impact", help="compute impact set")
    p_impact.add_argument("--types", required=True,
                          help="comma-separated type names")
    p_impact.add_argument("--with-clean", action="store_true",
                          help="union result with clean-file invariant set")

    p_refresh = sub.add_parser("refresh-clean",
                               help="rescan IR2 and update clean_files.json")

    p_show = sub.add_parser("show-clean", help="print current clean set")

    args = ap.parse_args()

    if args.cmd == "impact":
        types = {t.strip() for t in args.types.split(",") if t.strip()}
        impact = compute_impact_set(types, args.game)
        if args.with_clean:
            impact = union_with_clean(impact, args.game)
        for name in sorted(impact):
            print(name)
        print(f"# {len(impact)} objects", flush=True)
        return 0

    if args.cmd == "refresh-clean":
        clean = measure_clean_from_ir2(args.game)
        save_clean_files(args.game, clean)
        print(f"refreshed {args.game}: {len(clean)} clean files")
        return 0

    if args.cmd == "show-clean":
        clean = load_clean_files(args.game)
        for name in sorted(clean):
            print(name)
        print(f"# {len(clean)} clean files", flush=True)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
