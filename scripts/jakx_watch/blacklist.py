#!/usr/bin/env python3
"""blacklist.py — persistent record of (game, type, method, pattern) tuples
that have been reverted by apply_guard.

Each tool's planner consults the blacklist before proposing a fix and skips
matched candidates. This prevents the loop from re-trying the same losing
patches every iteration — without it, a "bad apple" candidate would consume
a full apply_guard validation cycle each iteration only to get reverted again.

Storage: .compound_loop/blacklist.json
Schema:
{
  "jak2": [
    {
      "key": "process::method-9::none:int",
      "type": "process",
      "method": "method-9",
      "pattern": "none:int",
      "reason": "rc dropped 515→512",
      "iterations": 3,
      "first_seen": "2026-04-26T06:00:00",
      "last_seen": "2026-04-26T06:30:00"
    },
    ...
  ],
  ...
}

API:
  is_blacklisted(game, type_name, method, pattern) -> bool
  add(game, type_name, method, pattern, reason) -> None  # idempotent: bumps counter
  load(game) -> dict[key, entry]
  size(game) -> int
  show(game) -> str  # human-readable
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLACKLIST_DIR = ROOT / ".compound_loop"
BLACKLIST_FILE = BLACKLIST_DIR / "blacklist.json"


def _make_key(type_name: str, method: str, pattern: str) -> str:
    """Composite key for blacklist lookup. method may be 'method-N' or 'extern'."""
    return f"{type_name}::{method}::{pattern}"


def _load_all() -> dict:
    """Load entire blacklist (all games). Returns empty dict on missing/invalid."""
    if not BLACKLIST_FILE.exists():
        return {}
    try:
        return json.loads(BLACKLIST_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict) -> None:
    BLACKLIST_DIR.mkdir(parents=True, exist_ok=True)
    # Atomic write: tmp → rename. Avoids torn writes if two processes race.
    tmp = BLACKLIST_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(BLACKLIST_FILE)


def load(game: str) -> dict[str, dict]:
    """Return {key: entry} for the given game."""
    all_data = _load_all()
    entries = all_data.get(game, [])
    return {e["key"]: e for e in entries if "key" in e}


def is_blacklisted(game: str, type_name: str, method: str, pattern: str) -> bool:
    """Check if (game, type, method, pattern) is on the blacklist."""
    return _make_key(type_name, method, pattern) in load(game)


def add(game: str, type_name: str, method: str, pattern: str,
        reason: str = "") -> None:
    """Add or bump a blacklist entry. Idempotent: existing entries get
    iterations+=1 and last_seen updated.
    """
    key = _make_key(type_name, method, pattern)
    now = datetime.now().isoformat(timespec="seconds")
    all_data = _load_all()
    entries = all_data.setdefault(game, [])
    for e in entries:
        if e.get("key") == key:
            e["iterations"] = e.get("iterations", 1) + 1
            e["last_seen"] = now
            if reason:
                e["reason"] = reason  # latest reason wins
            _save_all(all_data)
            return
    entries.append({
        "key": key,
        "type": type_name,
        "method": method,
        "pattern": pattern,
        "reason": reason,
        "iterations": 1,
        "first_seen": now,
        "last_seen": now,
    })
    _save_all(all_data)


def remove(game: str, type_name: str, method: str, pattern: str) -> bool:
    """Remove an entry. Returns True if found and removed.
    Use this to retry a previously-blacklisted candidate after the surrounding
    code has changed enough that the prior failure may no longer apply.
    """
    key = _make_key(type_name, method, pattern)
    all_data = _load_all()
    entries = all_data.get(game, [])
    new_entries = [e for e in entries if e.get("key") != key]
    if len(new_entries) == len(entries):
        return False
    all_data[game] = new_entries
    _save_all(all_data)
    return True


def size(game: str) -> int:
    return len(load(game))


def show(game: str | None = None) -> str:
    """Return a human-readable summary."""
    all_data = _load_all()
    games = [game] if game else sorted(all_data.keys())
    out = []
    for g in games:
        entries = all_data.get(g, [])
        out.append(f"\n=== {g} ({len(entries)} entries) ===")
        # Sort by iterations desc (most-revived bad apples first)
        for e in sorted(entries, key=lambda x: -x.get("iterations", 0))[:50]:
            out.append(
                f"  {e.get('type','')}::{e.get('method','')}  "
                f"{e.get('pattern','')}  ×{e.get('iterations','?')}  "
                f"({e.get('reason','')})"
            )
        if len(entries) > 50:
            out.append(f"  … {len(entries) - 50} more")
    return "\n".join(out)


# ---------- CLI ----------
def _main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="print blacklist contents")
    p_show.add_argument("--game", default=None,
                        help="restrict to one game (default: all)")

    p_check = sub.add_parser("check", help="test if entry is blacklisted")
    p_check.add_argument("--game", required=True)
    p_check.add_argument("--type", required=True)
    p_check.add_argument("--method", required=True)
    p_check.add_argument("--pattern", required=True)

    p_add = sub.add_parser("add", help="manually add an entry")
    p_add.add_argument("--game", required=True)
    p_add.add_argument("--type", required=True)
    p_add.add_argument("--method", required=True)
    p_add.add_argument("--pattern", required=True)
    p_add.add_argument("--reason", default="manual")

    p_rm = sub.add_parser("remove", help="remove an entry (allow retry)")
    p_rm.add_argument("--game", required=True)
    p_rm.add_argument("--type", required=True)
    p_rm.add_argument("--method", required=True)
    p_rm.add_argument("--pattern", required=True)

    args = ap.parse_args()

    if args.cmd == "show":
        print(show(args.game))
        return 0

    if args.cmd == "check":
        hit = is_blacklisted(args.game, args.type, args.method, args.pattern)
        print(f"{'BLACKLISTED' if hit else 'OK'}: {args.game} "
              f"{args.type}::{args.method} {args.pattern}")
        return 0 if not hit else 2

    if args.cmd == "add":
        add(args.game, args.type, args.method, args.pattern, args.reason)
        print(f"added: {args.game} {args.type}::{args.method} {args.pattern}")
        return 0

    if args.cmd == "remove":
        ok = remove(args.game, args.type, args.method, args.pattern)
        print("removed" if ok else "not found")
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
