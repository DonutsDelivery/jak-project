#!/usr/bin/env python3
"""
Offline-test sweep on migration candidates.

Batch-test "real-clean" migration candidates against offline-test to classify:
- GREEN: passes offline-test (bytecode matches reference)
- AMBER: decompiles but bytecode differs (diff reported)
- RED: offline-test fails (exit != 0, not a "no reference" case)
- SKIPPED: no reference file exists

Usage:
  python3 scripts/jakx_watch/offline_test_sweep.py [--batch-size N] [--limit N] [--candidates-file PATH]

Outputs results to .jakx_watch/offline_test_results.md
"""

import subprocess
import re
import sys
from pathlib import Path
from datetime import datetime

def run_offline_test(filename, offline_test_bin, iso_path):
    """Run offline-test on a single file. Returns (result, output, returncode)."""
    try:
        result = subprocess.run(
            [
                str(offline_test_bin),
                "--iso_data_path", str(iso_path),
                "--game", "jakx",
                "--file", filename,
                "--fail-on-cmp",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    except Exception as e:
        return -2, f"ERROR: {str(e)}"

def classify_result(returncode, output):
    """Classify offline-test result."""
    if returncode == 0:
        return "GREEN"
    elif "no reference" in output.lower():
        return "SKIPPED"
    else:
        return "AMBER"

def extract_diff_summary(output):
    """Extract a brief diff summary from AMBER output."""
    # Look for the unified diff section
    m = re.search(r'@@ .+? @@\n(.+?)(?:\n\[|\nCompiled|$)', output, re.DOTALL)
    if m:
        diff_text = m.group(1).strip()
        lines = diff_text.split('\n')[:3]  # First 3 lines of diff
        return " ".join(lines)
    return ""

def parse_candidates_file(candidates_path):
    """Parse migration_candidates.md to extract file list."""
    text = candidates_path.read_text()
    candidates = []

    # Look for rows in the "all candidates" section
    lines = text.split('\n')
    in_all_section = False

    for line in lines:
        if "## all candidates" in line:
            in_all_section = True
            continue

        if not in_all_section:
            continue

        # Match table rows: | # | score | cat | OT | name | ...
        if line.startswith('|') and 'untested' in line:
            # Extract the filename (in backticks)
            m = re.search(r'`([^`]+)`', line)
            if m:
                candidates.append(m.group(1))

    return candidates

def main():
    # Parse arguments
    batch_size = 15
    limit = None
    candidates_file = Path(".jakx_watch/migration_candidates.md")

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--batch-size" and i + 2 < len(sys.argv):
            batch_size = int(sys.argv[i + 2])
        elif arg == "--limit" and i + 2 < len(sys.argv):
            limit = int(sys.argv[i + 2])
        elif arg == "--candidates-file" and i + 2 < len(sys.argv):
            candidates_file = Path(sys.argv[i + 2])

    # Setup paths
    offline_test_bin = Path("build/Release/bin/offline-test")
    iso_path = Path("iso_data/jakx")

    if not offline_test_bin.exists():
        print(f"Error: offline-test binary not found at {offline_test_bin}")
        print("Build it with: cmake --build build/Release --target offline-test -j")
        sys.exit(1)

    if not candidates_file.exists():
        print(f"Error: candidates file not found at {candidates_file}")
        sys.exit(1)

    # Parse candidates
    candidates = parse_candidates_file(candidates_file)
    if limit:
        candidates = candidates[:limit]
    else:
        candidates = candidates[:batch_size]

    print(f"Testing {len(candidates)} candidates...")

    # Run tests
    results = {"green": [], "amber": [], "red": [], "skipped": []}
    details = {}

    for i, filename in enumerate(candidates, 1):
        print(f"  [{i:2d}/{len(candidates)}] {filename}...", end=" ", flush=True)

        returncode, output = run_offline_test(filename, offline_test_bin, iso_path)
        classification = classify_result(returncode, output)

        results[classification.lower()].append(filename)

        diff = extract_diff_summary(output) if classification == "AMBER" else ""
        details[filename] = {"result": classification, "diff": diff, "returncode": returncode}

        print(classification)

    # Generate output markdown
    output_lines = [
        "# offline-test sweep results",
        "",
        f"_generated: {datetime.now().isoformat()}_",
        f"_tested: {len(candidates)} files_",
        "",
        "## summary",
        "",
        f"- **GREEN** (passes offline-test): {len(results['green'])}",
        f"- **AMBER** (bytecode diff): {len(results['amber'])}",
        f"- **RED** (offline-test fails): {len(results['red'])}",
        f"- **SKIPPED** (no reference): {len(results['skipped'])}",
        "",
        "## results by status",
        "",
    ]

    # GREEN files
    if results['green']:
        output_lines.append("### GREEN ✓")
        output_lines.append("")
        for name in results['green']:
            output_lines.append(f"- `{name}`")
        output_lines.append("")

    # AMBER files
    if results['amber']:
        output_lines.append("### AMBER ~")
        output_lines.append("")
        for name in results['amber']:
            diff = details[name]['diff']
            if diff:
                output_lines.append(f"- `{name}` — {diff[:80]}")
            else:
                output_lines.append(f"- `{name}`")
        output_lines.append("")

    # RED files
    if results['red']:
        output_lines.append("### RED ✗")
        output_lines.append("")
        for name in results['red']:
            output_lines.append(f"- `{name}` (rc={details[name]['returncode']})")
        output_lines.append("")

    # SKIPPED files
    if results['skipped']:
        output_lines.append("### SKIPPED (no reference)")
        output_lines.append("")
        for name in results['skipped']:
            output_lines.append(f"- `{name}`")
        output_lines.append("")

    # Write results
    output_path = Path(".jakx_watch/offline_test_results.md")
    output_path.write_text('\n'.join(output_lines))

    print(f"\nWrote results to {output_path}")
    print(f"Summary: {len(results['green'])} GREEN, {len(results['amber'])} AMBER, {len(results['red'])} RED, {len(results['skipped'])} SKIPPED")

if __name__ == "__main__":
    main()
