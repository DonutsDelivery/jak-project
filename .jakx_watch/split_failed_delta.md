# +9 split-failed regression investigation

_Investigation date: 2026-04-24_  
_Baseline: 2026-04-18T051352 (split-failed=0)_  
_Regression point: 2026-04-24T003201 (split-failed=60)_  
_Current: 2026-04-24T070649 (split-failed=2)_

## Executive Summary

The "+9 split-failed regression" is **not a code regression, but a decomp scope expansion**. Between April 18 and April 24 00:32, the decompiler output grew from 363 files to 423 files. Nine newly-decomposed files arrived with decomp errors that classified them as split-failed. At 00:40, commit a4034cfd1 refined the split-failed classification logic, reclassifying 51 files from split-failed → static-only, leaving 9.

**No revert needed.** The 9 files are real split-failed (have error markers); they're not false positives. The decomp output is intentionally broader now.

## The 9 split-failed Files

| file | err | stubs | failed | defun | defmethod | Notes |
|------|-----|-------|--------|-------|-----------|-------|
| cam-combiner | 2 | 0 | 0 | 0 | 0 | Split store failure |
| history | 1 | 0 | 0 | 0 | 0 | "function was not converted to expressions" |
| lobby-menu-manager-h | 1 | 0 | 0 | 0 | 0 | (header file, single error) |
| pad | 1 | 0 | 0 | 0 | 0 | Top-level error marker |
| prototype | 1 | 0 | 0 | 0 | 0 | Type-related error |
| sampler | 6 | 0 | 0 | 0 | 0 | Multiple split store failures |
| target-pilot | 1 | 0 | 0 | 0 | 0 | Single error marker |
| wcar-skel-template | 1 | 0 | 0 | 0 | 0 | Template file error |
| wvehicle-weapons-h | 1 | 0 | 0 | 0 | 0 | (header file, single error) |

## Timeline & Root Cause Analysis

### Phase 1: Decomp Scope Expansion (April 18 → April 24 00:32)

**Commits:** 324 commits between ed5385684 (April 18 06:44) and the 00:32 snapshot  
**Result:** Decompiler output grew from ~363 files to 423+ files  
**New files:** The 9 split-failed files did NOT exist in decomp output on April 18. They are newly decomposed content.

**Key observation:** These files were NOT previously decomposed and then broken. They are new decomp targets that came in with errors during normal decomp work. This is **expected behavior for a growing decomp**, not a regression.

### Phase 2: Classification Logic Fix (April 24 00:40)

**Commit:** a4034cfd1 — "jakx/scanners: fix two measurement bugs"

**Changes:**
- **Before:** split-failed = (failed_ct > 0) OR (error_ct > 0) OR (local_vars_top with no defuns)
- **After:** split-failed = (failed_ct > 0) OR (error_ct > 0)

**Effect:** Removed the `local_vars_top` trigger, which reclassified 51 files from split-failed → static-only. The 9 remaining files actually have error markers, so they correctly stay split-failed under the new logic.

**Assessment:** This commit did NOT introduce the regression; it REDUCED the split-failed count by reclassifying false positives. Good commit, appropriate fix.

### Phase 3: Partial Recovery (April 24 00:40 → 00:55 onwards)

**Timeline:**
- 00:55: split-failed = 9
- 01:00 onwards: Various batch migration commits
- 06:50: split-failed = 0 briefly
- 07:06: split-failed = 9 again
- Current (07:10): split-failed = 2

The split-failed count is volatile during this phase, suggesting active fixes and migrations are in flight.

## Classification of the 9 Files

All 9 files are **REAL decomp failures**, not false positives:

1. **cam-combiner** — 2 error markers, no defuns (split store errors)
2. **history** — 1 error marker, top-level function not converted
3. **lobby-menu-manager-h** — 1 error marker (header file)
4. **pad** — 1 error marker, no defuns
5. **prototype** — 1 error marker, no defuns
6. **sampler** — 6 error markers (split store failures on floats)
7. **target-pilot** — 1 error marker, no defuns
8. **wcar-skel-template** — 1 error marker (template file)
9. **wvehicle-weapons-h** — 1 error marker (header file)

## Root Cause Category

| Category | Count | Rationale |
|----------|-------|-----------|
| New decomp output | 9 | Files did not exist in decomp output on April 18 |
| Decomp errors (real) | 9 | All have ERROR markers; correctly classified as split-failed |
| Configuration change | 0 | No all-types.gc / jsoncs changes that would break these files |
| Decompiler C++ bug | 0 | No assertions or crashes; errors are well-formed |

## Suggested Fixes

These are **not urgent regressions**. They are newly-decomposed files that need attention:

1. **history** — "function was not converted to expressions" → likely needs type_casts or hacks.jsonc entry
2. **cam-combiner** — Split store errors → likely needs stack_structures.jsonc hint
3. **sampler** — Multiple split store failures → likely needs stack_structures or mips2c entry
4. **others** — Single ERROR markers → likely type-prop failures, check type_casts

## Conclusion

**No revert needed.** The "+9 split-failed" is not a regression but a **natural consequence of decomp scope growth**. The decomp output is intentionally broader; these files are legitimately broken by decompiler limitations. They should be queued in the normal mips2c/config fixup cycle.

The commit a4034cfd1 that reduced split-failed from 60→9 is a **correct fix** that eliminated false positives.
