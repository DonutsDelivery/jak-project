#!/usr/bin/env python3
"""
Migrate 53 offline-test GREEN files from hand-ports to decomp-based versions.

For each GREEN file, runs update-from-decomp.py to replace the hand-port with
the decompiled version while preserving comments and decomp deviations.

Outputs migration log to .jakx_watch/migration_log.txt
"""

import subprocess
import sys
from pathlib import Path

GREEN_FILES = [
    "mspace-h",
    "cam-debug-h",
    "cam-interface",
    "cam-start",
    "camera-defs-h",
    "collide-frag-h",
    "collide-frag",
    "find-nearest-h",
    "cloth-art-h",
    "curves",
    "water-info-h",
    "art-h",
    "debug-sphere",
    "memory-usage-h",
    "dma-bucket",
    "draw-node-h",
    "drawable-actor-h",
    "drawable-group-h",
    "drawable-group",
    "drawable-h",
    "drawable-inline-array-h",
    "drawable-inline-array",
    "connect",
    "engines",
    "sparticle-subsampler",
    "entity-table",
    "res-h",
    "effect-control-h",
    "game-info-h",
    "jakx-init",
    "main-h",
    "penetrate-h",
    "settings-h",
    "game-task-h",
    "bounding-box-h",
    "geometry-h",
    "background-h",
    "prototype-h",
    "tfrag-h",
    "tie-h",
    "wind-h",
    "bones-h",
    "lights-h",
    "generic-merc-h",
    "merc-death",
    "merc-h",
    "generic-h",
    "generic-vu1-h",
    "generic-work-h",
    "display-h",
    "gs",
    "video-h",
    "math-camera-h",
]

def migrate_file(filename):
    """Run update-from-decomp.py for a single file. Returns (success, output)."""
    result = subprocess.run(
        ["python3", "scripts/gsrc/update-from-decomp.py", "--game", "jakx", "--file", filename],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0, result.stdout + result.stderr

def main():
    log_path = Path(".jakx_watch/migration_log.txt")
    skipped_path = Path(".jakx_watch/migration_skipped.md")

    migrated = []
    skipped = []
    log_lines = []

    print(f"Migrating {len(GREEN_FILES)} GREEN files...")

    for i, filename in enumerate(GREEN_FILES, 1):
        print(f"  [{i:2d}/{len(GREEN_FILES)}] {filename}...", end=" ", flush=True)

        try:
            success, output = migrate_file(filename)

            if success:
                print("OK")
                migrated.append(filename)
                log_lines.append(f"✓ {filename}")
            else:
                print("SKIP (error)")
                skipped.append((filename, "update-from-decomp failed"))
                log_lines.append(f"✗ {filename} — error in update-from-decomp")
                if "No such file" in output or "not found" in output:
                    log_lines.append(f"  (hand-port file not found)")

        except subprocess.TimeoutExpired:
            print("SKIP (timeout)")
            skipped.append((filename, "timeout"))
            log_lines.append(f"✗ {filename} — timeout")
        except Exception as e:
            print(f"SKIP ({str(e)[:20]})")
            skipped.append((filename, str(e)[:50]))
            log_lines.append(f"✗ {filename} — {str(e)[:50]}")

    # Write log
    log_path.write_text('\n'.join(log_lines))

    # Write skipped list
    if skipped:
        skipped_md = ["# Migration Skipped Files", ""]
        for filename, reason in skipped:
            skipped_md.append(f"- `{filename}` — {reason}")
        skipped_path.write_text('\n'.join(skipped_md))

    print(f"\nMigration complete:")
    print(f"  Migrated: {len(migrated)}/{ len(GREEN_FILES)}")
    print(f"  Skipped: {len(skipped)}")

    return len(skipped) == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
