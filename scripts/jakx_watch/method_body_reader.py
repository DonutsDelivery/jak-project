#!/usr/bin/env python3
"""Read actual return types from decomp output for (type, method) lookups.

Priority-4 helper — feeds into return_mismatch_apply.py's plan_fixes() to
validate child-type body return types before applying parent/child return-type
fixes. Unlocks entries currently skipped by the strict child-consistency check.

Usage (standalone):
    python3 scripts/jakx_watch/method_body_reader.py [--decomp-out DIR]

Usage (library):
    from method_body_reader import MethodBodyReader
    reader = MethodBodyReader(decomp_dir)
    actual = reader.actual_return("vehicle", 15)  # None if not found
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from return_mismatch_scan import scan_file, pick_decomp_dir  # noqa: E402


class MethodBodyReader:
    """Caches (type, method_idx) → actual_return_type from decomp WARNs."""

    def __init__(self, decomp_dir: Path) -> None:
        self._map: dict[tuple[str, int], str] = {}
        raw: dict[tuple[str, int], list[str]] = collections.defaultdict(list)

        for fp in sorted(decomp_dir.glob("*_disasm.gc")):
            for _caller, parent, _declared, actual, mnum in scan_file(fp):
                if parent and mnum is not None:
                    raw[(parent, mnum)].append(actual)

        # When multiple WARNs exist for the same method, take the most common.
        for key, actuals in raw.items():
            self._map[key] = collections.Counter(actuals).most_common(1)[0][0]

    def actual_return(self, type_name: str, method_idx: int) -> str | None:
        """Return the actual (body) return type, or None if unknown."""
        return self._map.get((type_name, method_idx))

    def __len__(self) -> int:
        return len(self._map)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decomp-out", help="Override decomp output directory")
    ap.add_argument(
        "--type", dest="type_name", help="Filter to a specific type name"
    )
    args = ap.parse_args()

    decomp_dir = Path(args.decomp_out).resolve() if args.decomp_out else pick_decomp_dir()
    if not decomp_dir.exists():
        print(f"ERROR: decomp dir not found: {decomp_dir}", file=sys.stderr)
        return 1

    reader = MethodBodyReader(decomp_dir)
    print(f"Loaded {len(reader)} (type, method) → actual-return entries from {decomp_dir}")

    if args.type_name:
        matches = {
            (tp, mnum): actual
            for (tp, mnum), actual in reader._map.items()
            if tp == args.type_name
        }
        if not matches:
            print(f"No entries for type '{args.type_name}'")
        for (tp, mnum), actual in sorted(matches.items(), key=lambda x: x[0][1]):
            print(f"  {tp}::method-{mnum} → {actual}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
