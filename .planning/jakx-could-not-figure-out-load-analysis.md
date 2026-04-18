# "Could not figure out load" — Root-Cause Analysis

Scope: 20-min research task. Read-only; no decompiler runs, no rebuild, no edits
outside this file.

## 1. C++ source location

The error is thrown from the types2 forward-propagation pass:

- `decompiler/types2/ForwardProp.cpp:2224` —
  `throw std::runtime_error(fmt::format("Could not figure out load: {}", ...))`
- `decompiler/types2/ForwardProp.cpp:2226` — variant "(2)" for the else branch
  (non-`pointer`/non-`OBJECT_PLUS_PRODUCT_WITH_CONSTANT` inputs).

Both throws are the final fallthrough of
`load_var_op_determine_type(...)` (the enclosing function beginning around
line 2000). Control flow leading there:

1. If input is a known typespec, attempt `reverse_field_multi_lookup` for a
   matching field at the given offset.
2. If input is a plain `pointer` or `OBJECT_PLUS_PRODUCT_WITH_CONSTANT`, fall
   back to `uint`/`int`/`float` based on load size/signedness.
3. If input is `INTEGER_CONSTANT_PLUS_VAR` at offset 0, try field lookup on the
   `objects_typespec`.
4. Otherwise, throw.

So the error fires only when the **input register's type is neither a concrete
typespec with a matching field at the given offset nor a generic pointer**.
This is purely a symptom of upstream type inference failing; it is not a bug
in the load code itself.

## 2. Root cause patterns in jakx output

Two distinct upstream failures produce this error; they have different fixes.

### Pattern A — `define-extern` declared as `object` instead of the real type

Example: `attackable-hash_ir2.asm:12`
```
;; ERROR: failed type prop at 16: Could not figure out load: (set! a0 (l.wu a0))
```
MIPS trail (lines 49-51):
```
lw  a0, *attackable-hash*(s7)   ;; a0 <- *attackable-hash*   (typed 'object')
lwu a0,  0(a0)                  ;; a0 <- (l.wu a0)           -- throws
```
Root cause is `decompiler/config/jakx/all-types.gc:40593`:
```
(define-extern *attackable-hash* object) ;; attackable-hash
```
The trailing comment already admits the true type — the symbol is an
`attackable-hash`, not `object`. With `object` as input, step-1 field lookup
fails (no field of `object` at offset 0), and `object` is not a `pointer`, so
no fallback applies.

The same anti-pattern repeats throughout jakx all-types: `*cpad-list*` at
line 10015 is `object` with trailing `;; cpad-list`. Every `define-extern` of
a global variable that is currently `object` with a comment suggesting a real
type is a latent "Could not figure out load" site.

### Pattern B — Method argument `a0` has no type at block entry

Examples:
- `pov-camera_ir2.asm:2070` — `(method 57 pov-camera)` first instruction is
  `lwu a0, 52(a0)` with `a0: <uninitialized>`.
- `pov-camera_ir2.asm:3650` — `(method 55 pov-camera)` op 2 is
  `(l.d (+ a0 252))` with `a0: <uninitialized>`.
- Same for method 56 op 10 (`Called a function, but we do not know its type`),
  method 59 op 9 (same).

Root cause: the decompiler does not have a type for `(method N pov-camera)`
itself, so the method signature's implicit first-arg (`self : pov-camera`)
never seeds `a0`. All three affected methods are declared generically in
`all-types.gc:29225-29234`:
```
(pov-camera-method-55 () none) ;; 55
(pov-camera-method-56 () none) ;; 56
(pov-camera-method-59 () none) ;; 59
```
Empty `()` arg list means the decompiler treats `a0` as uninitialized on
entry. (In jak3 a similar family is declared with full signatures and the
errors disappear.)

### Pattern C — Function declared as bare `function`

Method 56/59 also hit `Called a function, but we do not know its type`
because `process-grab?` and `process-release?` are declared as:
```
decompiler/config/jakx/all-types.gc:39956-39957
  (define-extern process-grab?   function)  ;; (function process symbol symbol :behavior process)
  (define-extern process-release? function) ;; (function process symbol :behavior process)
```
Compare jak3 `all-types.gc:35027-35028`, which uses the full signature.
With the bare-`function` declaration the callsite `(jalr ra, t9)` cannot
derive the return type, so `v0` is tagged `<uninitialized>` and propagates
into subsequent loads — producing the cascade seen in methods 55/56/59.

## 3. Fix mechanism — which knob to turn?

All three patterns are **data-only fixes** — no C++ change is needed.

| Pattern | Fix file | Cost |
|---|---|---|
| A — bad `define-extern` type | `decompiler/config/jakx/all-types.gc` | edit the `define-extern` to use the real type (it's already in the trailing comment) |
| B — empty method signature | `decompiler/config/jakx/all-types.gc` (the `deftype` methods block) | fill in arg types; `self` is implicit |
| C — bare `function` extern | `decompiler/config/jakx/all-types.gc` | replace `function` with the full `(function ...)` signature |

`type_casts.jsonc` is the **alternative** when you don't want to touch
all-types (e.g. global variable whose real type is ambiguous, or a specific
register at a specific op index). The shape, from
`decompiler/config/jak3/ntsc_v1/type_casts.jsonc`:
```
"(method 55 enemy)": [
  [27, "a0", "process-focusable"],
  [30, "a0", "process-focusable"]
],
```
Form: `[op_index, register, type]` or `[[start_op, end_op], register, type]`.
The jakx `type_casts.jsonc` is currently *empty* (16 lines, all comments):
`decompiler/config/jakx/ntsc_v1/type_casts.jsonc`.

Per-register casts are loaded at `decompiler/util/config_parsers.cpp` and
consumed during type propagation to seed specific regs at specific ops.

## 4. Proposed fixes

### attackable-hash

**Preferred** — fix `all-types.gc:40593`:
```
(define-extern *attackable-hash* attackable-hash)
```
(Requires `(deftype attackable-hash ...)` to exist. It doesn't yet in
jakx all-types — the banner at line 40591 says "is already defined!" but
no `deftype` is present. First port the `attackable-hash` deftype from
the `.o` file, then flip the extern.)

**Alternative (if deftype is unavailable)** — add to
`decompiler/config/jakx/ntsc_v1/type_casts.jsonc`:
```
"(top-level-login attackable-hash)": [
  [15, "a0", "(pointer uint128)"]
]
```
This at least gives the load a pointer so the fallback picks `uint` and
the function proceeds. Not as clean as the real type.

### pov-camera methods 55/56/59/57

**Preferred** — fill method signatures in `all-types.gc:29225-29234`:
```
(pov-camera-method-55 () none)  ;; 55
(pov-camera-method-56 () none)  ;; 56
(pov-camera-method-57 () none)  ;; 57
(pov-camera-method-59 () none)  ;; 59
```
Empty `()` leaves `a0` untyped on entry. Since these are methods of
`pov-camera`, `self : pov-camera` is implicit — the decompiler knows to
bind `a0 = self : pov-camera` *only* when the method signature has a real
arg list. Even `((self pov-camera)) none` would work; usually the idiom
is just `() none` and the decompiler seeds `self` from the method owner
(verify via any pov-camera method that decompiles cleanly). If the `() none`
declarations really do leave `a0` untyped in jakx, the type_casts fallback is:
```
"(method 55 pov-camera)": [[0, "a0", "pov-camera"]],
"(method 56 pov-camera)": [[0, "a0", "pov-camera"]],
"(method 57 pov-camera)": [[0, "a0", "pov-camera"]],
"(method 59 pov-camera)": [[0, "a0", "pov-camera"]]
```

Also fix `all-types.gc:39956-39957`:
```
(define-extern process-grab?   (function process symbol symbol :behavior process))
(define-extern process-release? (function process symbol :behavior process))
```
(Copy from jak3 `all-types.gc:35027-35028`.)

## 5. Top files by marker count

### Top 10 by `Could not figure out load` alone (the hard load failures)

| count | file |
|---|---|
| 66 | `decompiler_out/jakx/vehicle-util_disasm.gc` |
| 36 | `decompiler_out/jakx/net-player_disasm.gc` |
| 36 | `decompiler_out/jakx/net-hud_disasm.gc` |
| 25 | `decompiler_out/jakx/net-world_disasm.gc` |
| 22 | `decompiler_out/jakx/hud-effects_disasm.gc` |
| 21 | `decompiler_out/jakx/texture_disasm.gc` |
| 19 | `decompiler_out/jakx/rigid-body-object_disasm.gc` |
| 19 | `decompiler_out/jakx/process-drawable_disasm.gc` |
| 17 | `decompiler_out/jakx/vehicle_disasm.gc` |
| 16 | `decompiler_out/jakx/actor-link-h_disasm.gc` |

### Top 10 by combined `failed to figure out` + `Could not figure out load`

| count | file |
|---|---|
| 936 | `decompiler_out/jakx/car-tables_disasm.gc` |
| 707 | `decompiler_out/jakx/in-game-menu-hud_disasm.gc` |
| 697 | `decompiler_out/jakx/hud-widgets-3_disasm.gc` |
| 634 | `decompiler_out/jakx/net-game-modes2-h_disasm.gc` |
| 626 | `decompiler_out/jakx/scert-10-h_disasm.gc` |
| 614 | `decompiler_out/jakx/scert-8-h_disasm.gc` |
| 614 | `decompiler_out/jakx/scert-7-h_disasm.gc` |
| 599 | `decompiler_out/jakx/hud-cash_disasm.gc` |
| 578 | `decompiler_out/jakx/scert-3-h_disasm.gc` |
| 566 | `decompiler_out/jakx/scert-9-h_disasm.gc` |

Note: `failed to figure out what this is` (emitted at
`decompiler/analysis/final_output.cpp:576`) is a *different* failure — the
top-level emitter couldn't match a form to any known shape. These are
dominated by data-heavy files (`car-tables`, `in-game-menu-hud`,
`scert-N-h` script-data) where hand-written data tables confuse the
top-level detector. Fixing them needs `label_types.jsonc` entries, not
`type_casts.jsonc`. Different problem, different fix knob.

## 6. Recommendation

**This is ~1-2 hours of all-types editing, not weeks of C++ rewrite.**

Action plan:
1. Grep `all-types.gc` for `define-extern .* object.*;; [a-z]` — every such
   line is a Pattern-A candidate. Flip the type using the trailing comment.
2. Grep `all-types.gc` for `define-extern .* function)` (bare `function`
   rather than `(function ...)`) and port the signature from jak3's
   all-types when present.
3. Grep for method-declaration blocks where every line looks like
   `(foo-method-N () none)` — compare with jak3's equivalent `deftype` and
   fill in arg lists.
4. Re-run the decompiler. Anything still failing gets a per-op entry in
   `decompiler/config/jakx/ntsc_v1/type_casts.jsonc` (currently empty, so
   there's nothing to conflict with).

No C++ changes are indicated. The types2 forward-prop code behaves
correctly — it's the data hints that are missing.

The "failed to figure out what this is" markers in data-heavy files are a
separate workstream (label_types.jsonc), and the worst offenders
(`car-tables`, `scert-N-h`) are in script / table formats unique to jakx
that would benefit most from targeted label-type work.
