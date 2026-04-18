# Jak X decomp failure patterns

Survey of `decompiler_out/jakx/` plus the `banned_objects` list in `decompiler/config/jakx/jakx_config.jsonc`, post-rerun of every banned file to classify crash vs stub vs clean.

## Totals

- **275** `_disasm.gc` files contain the stub `;; ERROR: top level function was not converted to expressions`. Of these, **269** are regular (not banned) and **6** are banned-but-still-stub.
- **38** real entries in `banned_objects` (plus one junk entry `banned_objects` — the literal string — which is not a file).
  - **8** still crash the decompiler today (distinct C++ asserts, listed below).
  - **6** no longer crash but still emit a stub.
  - **24** now decompile cleanly and can be **un-banned immediately**.
- Grand total still-failing: **283** files (269 + 6 + 8).

## Un-ban candidates (decompile cleanly now)

These **24** files in `banned_objects` produce valid `_disasm.gc` when run. They were likely banned when the decompiler was at an earlier state and the config was never cleaned up. Removing them is a zero-work win:

- `hud-player-indicators`, `vehicle-antenna`, `vehicle-reticle`, `wcar`
- `wcar-base`, `wcar-falcon`, `wcar-mongoose`, `wcar-skel`
- `wcar-wombat`, `wvehicle-ai`, `wvehicle-effects`, `wvehicle-events`
- `wvehicle-net`, `wvehicle-part`, `wvehicle-physics`, `wvehicle-race`
- `wvehicle-sounds`, `wvehicle-states`, `wvehicle-util`, `wvehicle-weapons-oil`
- `wvehicle-weapons-util`, `wvehicle-weapons2`, `wvehicle-weapons3`, `wvehicle-wheel`

## Top error categories across 275 stub files

How many of the 275 stub files trip each category (a file can be in multiple buckets):

| Stub files | Category | Root cause | Fix approach |
|-----------:|----------|------------|---------------|
| 262 | Didn't know type of symbol | Forward-decl only or never-declared global in `all-types.gc` | Add `(define-extern foo X)` to `decompiler/config/jakx/all-types.gc` |
| 207 | Unknown symbol | Referenced type/function name missing from `all-types.gc` | Add forward decl in `all-types.gc` (copy from jak3 if it exists) |
| 107 | Return type mismatch | `all-types.gc` function signature disagrees with how jakx uses it | Adjust return type in `all-types.gc` (most `int vs none` = wrong `none` annotation) |
| 81 | Func may read unset reg | Function signature has wrong argcount — a0/a1 uninit | Fix arg count/type in `all-types.gc` |
| 73 | Could not figure out load | Load through a pointer whose type propagator can't resolve | Downstream of `Unknown symbol`/`Didn't know type` — fix upstream first |
| 60 | Failed to convert (mtlo1 s6) | Jak X-specific `mtlo1 s6` macc sequence not handled in `atomic_op_builder.cpp` | **Decompiler C++ patch** — extend `convert_mt{lo,hi}1_*` converters |
| 29 | add failed: uninitialized/integer | Downstream of upstream type-prop failure | Fix upstream signature / symbol |
| 27 | CFG building failed | Control flow pattern CFG pass rejects (early-return, odd fallthrough) | Patch CFG pass OR mark function asm in `asm_functions.jsonc` |
| 22 | Called function of unknown type | Call through register with unknown function type | Usually follows `Unknown symbol` for the func name |
| 21 | Unsupported inline assembly: sllv | `sllv rD, rS, r0` used by jakx (shift-by-zero = identity) | **Decompiler patch** — recognize `sllv _, _, r0` as mov; OR mark as asm |
| 16 | Flagged as asm by config | Listed in `asm_functions.jsonc`; stub is expected | Port ASM manually or leave stub |
| 15 | Flagged as asm because of sd s7 | Uses `sd s7, 16(sp)` — non-standard prologue | Patch prologue heuristic OR mark as asm |
| 15 | Type X is not defined | Typename never declared | Add deftype to `all-types.gc` |
| 14 | Strange gotos | Warning only | Review manually; usually benign |
| 10 | run-function-in-process with invalid function type | State/callback signature wrong in `all-types.gc` | Fix signature — batches across 10 `net-*-h` files |
| 5 | Unsupported inline assembly: srl/daddu | ASM sequences decompiler doesn't decode | Add to `asm_functions.jsonc` or patch decompiler |
| 4 | Bad vector register dependency | VU `vf2` chain not recognized | Leave as asm (particle/gfx code) |
| 2 | Failed store | Store through unresolved-type pointer | Fix upstream type |
| 2 | Type X is not fully defined | Forward-decl exists, deftype missing | Replace forward-decl with full deftype |
| 1 | Stack slot mismatch | Inferred stack slot size disagrees with caller | Add `stack_structures` hint |

**Reading the table**: the category counts are not mutually exclusive — a stub file typically has 3–5 different errors. The top category (*Didn't know type of symbol*, 262/275) is so broad it's almost universal but diluted across ~200 distinct symbols, so no single symbol fix unlocks it. The strong levers are the mid-rank rows with concentrated impact: `mtlo1 s6` (60 files, single C++ fix) and `sllv` (21 files, single C++ fix).

## Missing types & symbols (ordered by stub-files affected)

### Types referenced as `Type Error: Type X is not fully defined/defined`

- `skeleton-group` — 13 stub + 0 non-stub. First stub files: `collision-editor, driver, generic-obs, intro-part, intro-scenes2, keyboard, menu2-COMMON-GAME, net-eco-types`
- `process-drawable` — 1 stub + 4 non-stub. First stub files: `process-drawable`
- `joint-control` — 1 stub + 1 non-stub. First stub files: `process-drawable`
- `scene` — 2 stub + 0 non-stub. First stub files: `intro-scenes, intro-scenes3`
- `process-focusable` — 0 stub + 1 non-stub. First stub files: ``
- `region-prim-area` — 0 stub + 1 non-stub. First stub files: ``
- `sparticle-launch-control` — 1 stub + 0 non-stub. First stub files: `generic-obs`

### Types appearing as `Unknown symbol` (need at least forward-decl)

- `in-game-hud` — 12 stub files. Examples: `hud-cash, hud-high-scores, hud-results, hud-results-grand-prix, hud-widgets-2, hud-widgets-3`
- `process-drawable` — 9 stub files. Examples: `daxter, generic-obs-h, joint-exploder, main, net-eco-h, race-obs`
- `*part-group-id-table*` — 6 stub files. Examples: `atoll-part, menu2-part, net-race-hud, weather-part, wvehicle-hud, wvehicle-weapons-part`
- `*cpad-list*` — 5 stub files. Examples: `collision-editor, hud-cash, hud-high-scores, main, visvol-edit`
- `*net-game-mgr*` — 5 stub files. Examples: `hud-results, hud-widgets, net-artifact, net-boss-battle, net-player`
- `*net-process-mgr*` — 4 stub files. Examples: `net-mgr-medius, net-race, net-world, process-nettable`
- `*part-id-table*` — 4 stub files. Examples: `merc-death, net-rushhour, particle-curves, water-part`
- `process-focusable` — 4 stub files. Examples: `anim-tester, net-simple-destruct-h, wvehicle-weapons-aux, wvehicle-weapons-proj`
- `rigid-body-object` — 3 stub files. Examples: `construction-obs-h, rigid-body-object, vehicle-debris`
- `vehicle` — 3 stub files. Examples: `vehicle, vehicle-effects, vehicle-net`
- `*gui-control*` — 2 stub files. Examples: `level, loader`
- `*medius-player-cache*` — 2 stub files. Examples: `net-mgr-medius-players, net-mgr-medius-players-h`
- `net-available-game` — 2 stub files. Examples: `net-mgr-h, net-mgr-medius`
- `*screen-shot-work*` — 2 stub files. Examples: `capture-h, main`
- `*sound-bank-string*` — 2 stub files. Examples: `level, net-world`

### Globals needing `(define-extern X TYPE)`

Stub-file count per global (most in tail, ~1 file each). Top entries:

- `*scert-function-id*` — 5 file(s): `net-mgr-async, net-mgr-dme, net-mgr-medius, net-mgr-mgcl, scert-funcs`
- `*in-game-menu-process*` — 2 file(s): `in-game-menu-hud, main`
- `*ghost-info-ptr*` — 2 file(s): `net-world, net-world-h`
- `*flash0*` — 1 file(s): `mood`
- `*palette-fade-controls*` — 1 file(s): `time-of-day-h`
- `*nav-triangle-test-count*` — 1 file(s): `nav-control`
- `*HACK-find-nearest-focusable-ignore*` — 1 file(s): `find-nearest-h`
- `*scert-extra-params*` — 1 file(s): `net-init`
- `*tmp-construct-transition*` — 1 file(s): `net-enemy-h`
- `*hud-deathmatch-single*` — 1 file(s): `net-deathmatch`

The long tail (~200 one-off globals) is what pushes 262 files into the 'Didn't know type' bucket. Each fix is ~1 line in `all-types.gc` but batches poorly. A grep-based sweep that harvests `*symbol*` names from decompile output and emits `(define-extern *symbol* object)` stubs would clear most of them.

## Top load-offset patterns (stub files)

Loads where the decompiler couldn't figure out the struct type at a given offset. These are downstream of missing/incomplete types — fixing upstream types resolves most. Offsets hint at the target type's field layout:

| Stub files | Offset | Likely referenced field |
|-----------:|--------|-------------------------|
| 18 | `(+ a0 -4)` | type tag of basic (object header) |
| 14 | `a0)` | raw pointer deref |
| 10 | `gp)` | top-level / static var |
| 8 | `(+ a1 4)` | 2nd field of argument |
| 8 | `(+ gp 36)` | offset 9 in static struct |
| 7 | `(+ gp 4)` | field 1 of static |
| 7 | `(+ gp 24)` | field 6 of static |
| 6 | `(+ gp -4)` | type tag of static object |
| 5 | `(+ gp 40)` | field 10 of static |
| 5 | `(+ gp 8)` | field 2 of static |
| 4 | `(+ gp 12)` | field 3 of static |
| 4 | `(+ gp 16)` | field 4 / vector-w |
| 4 | `(+ a0 16)` | field 4 / vector-x |
| 4 | `(+ a0 36)` | field 9 |
| 4 | `a1)` |  |
| 4 | `(+ a0 4)` | field 1 of arg |
| 4 | `(+ gp 60)` | field 15 of static |
| 4 | `(+ gp 284)` | deep top-level field |
| 3 | `(+ s5 16)` | self-ptr field 4 |
| 3 | `(+ a0 316)` | `process-drawable`/`nav-state` deep field |
| 3 | `(+ t0 16)` | field 4 of t0 |
| 3 | `s5)` |  |
| 3 | `(+ a0 76)` | field 19 |
| 3 | `(+ a0 20)` | field 5 |
| 3 | `(+ a0 12)` | field 3 |

**Interpretation**: `(+ X -4)` fails = type of X is totally unknown (fix upstream). `(+ gp ...)` = offset into a static; resolve by typing the `*global*` that gp aliased. `(+ a0 ...)` at non-trivial offsets points at 2–3 repeated types — adding `process-drawable`, `in-game-hud`, `wcar-base` clears most of the deep-offset rows.

## Decompiler C++ crashes (hard crashes today)

Reproduced with: `build/Release/bin/decompiler/decompiler decompiler/config/jakx/jakx_config.jsonc iso_data/ decompiler_out/ --version ntsc_v1 --config-override '{"allowed_objects":["<file>"],"banned_objects":[]}' --disable-ansi`.

Grouped by assertion site:

- **decompiler/Function/CfgVtx.cpp:115** — `Assertion failed: 'x'` — 3 file(s): `race-line`, `collide-mesh`, `collide-shape`
- **decompiler/analysis/cfg_builder.cpp:32** — `Assertion failed: 'irb'` — 2 file(s): `net-mgr-medius-cache`, `editable`
- **decompiler/analysis/cfg_builder.cpp:1881** — `Assertion failed: 'op_as_expr'` — 1 file(s): `entity`
- **decompiler/analysis/atomic_op_builder.cpp:1345** — `Assertion failed: 'i2.get_src(1).get_reg() == temp'` — 1 file(s): `task-control`
- **decompiler/analysis/cfg_builder.cpp:724** — `Assertion failed: 'false'` — 1 file(s): `water-anim`

All 8 crashes sit inside the CFG-builder / atomic-op-builder pipeline — not the type system. These need C++ patches to the decompiler itself; they won't be fixed by `all-types.gc` edits.

## High-leverage fixes (ranked)

Each estimate is direct stub-to-partial unblocking; type fixes cascade further via the load-offset table.

1. **Un-ban the 24 already-passing files** (config-only, one-line each). Unblocks 24 files instantly, zero risk.
2. **Patch `atomic_op_builder.cpp` to handle jakx `mtlo1 s6` sequence** — unblocks up to **60 stub files**. #1 decomp-engine issue; the jakx asm uses a variant `mtlo1` pattern the jak3 decomp doesn't recognize.
3. **Patch `atomic_op_builder.cpp` to recognize `sllv X, Y, r0` as identity-mov** — unblocks **21 stub files**.
4. **Add `process-drawable` full deftype to `decompiler/config/jakx/all-types.gc`** (copy from jak3, verify offsets). Directly touches 9+5=14 files AND unblocks downstream `(+ a0 ...)` load rows.
5. **Add `in-game-hud` type** (jakx HUD base class) — **12 stub files** (all `hud-*`, `in-game-menu-hud`, `intro-scenes2`, `race-manager`).
6. **Fix `net-*-h` header signatures around `run-function-in-process`** — **10 stub files**: `level, net-eco-h, net-game-modes-h, net-game-modes2-h, net-player-h, net-powerup-h, net-race-h, net-simple-destruct-h, net-world-h, process-nettable`.
7. **Add `wcar-base` type** — 12 stub files reference it (all `wcar-*`).
8. **Add `driver` type** — 23 files reference it as `Unknown symbol`.

Fixes 2 + 3 alone (two C++ decompiler patches) unblock up to **81 stub files** without touching any type definitions.

## Appendix A: stub files with first error (269 non-banned + 6 banned-stub = 275)

Format: `file` — first distinct WARN/ERROR line from `_ir2.asm` (truncated to 90 chars).

- `actor-hash` — E: failed type prop at 48: Unknown symbol: actor-hash-buckets
- `actor-hash-h` — W: Return type mismatch int vs none.
- `ambient-h` — E: failed type prop at 18: Unknown symbol: talker
- `anim-tester` — E: failed type prop at 59: Unknown symbol: process-focusable
- `atoll-effects` — W: Return type mismatch texture-anim-array vs none.
- `atoll-ocean` — E: failed type prop at 12: Unknown symbol: *ocean-colors-atoll*
- `atoll-part` — E: failed type prop at 1: Unknown symbol: *part-group-id-table*
- `attackable-hash` — E: failed type prop at 15: Unknown symbol: *attackable-hash*
- `background` — E: failed type prop at 0: Unknown symbol: background-work
- `blit-displays` — E: failed type prop at 3: Unknown symbol: blit-displays-work
- `bones` — E: failed type prop at 9: Called a function, but we do not know its type
- `bsp` — W: Return type mismatch function vs none.
- `cam-debug` — E: failed type prop at 2: Unknown symbol: *camera-old-cpu*
- `cam-debug-h` — E: failed type prop at 52: Unknown symbol: *cam-layout*
- `cam-layout` — E: failed type prop at 115: Unknown symbol: volume-descriptor-array
- `cam-master` — E: Decompiler type system did not know the type of symbol cam-master-active. Add it!
- `cam-states-dbg` — W: Return type mismatch state vs none.
- `cam-update` — E: failed type prop at 17: Unknown symbol: *save-camera-inv-rot*
- `camera-defs-h` — W: Return type mismatch int vs none.
- `capture` — W: Return type mismatch function vs none.
- `capture-h` — E: failed type prop at 31: Unknown symbol: *screen-shot-work*
- `car-info-h` — W: Return type mismatch string vs none.
- `car-tables` — E: failed type prop at 12: Unknown symbol: *car-upgrade-info*
- `car-textures` — E: failed type prop at 114: Unknown symbol: *car-level-array*
- `cloth` — E: failed type prop at 3: Unknown symbol: verlet-particle-system
- `collide` — W: Return type mismatch (array uint32) vs none.
- `collide-probe` — E: failed type prop at 32: Unknown symbol: collide-probe-stack
- `collide-shape-h` — E: failed type prop at 166: Unknown symbol: collide-shape-moving
- `collide-touch-h` — E: failed type prop at 29: Unknown symbol: touching-prims-entry-pool
- `collision-editor` — E: failed type prop at 6: Type Error: Type skeleton-group is not defined.
- `construction-obs-h` — E: failed type prop at 3: Unknown symbol: rigid-body-object
- `daxter` — E: failed type prop at 7: Unknown symbol: process-drawable
- `debug` — E: failed type prop at 98: Unknown symbol: *debug-lines-trk*
- `debug-sphere` — W: Return type mismatch function vs none.
- `default-menu` — E: failed type prop at 238: Unknown symbol: *debug-menu-context*
- `dma-disasm` — W: Return type mismatch function vs none.
- `drift` — E: failed type prop at 24: Unknown symbol: drift-editor
- `driver` — E: failed type prop at 4: Type Error: Type skeleton-group is not defined.
- `dynamic-mem` — E: failed type prop at 61: Unknown symbol: *mem-manager*
- `dynamic-patch` — W: Return type mismatch function vs none.
- `editable-h` — E: failed type prop at 22: Unknown symbol: editable-region
- `editable-player` — E: failed type prop at 17: Unknown symbol: editable-array
- `emerc-vu1` — E: Failed to guess label use for L1 in (top-level-login emerc-vu1):0
- `entity-more-perm` — E: failed type prop at 7: Unknown symbol: entity-more-perm
- `entity-table` — W: Return type mismatch function vs none.
- `etie-near-vu1` — E: failed type prop at 18: Unknown symbol: etn-matrix
- `etie-vu1` — E: failed type prop at 18: Unknown symbol: etie-matrix
- `explosion` — E: failed type prop at 2: Unknown symbol: explosion
- `eye` — E: Failed to guess label use for L129 in (top-level-login eye):0
- `eye-h` — E: failed type prop at 7: Unknown symbol: eye
- `fact-h` — E: failed type prop at 38: Unknown symbol: fact-info-enemy
- `find-nearest` — E: failed type prop at 7: Unknown symbol: search-info
- `find-nearest-h` — W: Return type mismatch int vs none.
- `fmv-player` — E: failed type prop at 36: Unknown symbol: fmv-work
- `fmv-player-h` — E: failed type prop at 29: Unknown symbol: fmv-player
- `font` — W: Return type mismatch (function string dma-buffer font-context none) vs none.
- `font-data` — E: Failed to guess label use for L2 in (top-level-login font-data):0
- `font-h` — W: Return type mismatch pointer vs none.
- `foreground` — E: Failed to guess label use for L217 in (top-level-login foreground):0
- `game-save` — E: failed type prop at 84: Unknown symbol: auto-save
- `generic-effect` — E: Failed to guess label use for L110 in (top-level-login generic-effect):1
- `generic-merc` — E: Failed to guess label use for L179 in (top-level-login generic-merc):0
- `generic-obs` — E: failed type prop at 8: Type Error: Type skeleton-group is not defined.
- `generic-obs-h` — E: failed type prop at 3: Unknown symbol: process-drawable
- `generic-tie` — W: Return type mismatch function vs none.
- `generic-vu0` — E: Failed to guess label use for L1 in (top-level-login generic-vu0):0
- `generic-vu1` — E: Failed to guess label use for L23 in (top-level-login generic-vu1):0
- `gun-util` — E: Failed to guess label use for L11 in (top-level-login gun-util):11
- `headset` — E: failed type prop at 32: Unknown symbol: *decoder-queue-3-buf*
- `headset-h` — E: failed type prop at 47: Unknown symbol: headset-decoder
- `history` — E: failed type prop at 11: Unknown symbol: history-elt
- `hostnames` — W: Return type mismatch (array ip-to-name-map) vs none.
- `hud` — E: failed type prop at 38: Unknown symbol: *hud-string-used-list*
- `hud-cash` — E: failed type prop at 84: Unknown symbol: in-game-hud
- `hud-classes` — E: failed type prop at 16: Unknown symbol: hud-map
- `hud-effects` — E: Decompiler type system did not know the type of symbol *last-play-time*. Add it!
- `hud-high-scores` — E: failed type prop at 40: Unknown symbol: in-game-hud
- `hud-results` — E: failed type prop at 196: Unknown symbol: in-game-hud
- `hud-results-grand-prix` — E: failed type prop at 8: Unknown symbol: in-game-hud
- `hud-widgets` — E: failed type prop at 150: Unknown symbol: hud-item-player-name
- `hud-widgets-2` — E: failed type prop at 86: Unknown symbol: in-game-hud
- `hud-widgets-3` — E: failed type prop at 32: Unknown symbol: in-game-hud
- `hud-widgets-4` — E: failed type prop at 6: Unknown symbol: in-game-hud
- `hud-widgets-powerhang` — E: failed type prop at 58: Unknown symbol: in-game-hud
- `in-game-menu-hud` — E: failed type prop at 90: Unknown symbol: in-game-hud
- `in-game-menu-hud2` — E: failed type prop at 6: Unknown symbol: in-game-hud
- `intro-part` — E: failed type prop at 6: Type Error: Type skeleton-group is not defined.
- `intro-scenes` — E: failed type prop at 4: Type Error: Type scene is not defined.
- `intro-scenes2` — E: failed type prop at 6: Type Error: Type skeleton-group is not defined.
- `intro-scenes3` — E: failed type prop at 4: Type Error: Type scene is not defined.
- `joint-exploder` — E: failed type prop at 83: Unknown symbol: process-drawable
- `joint-mod` — E: failed type prop at 24: Unknown symbol: joint-mod
- `keyboard` — E: failed type prop at 10: Type Error: Type skeleton-group is not defined.
- `level` — E: failed type prop at 440: Unknown symbol: *default-pris-texture-anim-array*
- `level-info` — E: failed type prop at 8: Unknown symbol: default-level
- `light-trails` — E: failed type prop at 1: Unknown symbol: light-trail
- `lightning` — E: Failed to guess label use for L94 in (top-level-login lightning):14
- `lightning-h` — W: Return type mismatch lightning-probe-vars vs none.
- `lightning-new` — E: failed type prop at 7: Unknown symbol: lightning-bolt
- `lights` — E: failed type prop at 24: Called a function, but we do not know its type
- `loader` — E: failed type prop at 137: Unknown symbol: spooler-block
- `lobby-dma` — W: Return type mismatch function vs none.
- `lobby-ghost` — E: failed type prop at 13: Unknown symbol: ghost-file
- `lobby-menu-manager-h` — E: failed type prop at 14: Unknown symbol: lobby-menu-manager
- `main` — E: failed type prop at 63: Unknown symbol: process-drawable
- `mem-buffer-h` — E: failed type prop at 251: Unknown symbol: *msg-buffers*
- `menu2-COMMON-GAME` — E: failed type prop at 7: Type Error: Type skeleton-group is not defined.
- `menu2-h` — E: failed type prop at 7: Unknown symbol: menu-string
- `menu2-lists` — E: failed type prop at 7: Unknown symbol: *menu-level-info-beta-array*
- `menu2-part` — E: failed type prop at 1: Unknown symbol: *part-group-id-table*
- `merc` — E: Failed to guess label use for L68 in (top-level-login merc):0
- `merc-blend-shape` — E: failed type prop at 30: Unknown symbol: blerc-dcache
- `merc-death` — E: failed type prop at 13: Unknown symbol: *part-id-table*
- `merc-vu1` — E: Failed to guess label use for L1 in (top-level-login merc-vu1):0
- `minimap` — E: failed type prop at 8: Unknown symbol: *minimap*
- `mood` — E: Decompiler type system did not know the type of symbol *flash0*. Add it!
- `mood-tables` — E: failed type prop at 71: Unknown symbol: *mood-control*
- `mood-tables2` — E: failed type prop at 11: Unknown symbol: *override-table*
- `movie-path` — E: Decompiler type system did not know the type of symbol *movie-path-dir*. Add it!
- `nav-control` — E: Failed to guess label use for L527 in (top-level-login nav-control):117
- `nav-graph-editor` — E: failed type prop at 20: Unknown symbol: nav-graph-command-array
- `nav-mesh` — E: failed type prop at 16: Unknown symbol: *default-nav-mesh*
- `nav-mesh-editor` — E: failed type prop at 5: Unknown symbol: nav-mesh-editable
- `nav-mesh-editor-h` — E: failed type prop at 23: Unknown symbol: int16-array
- `net-artifact` — E: failed type prop at 27: Unknown symbol: *msg-map-artifact*
- `net-aux-voice` — E: failed type prop at 7: Unknown symbol: aux-voice-mgr
- `net-boss-battle` — E: failed type prop at 27: Unknown symbol: in-game-hud
- `net-colarb` — E: failed type prop at 18: Unknown symbol: *net-aux-msg-handlers*
- `net-deathmatch` — E: failed type prop at 13: Unknown symbol: net-game-mgr-deathmatch
- `net-deathrace` — E: failed type prop at 1: Unknown symbol: net-game-mgr-deathrace
- `net-eco` — E: failed type prop at 107: Unknown symbol: eco
- `net-eco-h` — E: failed type prop at 14: Unknown symbol: process-drawable
- `net-eco-types` — E: failed type prop at 4: Type Error: Type skeleton-group is not defined.
- `net-enemy` — E: failed type prop at 5: Unknown symbol: net-enemy
- `net-enemy-h` — E: failed type prop at 7: Unknown symbol: net-enemy-transition
- `net-game-mgr` — E: failed type prop at 6: Unknown symbol: in-game-hud
- `net-game-mgr-h` — E: failed type prop at 7: Unknown symbol: net-game-mgr-vehicle-info
- `net-game-modes-h` — E: failed type prop at 18: Unknown symbol: deathmatch-spawner-array
- `net-game-modes2-h` — E: failed type prop at 30: Unknown symbol: *msg-map-net-player-ctf*
- `net-http` — E: failed type prop at 2: Unknown symbol: *http-downloader*
- `net-hud` — E: failed type prop at 5: Unknown symbol: hud
- `net-init` — E: failed type prop at 36: Unknown symbol: sce-stat
- `net-logging` — E: failed type prop at 34: Unknown symbol: *net-log-buf*
- `net-logging-h` — E: Failed to guess label use for L3 in (top-level-login net-logging-h):11
- `net-mgr` — E: failed type prop at 0: Unknown symbol: *net-keypair-valid*
- `net-mgr-async` — E: failed type prop at 7: Unknown symbol: medius-simple-response
- `net-mgr-chat` — E: failed type prop at 18: Unknown symbol: received-chat-msg
- `net-mgr-dme` — E: failed type prop at 43: Unknown symbol: fake-msg
- `net-mgr-h` — E: failed type prop at 75: Unknown symbol: net-available-game
- `net-mgr-medius` — E: failed type prop at 152: Unknown symbol: net-available-game
- `net-mgr-medius-buddies` — W: Return type mismatch function vs none.
- `net-mgr-medius-clans` — E: failed type prop at 21: Unknown symbol: *tmp-clan-members*
- `net-mgr-medius-clans-h` — E: failed type prop at 28: Unknown symbol: medius-cache-index-array
- `net-mgr-medius-games` — E: failed type prop at 40: Unknown symbol: medius-game-array
- `net-mgr-medius-games-h` — E: failed type prop at 13: Unknown symbol: *medius-game-status-cache*
- `net-mgr-medius-players` — W: Return type mismatch function vs none.
- `net-mgr-medius-players-h` — E: failed type prop at 24: Unknown symbol: *medius-player-cache*
- `net-mgr-medius-rooms` — E: failed type prop at 13: Unknown symbol: medius-room
- `net-mgr-mgcl` — E: Failed to guess label use for L322 in (top-level-login net-mgr-mgcl):0
- `net-mgr-muis` — E: failed type prop at 16: Unknown symbol: universe-choice
- `net-mgr-playback` — E: Failed to guess label use for L59 in (top-level-login net-mgr-playback):12
- `net-mgr-sysmsg` — E: Failed to guess label use for L9 in (top-level-login net-mgr-sysmsg):0
- `net-player` — W: Return type mismatch function vs none.
- `net-player-h` — E: failed type prop at 50: Called a function, but we do not know its type
- `net-powerup` — E: failed type prop at 109: Unknown symbol: powerup-draw
- `net-powerup-h` — E: failed type prop at 65: Unknown symbol: *msg-map-net-powerup*
- `net-process-mgr` — E: failed type prop at 1: Unknown symbol: net-process-mgr
- `net-process-mgr-h` — E: failed type prop at 18: Unknown symbol: net-process-mgr
- `net-projectile-h` — E: failed type prop at 3: Unknown symbol: projectile
- `net-race` — E: failed type prop at 19: Unknown symbol: net-game-mgr-race
- `net-race-h` — E: failed type prop at 27: Unknown symbol: *msg-map-net-player-race*
- `net-race-hud` — E: failed type prop at 79: Unknown symbol: *part-group-id-table*
- `net-rushhour` — E: failed type prop at 3: Unknown symbol: *part-id-table*
- `net-simple-destruct` — E: failed type prop at 15: Unknown symbol: net-simple-destruct
- `net-simple-destruct-h` — E: failed type prop at 3: Unknown symbol: process-focusable
- `net-start` — W: Return type mismatch function vs none.
- `net-time-trial-h` — E: failed type prop at 9: Unknown symbol: timetrial-snapshot
- `net-util` — E: failed type prop at 28: Unknown symbol: auto-test-levels
- `net-world` — E: Failed to guess label use for L943 in (top-level-login net-world):137
- `net-world-h` — E: failed type prop at 97: Unknown symbol: *msg-map-net-world*
- `ocean-h` — E: failed type prop at 40: Unknown symbol: ocean-spheres
- `ocean-mid` — E: failed type prop at 3: Unknown symbol: ocean
- `ocean-near` — E: failed type prop at 3: Unknown symbol: ocean
- `ocean-trans-tables` — E: Failed to guess label use for L19 in (top-level-login ocean-trans-tables):0
- `pad` — E: failed type prop at 31: Unknown symbol: cpad-info
- `part-tester` — E: failed type prop at 10: Unknown symbol: save-memcard
- `particle-curves` — E: failed type prop at 16: Unknown symbol: *part-id-table*
- `pilot-states` — W: Return type mismatch state vs none.
- `pov-camera` — E: failed type prop at 1: Unknown symbol: pov-camera
- `prim` — E: failed type prop at 10: Unknown symbol: prim-strip
- `process-drawable` — E: failed type prop at 30: Unknown symbol: draw-control
- `process-nettable` — E: failed type prop at 152: Unknown symbol: *msg-map-net-test*
- `profile` — E: Failed to guess label use for L3 in (top-level-login profile):0
- `race-manager` — E: failed type prop at 6: Unknown symbol: race-state
- `race-obs` — E: failed type prop at 3: Unknown symbol: process-drawable
- `ragdoll-h` — E: failed type prop at 7: Unknown symbol: ragdoll-edit-info
- `ragdoll-test` — E: failed type prop at 6: Type Error: Type skeleton-group is not defined.
- `ramdisk` — W: Return type mismatch int vs none.
- `rigid-body` — E: failed type prop at 9: Unknown symbol: debug-rigid-body-move
- `rigid-body-object` — E: failed type prop at 1: Unknown symbol: rigid-body-object
- `rigid-body-queue` — E: failed type prop at 92: Unknown symbol: rigid-body-queue-manager
- `rigid-body-surface` — E: Failed to guess label use for L1 in (top-level-login rigid-body-surface):0
- `rigid-body-surface-h` — E: failed type prop at 7: Unknown symbol: rigid-body-surface
- `ripple` — E: failed type prop at 18: Unknown symbol: ripple-globals
- `sampler` — E: failed type prop at 16: Unknown symbol: install-handler
- `scene` — E: failed type prop at 20: Unknown symbol: scene-player
- `scene-actor` — E: failed type prop at 6: Type Error: Type skeleton-group is not defined.
- `scert-funcs` — W: Return type mismatch int vs none.
- `script` — E: failed type prop at 42: Unknown symbol: *script-form*
- `shadow-vu1` — E: failed type prop at 7: Unknown symbol: shadow-vu1-constants
- `shrub-work` — E: failed type prop at 2: Unknown symbol: *instance-shrub-work*
- `shrubbery` — E: failed type prop at 127: Unknown symbol: dma-test
- `shrubbery-h` — E: failed type prop at 18: Unknown symbol: shrub-view-data
- `sky-data` — E: failed type prop at 13: Called a function, but we do not know its type
- `spartacus-editor` — E: failed type prop at 10: Unknown symbol: *spartacus-library*
- `sparticle` — E: failed type prop at 1: Unknown symbol: sparticle-cpuinfo
- `sparticle-h` — E: failed type prop at 9: Unknown symbol: sparticle-cpuinfo
- `sparticle-launcher` — E: failed type prop at 29: Unknown symbol: sparticle-launch-control
- `sparticle-launcher-h` — E: failed type prop at 7: Unknown symbol: sparticle-birthinfo
- `spatial-hash` — E: Decompiler type system did not know the type of symbol *grid-hash-work*. Add it!
- `sprite` — E: failed type prop at 7: Unknown symbol: sprite-header
- `sprite-distort` — E: failed type prop at 7: Unknown symbol: sprite-distorter-sine-tables
- `sprite-glow` — E: failed type prop at 18: Unknown symbol: sprite-glow-consts
- `statistics` — E: failed type prop at 65: Unknown symbol: *net-player-ladder-stats-info-array*
- `subdivide` — E: failed type prop at 62: Unknown symbol: terrain-context
- `subdivide-h` — E: failed type prop at 23: Unknown symbol: subdivide-dists
- `target` — W: Return type mismatch state vs none.
- `target-death` — W: Return type mismatch state vs none.
- `target-util` — E: failed type prop at 4: Type Error: Type skeleton-group is not defined.
- `task-scenes` — E: failed type prop at 6: Type Error: Type skeleton-group is not defined.
- `texture-anim` — E: Failed to guess label use for L201 in (top-level-login texture-anim):0
- `texture-anim-funcs` — E: Failed to guess label use for L26 in (top-level-login texture-anim-funcs):5
- `texture-anim-tables` — E: Failed to guess label use for L163 in (top-level-login texture-anim-tables):12
- `texture-h` — W: Return type mismatch int vs none.
- `tfrag` — E: failed type prop at 49: Unknown symbol: t-stat
- `tfrag-methods` — E: failed type prop at 33: Unknown symbol: drawable-tree-tfrag-trans
- `tfrag-near` — E: Failed to guess label use for L1 in (top-level-login tfrag-near):0
- `tfrag-work` — E: failed type prop at 5: Unknown symbol: *tfrag-work*
- `tie` — E: failed type prop at 62: Unknown symbol: tie-consts
- `tie-h` — E: failed type prop at 25: Unknown symbol: instance
- `tie-methods` — E: Decompiler type system did not know the type of symbol *tie*. Add it!
- `tie-near` — E: failed type prop at 7: Unknown symbol: tie-near-consts
- `tie-work` — E: failed type prop at 3: Unknown symbol: *instance-tie-work*
- `time-of-day` — E: failed type prop at 6: Unknown symbol: time-of-day-proc
- `time-of-day-h` — E: failed type prop at 18: Unknown symbol: palette-fade-controls
- `timer-h` — E: failed type prop at 24: Unknown symbol: timer-hold-bank
- `title-obs` — E: failed type prop at 7: Unknown symbol: title-control
- `traffic-h` — W: Return type mismatch int vs none.
- `trail-h` — E: failed type prop at 29: Unknown symbol: trail-blocker
- `udp-layer` — E: failed type prop at 18: Unknown symbol: udp-layer
- `vehicle` — E: failed type prop at 13: Unknown symbol: vehicle
- `vehicle-debris` — E: failed type prop at 16: Unknown symbol: rigid-body-object
- `vehicle-effects` — E: failed type prop at 1: Unknown symbol: vehicle
- `vehicle-h` — E: failed type prop at 224: Unknown symbol: vehicle-explosion-info
- `vehicle-manager` — E: failed type prop at 7: Unknown symbol: vehicle-manager
- `vehicle-net` — E: failed type prop at 34: Unknown symbol: vehicle
- `vehicle-util` — E: failed type prop at 67: Unknown symbol: rigid-body-vehicle-constants
- `viewer` — E: failed type prop at 5: Unknown symbol: process-drawable
- `visvol-edit` — E: failed type prop at 20: Unknown symbol: visvol-editor
- `water` — E: failed type prop at 10: Unknown symbol: *water-simple-alpha-curve-in*
- `water-part` — E: failed type prop at 1: Unknown symbol: *part-id-table*
- `wcar-projectiles` — E: failed type prop at 3: Unknown symbol: net-projectile
- `wcar-skel-template` — E: failed type prop at 4: Type Error: Type skeleton-group is not defined.
- `weather-part` — E: failed type prop at 1: Unknown symbol: *part-group-id-table*
- `wind-h` — E: failed type prop at 7: Unknown symbol: wind-vector
- `wind-work` — E: failed type prop at 5: Unknown symbol: *wind-work*
- `wvehicle` — E: failed type prop at 1: Unknown symbol: wvehicle
- `wvehicle-hud` — E: failed type prop at 1: Unknown symbol: *part-group-id-table*
- `wvehicle-hud-h` — E: failed type prop at 14: Unknown symbol: hud
- `wvehicle-weapons` — E: failed type prop at 1: Unknown symbol: vehicle-weapon-slot
- `wvehicle-weapons-aux` — E: failed type prop at 7: Unknown symbol: red-sentry-bot
- `wvehicle-weapons-data` — E: failed type prop at 34: Unknown symbol: *weapon-select-table-yellow-race-first*
- `wvehicle-weapons-h` — E: failed type prop at 27: Unknown symbol: process-drawable
- `wvehicle-weapons-part` — E: failed type prop at 527: Type Error: The method with id 10 of type object could not ...
- `wvehicle-weapons-proj` — E: failed type prop at 8: Unknown symbol: mine-a

## Appendix B: banned_objects (38 real entries + 1 junk)

### Still crash (hard abort): 8

- `race-line` — `CfgVtx.cpp:115` / `Assertion failed: 'x'`
- `collide-mesh` — `CfgVtx.cpp:115` / `Assertion failed: 'x'`
- `collide-shape` — `CfgVtx.cpp:115` / `Assertion failed: 'x'`
- `net-mgr-medius-cache` — `cfg_builder.cpp:32` / `Assertion failed: 'irb'`
- `editable` — `cfg_builder.cpp:32` / `Assertion failed: 'irb'`
- `entity` — `cfg_builder.cpp:1881` / `Assertion failed: 'op_as_expr'`
- `task-control` — `atomic_op_builder.cpp:1345` / `Assertion failed: 'i2.get_src(1).get_reg() == temp'`
- `water-anim` — `cfg_builder.cpp:724` / `Assertion failed: 'false'`

### No longer crash and decompile cleanly — remove from banned_objects: 24

- `hud-player-indicators`, `vehicle-antenna`, `vehicle-reticle`, `wcar`
- `wcar-base`, `wcar-falcon`, `wcar-mongoose`, `wcar-skel`
- `wcar-wombat`, `wvehicle-ai`, `wvehicle-effects`, `wvehicle-events`
- `wvehicle-net`, `wvehicle-part`, `wvehicle-physics`, `wvehicle-race`
- `wvehicle-sounds`, `wvehicle-states`, `wvehicle-util`, `wvehicle-weapons-oil`
- `wvehicle-weapons-util`, `wvehicle-weapons2`, `wvehicle-weapons3`, `wvehicle-wheel`

### No longer crash but still stub: 6

- `wcar-projectiles` — E: failed type prop at 3: Unknown symbol: net-projectile
- `wvehicle` — E: failed type prop at 1: Unknown symbol: wvehicle
- `wvehicle-weapons` — E: failed type prop at 1: Unknown symbol: vehicle-weapon-slot
- `wvehicle-weapons-aux` — E: failed type prop at 7: Unknown symbol: red-sentry-bot
- `wvehicle-weapons-part` — E: failed type prop at 527: Type Error: The method with id 10 of type object ...
- `wvehicle-weapons-proj` — E: failed type prop at 8: Unknown symbol: mine-a

### Junk entry (1)

- `banned_objects` — the literal string `"banned_objects"` as the first list element. Looks like a comment/label artifact. Not a real file name (decompiler errors `Expected to find 'banned_objects' in the ObjectFileDB`). Harmless.