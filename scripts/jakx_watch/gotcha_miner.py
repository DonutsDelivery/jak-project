#!/usr/bin/env python3
"""
Mine git history for recurring bug patterns and generate gotcha candidates.

Analyzes the last 200 commits for:
- Reverts (bugs that required undo)
- Runtime errors (rc=134, rc=137, OOM)
- Type system bugs (type_casts, all-types, clobber, method mismatches)
- Layout bugs (size-assert, offset-assert)
- Decomp bugs (block comments, stub markers)

Outputs candidates to .jakx_watch/gotchas_candidates.md.
"""

import subprocess
import re
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def run_git(cmd):
    """Run git command and return stdout."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: git command failed: {cmd}")
        print(result.stderr)
        return ""
    return result.stdout.strip()

def get_recent_commits(count=200):
    """Get the last N commits as (sha, oneline) tuples."""
    output = run_git(f"git log --oneline -n {count} --all")
    commits = []
    for line in output.split('\n'):
        if not line.strip():
            continue
        parts = line.split(' ', 1)
        if len(parts) == 2:
            commits.append((parts[0], parts[1]))
    return commits

def get_commit_message(sha):
    """Get full commit message."""
    return run_git(f"git log --format=%B -n 1 {sha}")

def get_commit_files(sha):
    """Get list of changed files."""
    output = run_git(f"git show --stat {sha}")
    return output

def classify_commit(sha, oneline, full_message, changed_files):
    """Classify commit by pattern keywords."""
    patterns = defaultdict(list)

    text = (oneline + " " + full_message).lower()
    files = changed_files.lower()

    # Reverts
    if 'revert' in text or 'undo' in text:
        patterns['revert'].append(sha)

    # Runtime errors
    if 'rc=134' in text or 'rc=134' in oneline:
        patterns['rc_134'].append(sha)
    if 'rc=137' in text or 'rc=137' in oneline:
        patterns['rc_137'].append(sha)
    if 'oom' in text:
        patterns['oom'].append(sha)

    # Type system bugs
    if 'type_casts' in files or 'type_casts' in text:
        patterns['type_casts_fix'].append(sha)
    if 'all-types' in files or 'all-types.gc' in text:
        patterns['all_types_fix'].append(sha)
    if 'clobber' in text:
        patterns['clobber'].append(sha)
    if 'define-extern' in text:
        patterns['define_extern'].append(sha)

    # Method declaration bugs
    if ':methods' in text or 'method-count' in text or 'method-count-assert' in text:
        patterns['method_declaration'].append(sha)
    if 'return' in text and 'mismatch' in text:
        patterns['return_mismatch'].append(sha)

    # Layout bugs
    if 'size-assert' in text or 'size_assert' in text:
        patterns['size_assert'].append(sha)
    if 'offset-assert' in text or 'offset_assert' in text:
        patterns['offset_assert'].append(sha)

    # Decomp bugs
    if '#|' in text or 'block comment' in text or 'commented' in text and 'deftype' in text:
        patterns['block_comment_deftype'].append(sha)
    if 'stub' in text and 'marker' in text:
        patterns['stub_marker'].append(sha)

    # Field/type bugs
    if 'unknown' in text and 'field' in text:
        patterns['unknown_field'].append(sha)
    if 'field drift' in text or 'field-drift' in text:
        patterns['field_drift'].append(sha)

    # Inline struct / alignment
    if 'inline' in text and 'align' in text:
        patterns['inline_alignment'].append(sha)
    if 'inline' in text and ('struct' in text or 'field' in text):
        patterns['inline_struct'].append(sha)

    # Process offset
    if 'process-drawable' in text and 'offset' in text:
        patterns['process_drawable_offset'].append(sha)

    return patterns

def find_revert_pairs(commits_with_patterns):
    """Find revert-original commit pairs."""
    revert_pairs = []
    reverted_shas = set()

    for sha, oneline, full_msg, patterns in commits_with_patterns:
        if 'revert' in patterns:
            reverted_shas.add(sha)
            # Try to find what was reverted
            # Look for "revert" in message to find the original commit reference
            match = re.search(r'([a-f0-9]{7,})', full_msg)
            if match:
                original_sha = match.group(1)
                revert_pairs.append((original_sha, sha, oneline))

    return revert_pairs

def main():
    print("Mining last 200 commits for bug patterns...")

    commits = get_recent_commits(200)
    print(f"Found {len(commits)} commits")

    pattern_frequency = defaultdict(list)
    commits_with_patterns = []

    for sha, oneline in commits:
        full_message = get_commit_message(sha)
        changed_files = get_commit_files(sha)

        patterns = classify_commit(sha, oneline, full_message, changed_files)

        # Accumulate pattern frequencies
        for pattern_type, shas in patterns.items():
            pattern_frequency[pattern_type].extend(shas)

        commits_with_patterns.append((sha, oneline, full_message, patterns))

    # Find patterns with ≥3 occurrences
    candidate_patterns = {
        pattern: shas
        for pattern, shas in pattern_frequency.items()
        if len(shas) >= 3
    }

    print(f"\nFound {len(candidate_patterns)} candidate patterns (≥3 occurrences)")
    for pattern, shas in sorted(candidate_patterns.items(), key=lambda x: -len(x[1])):
        print(f"  {pattern}: {len(shas)} occurrences")

    # Generate candidates document
    output_lines = [
        "# gotchas candidates — human review needed",
        "",
        f"_source: scripts/jakx_watch/gotcha_miner.py · generated: {datetime.now().isoformat()}_",
        f"_scope: last 200 commits · new candidates: {len(candidate_patterns)}_",
        "",
        "Each candidate is a pattern that appeared ≥3 times in git history. Review, promote into gotchas.md if valid, close if not.",
        "",
    ]

    # Define pattern-to-friendly-name mapping
    pattern_names = {
        'revert': 'Reverted Commits (Bugs)',
        'rc_134': 'RC=134 Errors',
        'rc_137': 'RC=137 Errors',
        'oom': 'Out-of-Memory Errors',
        'type_casts_fix': 'Type Casts Fixes',
        'all_types_fix': 'All-Types Fixes',
        'clobber': 'Clobber Pattern Issues',
        'define_extern': 'Define-Extern Issues',
        'method_declaration': 'Method Declaration Bugs',
        'return_mismatch': 'Return Type Mismatches',
        'size_assert': 'Size-Assert Violations',
        'offset_assert': 'Offset-Assert Violations',
        'block_comment_deftype': 'Block-Commented Deftype Issues',
        'stub_marker': 'Stub Marker Problems',
        'unknown_field': 'Unknown Field Type Bugs',
        'field_drift': 'Field Drift Issues',
        'inline_alignment': 'Inline Struct Alignment Bugs',
        'inline_struct': 'Inline Struct Issues',
        'process_drawable_offset': 'Process-Drawable Offset Shifts',
    }

    candidate_num = 0
    for pattern, shas in sorted(candidate_patterns.items(), key=lambda x: -len(x[1])):
        candidate_num += 1
        pattern_name = pattern_names.get(pattern, pattern.replace('_', ' ').title())

        output_lines.append(f"## Candidate {candidate_num}: {pattern_name}")
        output_lines.append("")
        output_lines.append(f"**Pattern:** `{pattern}`")
        output_lines.append(f"**Frequency:** {len(shas)} commits in last 200")
        output_lines.append("")
        output_lines.append("**Representative commits:**")

        # Show up to 5 most recent
        for sha in shas[:5]:
            for c_sha, c_oneline, _, _ in commits_with_patterns:
                if c_sha == sha:
                    output_lines.append(f"  - `{sha}` {c_oneline}")
                    break

        if len(shas) > 5:
            output_lines.append(f"  - ... and {len(shas) - 5} more")

        output_lines.append("")
        output_lines.append("**Suggested detection:** <analyze representative commits and propose check>")
        output_lines.append("")

    # Write candidates document
    candidates_path = Path(".jakx_watch/gotchas_candidates.md")
    candidates_path.parent.mkdir(parents=True, exist_ok=True)

    with open(candidates_path, 'w') as f:
        f.write('\n'.join(output_lines))

    print(f"\nWrote {candidates_path}")
    print(f"Generated {candidate_num} candidate patterns for review")

if __name__ == "__main__":
    main()
