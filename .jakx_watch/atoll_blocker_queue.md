# Atoll tutorial blocker queue
_last updated: 2026-04-24T01:25Z by PAIR3-B after boot-path audit_

## Active blockers (drain these first)

| priority | file | blocker type | status | assignee | notes |
|----------|------|--------------|--------|----------|-------|
| 1 | atoll.gd | atoll-obs.o excluded — no entity data in DGO → no race entities in BSP | TODO | PAIR3-B | Without entity records, reset-actors has nothing to spawn. atoll-obs.o must be decompiled and added to DGO |
| 2 | main.gc / display-loop | No entity-birth call in frame loop — even with entity data, actors never spawn | TODO | PAIR3-B | Need actors-update / entity-birth-update equivalent in while loop after initialize! |
| 3 | race-manager.gc | 3-line stub — race init never runs | DONE | PAIR3-A | end-lap(method-11), race-state-method-9, race-state-method-10 all decompile clean. race-h.gc updated to binary layout (racer-state+race-state). GAME.CGO builds. |
| 4 | race-control.gc | method-9 type_prop fail (l.wu + a1 28); output-race-mesh no type analysis | DONE @ a77f317f5 | PAIR1-B | method-9 decompiles clean (WARN only); output-race-mesh a0 typed as race-line (op52 remains for PAIR2-B) |
| 5 | vehicle-manager.gc | 3-line stub — vehicle spawning unimplemented | IN PROGRESS | PAIR1-A | claimed 01:35Z — auditing decomp output to identify type_prop blockers |
| 6 | driver.gc + driver-*.gc | 3-line stubs — no driver behavior | IN PROGRESS | PAIR2-A | claimed — auditing decomp output for driver.gc + driver-jak.gc type_prop blockers |
| 7 | draw pipeline / foreground-initialize-engines | Crashes when foreground-initialize-engines is called (bisect underway) | DONE @ 9716a6bfe | PAIR1-A | Bisect resolved: crash was update-time-of-day (calls clear-mood-times), not foreground-initialize-engines. Removed update-time-of-day from hook; full pipeline now stable |
| 8 | sky texture missing | atoll level-flags has no 'sky flag → sky GOAL code is no-op; C++ renderer uses random texture | IN PROGRESS | PAIR3-B | claimed — adding (level-flags sky display-wait ocean-near-translucent) to atoll level-info |
| 9 | ripple-globals size-assert | rc=134 type error blocking decomp (FIXED) | DONE @ this session | PAIR3-B | Added :pack-me to ripple-request + :inline to ripple-globals.requests |

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
