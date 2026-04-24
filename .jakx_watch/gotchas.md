# Jak-X decomp gotchas — read before touching all-types.gc / type_casts.jsonc

Recurring mistakes distilled from recent commit history. New session? Read this first.

## all-types.gc

1. **`#| ... |#` block comments swallow deftypes silently.** When activating a type, scan the WHOLE block for an opening `#|` above and a closing `|#` below — not just the line directly before the deftype. Symptom: scanner fails rc=134 with "Type X is unknown" even though you see the deftype in git diff. Seen twice this week (475fd52cd → 621ec3815 / f1248cc62 for part-tracker-init-params).

2. **When activating a deftype, disable its matching `define-extern` stub.** Pattern: find `(define-extern typename object)` and comment with `;; (define-extern typename object) ;; clobbers active deftype`. Otherwise the stub re-declares the type as `object` and clobbers your fields. See `clobber_queue.md` for the full set.

3. **`:size-assert` is authoritative — recompute, don't guess.** If you change field layout, recalculate offset+size. Wrong `:size-assert` → scanner crashes rc=134 at load time on that type. (77909ba9e debug-rigid-body-move had `#x1b4` vs actual `#x1b0`.)

4. **`:method-count-assert` must match parent + own count.** Subtypes inherit parent methods. Check parent's count before asserting.

5. **Activation order matters.** If type B depends on type A, activate A first. Use `cluster_impact.md` to plan chains.

6. **BULK activation attempts FAIL without per-item validation.** Pattern: activating 5+ types in one commit without checking each one → reverts cost +765 mean errors. Worst offenders: label_types bulk copy-port by NAME only (not type match) → wrong hints applied (+5717 errors reverted); touching-list :methods batch → method-count mismatch (+5254); sky-work vector4w inline crash (+4903). Activation must be: 3-5 types MAX per commit, each sampled against offline-test green. (Case: 0c6a90abe label_types revert, 90c87219c touching-list revert, c9ef54ccc sky-work revert.)

## type_casts.jsonc

7. **NEVER use RANGE casts on recursive types** — nav-control ↔ nav-state ↔ nav-mesh, entity cycles, any type whose methods call sibling methods that recurse back. Range casts let type_prop pass on multiple methods → form-builder recurses exponentially → OOM rc=137, 20+GB RSS in seconds, blocks 200+ downstream files. Use single-op casts only. (Case: 0c2ee6182 caused OOM, 8db03ded2 reverted; 233 files blocked ~90 min.)

8. **NEVER "correct" :methods return types blind — read the method body first.** Pattern: Session 16 fixed 58 method return types by comparing to parent signature, but inverted the logic (int→none when should be none→int). Blind batch corrections cost +7071 errors. Rule: for each method, (1) read the actual defun body in decompiler output, (2) check what it returns, (3) compare to declaration, (4) fix declaration to match actual (not vice versa). Only then batch-apply after peer review. (Case: fix jakx/all-types: fix 58 return type mismatches caused +7071 errors, reverted.)

9. **TYPE-header reads at `offs=-4`** are the top error cluster (~150). Shape: `(l.wu (+ reg -4))` on untyped register trying to read the type tag. Fix: cast source reg to `basic` at that op. See `bulk_fix_queue.md` row #1 — coordinate there to avoid duplicate effort.

10. **mips2c bulk-suppress in hacks.jsonc requires PS2 extended-opcode vetting.** When batch-adding `mips2c-suppress` entries without checking for VU/PS2 extended opcodes (mtlo1, mflo1, mula.s, madda.s, madd.s, etc.), the C++ decompiler crashes at `get_imm()` trying to read immediate operands that don't exist in standard opcodes. Crash signature: rc=134 during form-builder, immediate error "invalid immediate". Use the `VU_CRASH_OPCODES` regex in `scripts/jakx_watch/asm_func_apply.py` to check each candidate first. (Case: c5f7ff573 bulk-added 548 entries, crashed on mtlo1; reverted 1672309a3.)

## Decompiler + scanner workflow

11. **Always run `scripts/jakx_watch/run.sh` (flock-serialized).** Bare `decompiler` invocations race each other when two sessions run concurrently → corrupted IR2, mis-attributed metrics. Set `JAKX_WATCH_WAIT=1` if you need to serialize against in-flight runs. (dc31a5eb0 added the flock wrapper.)

12. **`--dump_current_output` on offline-test is the green-gate for real-clean files.** If you activate a file → run offline-test → diff; only then mark as "migration candidate" (real-clean with offline-test green). See `migration_candidates.md` — 457 candidates tracked, 118 green.

13. **rc=134 = runtime_error throw** (type/size error, unknown type). **rc=137 = OOM kill.** Different fixes — 134 is usually an all-types.gc or type_casts issue; 137 is usually a recursive-type form-builder blowup.

## Game runtime (when testing boot)

14. **goalc build log goes to /tmp/goalc-build.log.** Always redirect and tail that, not task-local temp files. Multiple cron agents consume it.

15. **Use MCP tools over bash for the live game.**
    - `read_game_log(filter_pattern="X")` beats `cat /tmp/gk-*.log | grep X`
    - `game_status` beats `pgrep -f "gk.*jakx"`
    - `evaluate_goal(expr)` beats goalc subprocess wrappers
    Bash is still needed for: kill (`pkill -9 -f 'gk.*jakx'`), start, cmake.

## Meta — measurement

16. **Measure delta per commit.** Note errors-before + errors-after in commit message. Without attribution, bulk_fix_queue can't rank future patterns by EV. Example: `fix(...): pattern-pass offs=-4 (Δerr 8376 → 8226, -150)`.

17. **Lane boundaries = commit scope, not file access.** Read anything. Only COMMIT within your lane. Coordinate via queue files (`atoll_blocker_queue.md`, `bulk_fix_queue.md`), not file locks.

## Scope reminder (OpenGOAL canonical order)

18. **Decomp quality FIRST, boot/graphics/gameplay LAST.** OpenGOAL team's order (mega-issue #1570):
    1. Language/decompiler quality
    2. Auto-generated all-types
    3. Compiler working
    4. Test framework
    5. KERNEL.CGO
    6. Bulk engine decomp ← **we are here**
    7. Graphics/sound
    8. Boot → title → gameplay
    Hand-porting gameplay code before step 6 is complete is premature. If stuck, redirect to step 6 work.

## all-types.gc (addendum)

19. **Inline struct containers with nested `:inline` arrays/fields need `:pack-me` when interior offsets land on non-8-byte boundaries.** Pattern: parent struct embeds an `:inline` child type; the child's natural alignment bumps a sibling field past its declared `:offset`. Symptom: `:size-assert`/`:offset-assert` mismatch, or runtime crash on type init with "offset N != expected M". Fix: add `:pack-me` to the parent struct deftype. Seen in: `a9f07427a` driver alignment crash; `a77f317f5` sky-work orbit alignment; `4ccb676b7` curve :pack-me at offset 20; `7061aa760` curve :inline at offset 20. Mined from 11 commits in gotchas_candidates.md pattern `inline_alignment`.
