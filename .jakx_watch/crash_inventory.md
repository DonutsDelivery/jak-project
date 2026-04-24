# Jakx Decomp Crash Inventory — 364 Blocked Files

_source: scripts/jakx_watch/run.sh JAKX_WATCH_FORCE=1 · analyzed: 2026-04-24T08:06:50_

## Executive Summary

**Decompiler blocked**: 364 files (49% of 713 total)
**Fatal crash**: Label type conflict during `debug` file label parsing (mips2c phase)
**Processed before crash**: 349/713 files; generated output: 395 .gc files

### Error Distribution (Processed Files)
| Category | Count | % of Total | Root Cause |
|----------|-------|-----------|-----------|
| **type_prop failures** | 848 | 53% | Missing type_casts.jsonc hints for struct loads |
| **warnings (unknown types)** | 630 | 40% | Unresolved function signatures in anon-functions |
| **static_ref decompile failures** | ~200 | 13% | Label type conflicts + missing label_types |
| **method_not_found** | ~40 | 3% | Type method counts mismatch (process = 14, not 9) |
| **type_add failures** | 106 | 7% | Uninitialized struct + integer arithmetic |

## Fatal Crash Analysis

### Root Cause: Label Type Conflict

```
Error parsing labels for debug: Conflicting types for label L283: 
  (inline-array vector) and string
```

**Location**: `debug` file, label L283
**Phase**: Mips2c processing (during sparticle-motion-blur-dirt parsing)
**Hypothesis**: 
- Label L283 has two conflicting type annotations in `label_types.jsonc`
- OR L283 is a static data region with dual interpretations (array vs scalar)
- Blocking effect: Entire label parsing phase fails → 364 files never attempted

**Fix**: Add single authoritative label_types entry for L283 in debug file; verify no duplicate/conflicting entries

---

## Bucket 1: LABEL_TYPES Conflicts (Fatal)

**Count**: 364 blocked files + debug file with explicit L283 conflict
**Impact**: Blocks all downstream file processing once label parse fails
**Hypothesis**: 
- Bulk label_types copy-port (sessions 14-16) introduced duplicate/conflicting entries
- L283 has two type hints that don't unify (array type vs scalar type)
- Decompiler's label type resolver finds conflict, crashes

**Resolution Path**:
1. Search `decompiler/config/jakx/ntsc_v1/label_types.jsonc` for all occurrences of `L283`
2. Merge or remove duplicates; keep only the authoritative one
3. Re-run `bash scripts/jakx_watch/run.sh` → should unblock all 364 files

---

## Bucket 2: TYPE_PROP Failures (848 errors)

Occurs in processed files; these continue running even with errors.

**Top 5 Representative Files**:
1. `default-base-menu-post` — "Could not figure out load: (set! v1 (l.wu (+ s6 248)))" → missing struct offset cast
2. `(method 58 base-menu)` — "Could not figure out load: (set! f0 (l.f (+ gp 284)))" → base-menu layout unknown
3. `base-menu-init-by-other` — "Could not figure out load: (set! f0 (l.f a1))" → parameter type ambiguous
4. `(method 63 base-menu)` — "Could not figure out load: (set! v1 (l.wu (+ gp 248)))" → struct offset ditto
5. `(method 64 base-menu)` — "Could not figure out load: (set! v1 (l.wu (+ gp 76)))" → struct offset ditto

**Pattern**: Struct load with unknown base type or missing field offset
**Hypothesis**: base-menu, basic, and menu-system types have layout mismatches vs jak3. Fields at +76, +248, +284 are undeclared or mis-typed.

**Resolution Path**:
1. Extract MIPS register type for each load (e.g., is gp a base-menu? process? object?)
2. Add type_casts.jsonc entries: `"(set! REG (l.wu (+ gp 248)))" → (the-as base-menu gp)`
3. Iterate until no more failures
4. Expected Δerr: -700+ (848 errors with cascading fixes)

---

## Bucket 3: STATIC_REF Decompile Failures (~200 errors)

**Top 3 Representative Entries**:
1. `(top-level-login menu2-part)` — "Unable to 'decompile_at_label' L33 (using type sparticle-launch-group), Reason: In structure ... unknown data"
2. `(top-level-login intro-part)` — "Unable to 'decompile_at_label' L950 (using type sparticle-launch-group), Reason: In structure ... unknown data"
3. `(top-level-login sprite-glow)` — "Unable to decompile_at_label L25 (using type simple-sprite-system), Reason: In structure ... unknown data"

**Pattern**: Label decompilation fails because nested struct has UNKNOWN fields
**Hypothesis**: 
- sparticle-launch-group, simple-sprite-system have uncommented or UNKNOWN fields
- Decompiler tries to walk the struct and hits unknown type → bails
- Blocked files: All that call these top-level-logins (menu2, intro-scenes, sprite families)

**Resolution Path**:
1. Activate sparticle-launch-group and simple-sprite-system in all-types.gc (add UNKNOWN → real type guesses)
2. OR add label_types hint for the specific label (e.g., L33 → (array sparticle-launcher))
3. Expected Δerr: -200+ 

---

## Bucket 4: TYPE_ADD Failures (106 errors)

Uninitialized struct initialization with integer offsets.

**Top 5 Representative Entries**:
1. `(method 13 camera-facing-quad)` — "add failed: <uninitialized> <integer 12>" → camera-facing-quad size unknown
2. `decode-net-anim-state` — "add failed: <uninitialized> <integer 16>" → net-anim-state not sized
3. `get-anim-offset` — "add failed: <value x 16> <uninitialized>" → multiply-then-alloc pattern
4. `(method 49 net-powerup)` — "add failed: <uninitialized> <integer 220>" → net-powerup offset calc
5. `(method 50 net-powerup)` — "add failed: <uninitialized> <integer 28>" → net-powerup ditto

**Pattern**: New struct instantiation or offset computation; decompiler can't infer size
**Hypothesis**: 
- camera-facing-quad, net-anim-state, net-powerup are comment-blocked or have wrong size
- Methods allocate new instances w/o knowing final size
- OR locals are untyped (should be `(local ...)` with type hint)

**Resolution Path**:
1. Activate camera-facing-quad and other net-* types
2. Run offline-test to seed correct sizes
3. Expected Δerr: -100+ once sizes are known

---

## Bucket 5: Unknown Function Types (630 warnings)

**Pattern**: "Function (anon-function N <file>) didn't know its type"
**Hypothesis**: 
- Lambdas and local closures in top-level-logins (menu2, base-menu, etc.) lack explicit type hints
- Decompiler emits `;;! WARN: unknown function type` but continues
- Not blocking; functions are emitted as `(lambda () ...)` but type-check fails

**Resolution Path**:
- Add lambda type hints in all-types.gc or hacks.jsonc for anon functions in menu2-COMMON-GAME, etc.
- Low priority; warnings don't block decompilation

---

## Bucket 6: Method Not Found (40 errors)

**Pattern**: "The method with id N of type X could not be found"
**Examples**: 
- "(method 55 of type process)" — process has 14 methods, not 9 (session 16 lesson)
- "(method 65 of type basic)" — basic method count mismatch

**Hypothesis**: Process and other base types' method tables are declared with wrong counts in all-types.gc. Auto-regen assumes old jak3 counts.

**Resolution Path**:
- Recount process method table (should be 14: 0-13)
- Recount basic method table (should be 60+)
- Update all-types.gc method-count-assert statements
- Expected Δerr: -40+

---

## Recommendations (Ordered by Unblock Impact)

1. **IMMEDIATE**: Fix label_types L283 conflict in `debug` file → unblocks 364 files in next run
2. **THEN**: Drain type_prop failures (bucket 2) → -700+ error reduction via type_casts.jsonc sweep
3. **PARALLEL**: Activate sparticle-launch-group, simple-sprite-system → fixes static_ref decompile failures (-200+)
4. **THEN**: type_add failures (bucket 4) by activating camera-facing-quad, net-* types
5. **FINAL**: Method count assertions (bucket 6) for process / basic

**Estimated Total Unblock**: 364 + 700 + 200 + 100 + 40 = ~1400 error reduction after all buckets drained.

---

## Next Session Trigger

Once label_types L283 is fixed, re-run:
```bash
JAKX_WATCH_FORCE=1 bash scripts/jakx_watch/run.sh
```

Expect:
- decomp progress: 713/713 processed (0 blocked)
- real-clean: 100+ (current)
- real-partial: 145+ (may increase slightly as blocked files decomp w/ errors)

Then dispatch type_casts and activation buckets per winner_patterns.md guidance.
