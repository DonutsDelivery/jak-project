# Atoll tutorial blocker queue
_last updated: 2026-04-24T01:25Z by PAIR3-B after boot-path audit_

## Active blockers (drain these first)

| priority | file | blocker type | status | assignee | notes |
|----------|------|--------------|--------|----------|-------|
| 1 | atoll.gd | atoll-obs.o excluded — no entity data in DGO → no race entities in BSP | TODO | PAIR3-B | Without entity records, reset-actors has nothing to spawn. atoll-obs.o must be decompiled and added to DGO |
| 2 | main.gc / display-loop | No entity-birth call in frame loop — even with entity data, actors never spawn | TODO | PAIR3-B | Need actors-update / entity-birth-update equivalent in while loop after initialize! |
| 3 | race-manager.gc | 3-line stub — race init never runs | IN PROGRESS | PAIR3-A | claimed 01:27Z — fixing racer-state-method-11 type_prop (l.wu + a2 28) via type_cast |
| 4 | race-control.gc | method-9 type_prop fail (l.wu + a1 28); output-race-mesh no type analysis | IN PROGRESS | PAIR1-B | claimed 01:32Z — fixing via all-types.gc method sigs for race-control/racer-state |
| 5 | vehicle-manager.gc | 3-line stub — vehicle spawning unimplemented | TODO | - | decomp out exists but status unknown |
| 6 | driver.gc + driver-*.gc | 3-line stubs — no driver behavior | TODO | - | 10+ files. Can defer non-Jak drivers for tutorial |
| 7 | draw pipeline / foreground-initialize-engines | Crashes when foreground-initialize-engines is called (bisect underway) | IN PROGRESS | PAIR3-B | Another agent bisecting; bisect1 game is stable with sky+background only |
| 8 | sky texture missing | atoll level-flags has no 'sky flag → sky GOAL code is no-op; C++ renderer uses random texture | TODO | PAIR3-B | Add (level-flags sky) to atoll level-info; verify texture page available |
| 9 | ripple-globals size-assert | rc=134 type error blocking decomp (FIXED) | DONE @ this session | PAIR3-B | Added :pack-me to ripple-request + :inline to ripple-globals.requests |

## Completed

- [x] ripple-globals / ripple-request — added :pack-me + :inline to fix size-assert rc=134
- [x] display-loop wires initialize! 'game "atoll-start" (title-obs.gc:130)
- [x] atoll geometry renders (tfrag, tie, shrub, water) via background pipeline
- [x] sky draw call wired in main-draw-hook (draw *sky-work* + flush-cache)
- [x] foreground-engine-execute wired in main-draw-hook

## Investigating (not yet confirmed blockers)

- atoll-obs.o — what entity types does it define? Need to check extracted raw object to understand race entity layout
- foreground-initialize-engines crash — bisect agent identified minimal-stable is sky+background; foreground-initialize-engines is suspect. Root cause: *shadow-globals* bucket access. May be null or wrong size.
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
