# Atoll tutorial blocker queue
_last updated: 2026-04-24T04:00Z by PAIR3-B — entity birth system stable_

## Active blockers (drain these first)

| priority | file | blocker type | status | assignee | notes |
|----------|------|--------------|--------|----------|-------|
| 1 | bsp-header birth | entity-links-array + birth!/kill! system | DONE | PAIR3-B | bsp-init-actors! (inlined add-to-level!) allocates entity-links-array for 185 BSP entities. entity.birth!, entity-actor.birth!, entity.kill!, entity-actor.kill!, entity-deactivate-handler, init-entity all ported to jakx-stubs-late.gc. actors-update guards on dead+bit-0. Game stable: no SEGFAULT, 185 entities processed (all etype=0 — pure data markers, expected; race entities spawn procedurally via race-control). |
| 2 | main.gc / display-loop | No entity-birth call in frame loop — actors-update wired but *spawn-actors* stayed #f | DONE | PAIR3-B | actors-update wired in drawable.gc. *spawn-actors* now defined #t in jakx-stubs-late.gc AND re-asserted each frame in drawable.gc (counters game-info's set-#f during initialize!-'play). Game stable w/ fresh build; no crash. |
| 3 | race-manager.gc | 3-line stub — race init never runs | DONE | PAIR3-A | end-lap(method-11), race-state-method-9, race-state-method-10 all decompile clean. race-h.gc updated to binary layout (racer-state+race-state). GAME.CGO builds. |
| 4 | race-control.gc | method-9 type_prop fail (l.wu + a1 28); output-race-mesh no type analysis | DONE @ a77f317f5 | PAIR1-B | method-9 decompiles clean (WARN only); output-race-mesh a0 typed as race-line (op52 remains for PAIR2-B) |
| 5 | vehicle-manager.gc | 3-line stub — vehicle spawning unimplemented | IN PROGRESS | PAIR1-A | claimed 01:35Z — auditing decomp output to identify type_prop blockers |
| 6 | driver.gc + driver-*.gc | 3-line stubs — no driver behavior | IN PROGRESS | PAIR2-A | **Audit findings 2026-04-24:** (1) `driver.vehicle uint8 8 :offset 276` blocks `l.d (+ X 276)` in method-3, driver-trans — change to `uint64` (but 276 is 4-byte not 8-byte aligned; GOAL may reject; test rc=134 first). (2) `info-pad uint8 24 :offset 252` blocks `l.b (+ s6 264)` in exit/enter-intro-driver — change to `info driver-info :inline :offset 252` to enable named field access at 264=driver-info.arm0-node (int8). (3) `driver-init-by-other` cast `[0, "s6", "driver"]` wrong op — s6 first READ at op 1 (`lwu a0, 52(s6)`), change to `[1, "s6", "driver"]`. (4) Many driver behavior functions need s6 typed as driver (driver-anim, driver-head, driver-trans, code-idle, code-intro): single-op cast at op 0 doesn't persist. Use range casts `[[0,N], "s6", "driver"]` — driver has NO type cycle so range casts are safe (gotcha #6 only blocks recursive types). (5) `driver-spawn` op 64: s5=none (return of type-from-driver-type which is `(function none)`); change define-extern to typed signature. (6) Inline byte-arrays (anim-vel/anim-pos at 300/316) block float loads — these are unaligned vectors, skip for now. (7) `turn-back-anim (int8 :offset 332)` — named field but still returns `<uninitialized>`; root cause still unknown. |
| 7 | draw pipeline / foreground-initialize-engines | Crashes when foreground-initialize-engines is called (bisect underway) | DONE @ 9716a6bfe | PAIR1-A | Bisect resolved: crash was update-time-of-day (calls clear-mood-times), not foreground-initialize-engines. Removed update-time-of-day from hook; full pipeline now stable |
| 8 | sky texture missing | atoll level-flags has no 'sky flag → sky GOAL code is no-op; C++ renderer uses random texture | BLOCKED | PAIR3-B | tested: adding (level-flags sky display-wait ocean-near-translucent) crashes at first frame after initialize! returned. Sky GOAL code path has null deref. Reverted. Needs investigation of sky init-path vs target nilness. |
| 9 | ripple-globals size-assert | rc=134 type error blocking decomp (FIXED) | DONE @ this session | PAIR3-B | Added :pack-me to ripple-request + :inline to ripple-globals.requests |
| 10 | nav-control OOM | decompiler exited rc=137 (OOM 20+GB RSS) on nav-control; blocked 233 downstream files | DONE @ 8db03ded2 | sibling session | Root cause: 0c2ee6182 expanded nav-control type_casts from single-op to RANGE casts. Range casts made multiple nav-control methods pass type_prop → form-builder then recurses exponentially on nav-control↔nav-state↔nav-mesh type cycle → OOM. Fix: revert range casts back to single-op. Decomp now runs rc=0 in 23s, emits 450 files. driver.gc (589) and vehicle-manager (at ~514) now decompile. My fb7b6e957 nav-control.mesh revert was unnecessary but harmless — the OOM was in form-building, not type loading. |

## Completed

- [x] ripple-globals / ripple-request — added :pack-me + :inline to fix size-assert rc=134
- [x] display-loop wires initialize! 'game "atoll-start" (title-obs.gc:130)
- [x] atoll geometry renders (tfrag, tie, shrub, water) via background pipeline
- [x] sky draw call wired in main-draw-hook (draw *sky-work* + flush-cache)
- [x] foreground-engine-execute wired in main-draw-hook
- [x] foreground-initialize-engines crash resolved — crash was update-time-of-day, not fwd-init-engines; full pipeline (fwd-init + sky + fwd-engine + background) stable @ 9716a6bfe

## Investigating (not yet confirmed blockers)

- atoll-obs.o — what entity types does it define? Need to check extracted raw object to understand race entity layout
- foreground-initialize-engines crash — RESOLVED. Real crash was update-time-of-day calling clear-mood-times (zeroes mood seeds) then weather vtable null-dispatch. foreground-initialize-engines is safe.
- entity birth system — jak3 uses actors-update *level* in real-main-draw-hook. Need to add to jakx frame loop once entity data is present.

## Deferred (out-of-scope for tutorial)

- vehicle customization (garage-tool-arm, wrench, antenna, etc.)
- championship / points progression
- unlocks / purchase-secrets
- netconfig / lobby / P2P code
- keyboard-control
- editable-* types
- advanced HUD (only race countdown + finish needed)
- gun weapons beyond basic defaults
- driver-ashelin, driver-gtblitz, driver-kaeden, driver-kiera, etc. (only driver-jak needed)
- atoll-ocean.o, atoll-effects.o, atoll-part.o (visual polish, not required for playability)

## Boot path summary (as of 2026-04-24)

```
play-boot
  → title-obs.gc startup state
    → FMVs play (THX, INTRO, INTROB)
    → atoll DGO loaded (geometry + textures only)
    → atoll BSP activated, connected to background-draw-engine
    → initialize! *game-info* 'game #f "atoll-start" #f
      → game-info.gc: sets continue to atoll-start, calls reset-actors 'game
      → reset-actors: kills no entities (none exist in BSP), sets birth-max=1000
      → returns
    → title-obs goes idle
  → display-loop keeps running, draws atoll geometry each frame
  ← STUCK HERE: no race entities, no vehicle, no race-control, no countdown
```

Key gap: atoll-obs.o not in DGO → BSP has no entity records → reset-actors is a no-op → nothing spawns.
