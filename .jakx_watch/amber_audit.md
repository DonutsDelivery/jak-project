# AMBER File Audit — 7 files from batch 1 offline-test sweep

_source: scripts/jakx_watch/offline_test_results.md_
_audited: 2026-04-24_

| File | Issue | Diff | Action | Effort |
|------|-------|------|--------|--------|
| `ambient-h` | method_return_type | `draw-text: none→int` | LOG_FOR_REVIEW | M |
| `joint-h` | method_return_type | `push-anim-to-targ: none→int` | LOG_FOR_REVIEW | M |
| `camera-h` | method_return_type | 3 methods: `debug-*: none→int` | LOG_FOR_REVIEW | M |
| `pov-camera-h` | method_return_type | 2 methods: `set-stack-size!, pov-camera-method-58: none→int` | LOG_FOR_REVIEW | M |
| `drawable-tree` | missing_decomp | (no decompiler output) | INVESTIGATE | S |
| `entity-h` | method_return_type | `debug-draw: none→int` | LOG_FOR_REVIEW | M |
| `lightning-new-h` | missing_decomp | (no decompiler output) | INVESTIGATE | S |

## Pattern Analysis

**Method Return-Type Mismatches (5/7 files)**

All AMBER files with decompiler output show the same issue: **methods returning `int` in decompiled bytecode but declared as `none` in reference files.**

### Issues by File

- `ambient-h`: 1 method (draw-text)
- `joint-h`: 1 method (push-anim-to-targ)
- `camera-h`: 3 methods (debug-point-info, debug-all-points, debug-draw-spline)
- `pov-camera-h`: 2 methods (set-stack-size!, pov-camera-method-58)
- `entity-h`: 1 method (debug-draw)

**Total: 8 method return-type corrections needed**

### Root Cause Candidates

1. **Hand-written reference files are incorrect** — decompiler bytecode is correct; need to update all-types.gc refs
2. **type_casts entries needed** — decompiler is misreading return values; need cast hints in `type_casts.jsonc`
3. **Actual decompiler bug** — decompiler emitting wrong return type

### CRITICAL: DO NOT FIX BLIND

⚠️ See gotchas.md entry #8 — last blind batch return-type corrections cost +7071 errors. Each method needs:
1. Read the actual defun body in decompiler output
2. Check what it returns
3. Decide: update reference file OR add type_casts entry
4. Review before batch-applying

### Missing Files (2/7)

- `drawable-tree`: decompiler output not found (may not have been decompiled yet)
- `lightning-new-h`: decompiler output not found (may not have been decompiled yet)
