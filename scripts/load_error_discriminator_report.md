# Load Error Discriminator: Classification Report

**Date:** 2026-05-14
**Source:** 100 sample "Could not figure out load" errors across 17 IR files
**Scope:** racing-critical (nav, entity, vehicle, wcar-drone, wvehicle-weapons) + utility + problematic

## Bucket Definitions

| Bucket | Meaning | Action |
|--------|---------|--------|
| **LOCAL CAST** | Register typed wrong locally. The correct type is inferable from local context (function signature, saved-register assignments, prior definitions). Cast at load site is safe and correct. | Generate type cast entry. |
| **UPSTREAM SIG** | Register arrived with wrong type from the caller (typically a0-a3 parameter typed as `object`). Casting here would mask the real bug — the call site or callee signature needs fixing. | Flag for review. Do not auto-cast. |
| **MASK-BUG** | Missing type definition (field doesn't exist at offset), deref-kind mismatch (l.hu on a float field), VU register issue, known no_type_analysis function, or decompiler bug. A cast would produce a bad output or silence a signal. | Skip entirely. |

## Discriminator Heuristics (numbered, in priority order)

### LOCAL CAST patterns

1. **s6 typed as uint/none/object → cast to `process`**
   - s6 IS the process pointer in the MIPS ABI. If the decompiler has it as anything other than a process subtype, the type was lost locally.
   - Safe: casting to `process` is always correct for pointer arithmetic on s6.
   - Example: `(set! v1 (l.wu (+ s6 140)))` where `curr_type=''` → cast s6→process at op

2. **gp typed as uint/none/object in a method → cast to method's `this` type**
   - gp = a0 at entry in virtually all methods (gprs save pattern). gp holds `this` for the entire function.
   - The method's `this` type is available from the function declaration line `.function (method N TypeName)`.
   - Example: `(method 73 net-game-mgr-artifact)`, gp→net-game-mgr-artifact

3. **a0 typed as uint/none/object in method, still at op < 5 → cast to method's `this` type**
   - Only safe when a0 hasn't been reassigned (early ops). Conservative: limit to op ≤ 3.

4. **Saved register (s5, s4, s3, s2) from parameter, typed as uint/none/object in method → cast to `this` type**
   - s5 = a1 at entry means it holds the first argument. In methods, a1 is often `object` by convention.
   - Conservative: only cast saved registers that trace to a0 (this), not other params (those are UPSTREAM SIG).
   - Actually, s5 from a0 is rare. More common: s5 = a1 → holds argument, which may have a known type from the call context.

5. **v1 typed as uint (from a previous load that succeeded but returned uint) → cast to `pointer`**
   - Many uint loads are actually handles/pointers that the decompiler couldn't type.
   - Cast to `pointer` resolves the dereference without over-committing to a specific type.
   - Example: `(set! a2 (l.wu a0))` where a0 = sllv result from uint → cast a0→pointer

6. **a0 typed as uint (from an extracted handle or ptr arithmetic) → cast to `pointer`**
   - Common pattern: ld → subu-s7 → sllv gives uint, then l.wu on the uint fails.
   - Cast to `pointer` at the load site fixes it.

### UPSTREAM SIG patterns

7. **a0/a1 typed as `object` in a method → MASK-BUG (really upstream)**
   - The parameter arrived as `object` from the caller. The callee's type annotation shows `[a1: object]`.
   - Casting inside this function would decompile but produce wrong output.
   - Fix: cast at the CALL SITE in the caller's type_casts.jsonc.

8. **Top-level function (not a method) with a0 typed as `object` or `''` → UPSTREAM SIG**
   - No method_type available → can't infer the correct type.
   - The caller or global signature needs fixing.

### MASK-BUG patterns

9. **Source register already has a concrete struct type → MASK-BUG**
   - The decompiler HAS the type but still fails the load. This means:
     a. The field at that offset doesn't exist in the type (missing field def)
     b. The access kind (l.hu, l.d, l.f) doesn't match the field's declared type (deref-kind mismatch)
   - A type cast won't help — it already has the right type.

10. **Known skip functions** → MASK-BUG
    - `(method 45 kras-pump-break-proxy)` — intentional no_type_analysis
    - `bsp-header.birth` — known next-blocker

11. **l.q access (quadword load) on any register → MASK-BUG**
    - l.q is VU-unit related and has different type-propagation rules.
    - Casting won't help — needs VU analysis or type defs.

12. **l.hu on a struct-typed register at offset 0 → MASK-BUG**
    - Type field at offset 0 is 4 bytes (l.wu), but code uses l.hu.
    - This is a genuine access-kind mismatch in the IR, not a type issue.

13. **Offset doesn't exist in the source register's type → MASK-BUG (missing field def)**
    - Example: spartacus-editor has fields, but offset 140 doesn't match
    - Fix: add field definition in all-types.gc

## Sample Classification Results

From the 100 samples, approximate breakdown:

| Bucket | Count | ~% |
|--------|-------|----|
| LOCAL CAST | 42 | 42% |
| UPSTREAM SIG | 18 | 18% |
| MASK-BUG | 40 | 40% |

Within LOCAL CAST:
- s6→process: 5 (all top-level process functions)
- gp→method_type: 12 (method bodies, offset loads into gp)
- a0→pointer (handle extraction): 18 (uint from handle arithmetic)
- v1→pointer: 7 (generic pointer needed)

## Implementation Notes

The discriminator check order must be:
1. Known skip? → MASK-BUG (fast reject)
2. Is source a concrete struct type? → MASK-BUG (fast reject)
3. s6? → LOCAL CAST (always safe)
4. Known no_type_analysis? → MASK-BUG
5. Parameter (a0-a3) with `object` type? → UPSTREAM SIG
6. l.q access? → MASK-BUG
7. gp in method with primitive type? → LOCAL CAST (gp = this)
8. a0 in method, op ≤ 3, primitive type? → LOCAL CAST (a0 = this)
9. uint/none type → LOCAL CAST (cast to `pointer`)
10. Concrete struct type → MASK-BUG
11. Everything else → UPSTREAM SIG
