# Jakx applier priority queue

_User-approved tool roadmap · 2026-04-24_

Orchestrator (meta-projects) drafted and user approved these 7 applier/tool projects. Ranked by error-category leverage against current status.md. Sonnet sessions should self-select from this queue when current work ships. Every applier MUST integrate `scripts/jakx_watch/apply_guard.py`.

## Priority 1 — `clobber_fixup.py` (drains ~3456 errors)

**Target category:** `Function may read a register that is not set: REG` — current #1 error bucket.

**Pattern:** Function definitions missing clobber-list declarations → decompiler can't prove register liveness → emits the error per call site.

**Shape:**
1. Parse every `Function may read a register that is not set: <REG>` error from `decompiler_out/jakx/**/*_ir2.txt`.
2. For each: determine the calling function, inspect its disasm header for declared clobbers.
3. Cross-reference with jak3's equivalent function (most clobber declarations are portable).
4. Emit patch to `decompiler/config/jakx/ntsc_v1/register_usage.jsonc` (if that's the right config) or wherever jakx puts clobber overrides.
5. Guard with `apply_guard.run_with_guard()`, strict defaults.

**Difficulty:** HARD (register-liveness analysis, cross-reference jak3).
**Estimated time:** 3-4 hours.
**Ready to build:** Yes — data is in IR2 output already.

## Priority 2 — `type_cast_extractor.py` (drains ~867 errors)

**Target categories:** `failed type prop at N: Could not figure out load: (set! REG (l.wu ...))` — categories 3/6/7/8 combined.

**Pattern:** Error message itself contains the op index, source register, and offset. E.g., `set! REG (l.wu (+ REG N))` means "at op N, REG needs a cast to infer load type".

**Shape:**
1. Parse these errors from IR2 output.
2. Extract (file, op_N, src_register, offset) — all present in the error text.
3. Heuristically infer type from neighboring casts or field-type lookups (similar to `inspect_to_type_casts.py`).
4. Emit entries to `decompiler/config/jakx/ntsc_v1/type_casts.jsonc`.
5. Guard with `apply_guard`.

**Difficulty:** MEDIUM.
**Estimated time:** ~1-2 hours.
**Ready to build:** Yes — easiest because error messages are self-describing.

## Priority 3 — `asm_func_apply` evolution (drains ~722 errors)

**Target category:** `function was not converted to expressions. Cannot decompile.`

**Pattern:** Functions using PS2/VU extended opcodes that mips2c can't handle. Need `:asm-func` declaration + matching mips2c-suppress entry in hacks.jsonc.

**Shape:** Evolve existing `asm_func_apply.py` to:
1. Auto-scan "function was not converted" errors.
2. Check each function's disasm for non-standard opcodes (VU_CRASH_OPCODES regex already exists, extend to all non-standard MIPS).
3. Emit `:asm-func` + hacks.jsonc mips2c-suppress ATOMICALLY (both files in one commit — prevents c5f7ff573 class of bug).
4. Guard with `apply_guard`.

**Difficulty:** MEDIUM-EASY (80% already built in existing asm_func_apply.py).
**Estimated time:** ~1 hour to finish.
**Currently owned by:** ff51092d (they're on split_store_fix first; this is their natural next task).

## Priority 4 — `method_body_reader.py` library

**Target:** Helper module. Unlocks more of the 718 queued `return_mismatch_apply` entries.

**Pattern:** Current return_mismatch_apply is too conservative — filters to single safest edit. With a helper that can read a method body and return its actual return type, the applier can safely batch larger patterns (e.g., `none→int` class) because each edit is validated against the real body.

**Shape:**
1. `method_body_reader.read(type_name, method_idx) → ReturnInfo` — returns actual return type from decomp output.
2. `return_mismatch_apply.py` imports it; uses `.read()` to validate each proposed edit before applying.

**Difficulty:** EASY.
**Estimated time:** 30 min.
**Ready to build:** Yes.

## Priority 5 — `safe_label_types_copy.py`

**Target:** Automates `label_types_copy_queue.md` (142 entries) safely per gotcha #20.

**Pattern:** Current manual copy-port (9456ca98's tie-methods attempt) hit an unactivated-type reference and crashed 324 files. Automate the verification step.

**Shape:**
1. For each "confirmed" entry in label_types_copy_queue.md: grep the referenced type name against all-types.gc.
2. Skip entries where type is inside a `#| |#` block or absent entirely.
3. Emit filtered batch to `decompiler/config/jakx/ntsc_v1/label_types.jsonc`.
4. Guard with `apply_guard` (coverage drop veto will catch any slipped references).

**Difficulty:** EASY.
**Estimated time:** ~45 min.
**Ready to build:** Yes.

## Priority 6 — `dependency_graph_activator.py`

**Target:** Makes `cluster_impact.md` usable. Automates safe type-cluster activation per gotcha #6 (≤5 types per commit).

**Pattern:** For a target cluster of commented types: walk parent-type dependencies and field/method type refs, produce a topologically-ordered activation plan in 5-type-batch commits.

**Shape:**
1. Parse cluster_impact.md.
2. For each cluster: build DAG of dependencies.
3. Emit a sequence of commits of ≤5 types each, each batch activated + scanner-run + apply_guard-vetted.
4. Halt chain on first gate veto; report the break-point.

**Difficulty:** HARD (needs cluster_impact semantics + DAG analysis).
**Estimated time:** 3-4 hours.
**Currently cluster_impact.md is DORMANT** (all rows net_sf=0) — low urgency. Revisit when clusters regenerate with leverage.

## Priority 7 — Pre-commit gotcha-rule enforcer

**Target:** Enforces gotchas.md #1-#20 as a git pre-commit hook. Would have caught today's 14b308c3e bug (gotcha #20).

**Pattern:** Parse the staged diff, check against a set of rules:
- More than 5 deftypes activated in one commit → block (#6)
- Range cast added to recursive type → block (#7)
- label_types entry referencing non-active type → block (#20)
- :size-assert changed without :offset-assert recompute → warn (#3)
- mips2c-suppress entry without opcode vet → warn (#10)

**Shape:**
1. `.githooks/pre-commit` script calls `scripts/jakx_watch/gotcha_enforce.py`.
2. Each rule is a Python function returning `(passed, reason)`.
3. Fails commit with specific rule citation.

**Difficulty:** MEDIUM.
**Estimated time:** ~2 hours (20 rules × ~6 min each).

## Self-select guide

When your current task ships:
1. Grep git log for `feat(jakx_watch): <tool_name>` — if landed, pick next one.
2. **Route by error-category leverage first, difficulty second.** A drained #1 category is more impactful than 3 drained #5 categories.
3. When in doubt, start with Priority 4 (method_body_reader — smallest, unlocks return_mismatch which is already #1 ROI per winner_patterns).
4. If you author one, add a row to `tool_utilization.md` once shipped.

## Anti-patterns from this session

- `c5f7ff573` bulk mips2c-suppress without per-entry opcode check → +200 crashed files, reverted. (See gotcha #10.)
- `14b308c3e` label_types copy without type-activation grep → 324 crashed files, surgically fixed. (See gotcha #20.)

Every applier must run the scanner post-apply and veto via apply_guard. No exceptions.
