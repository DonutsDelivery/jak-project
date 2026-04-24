# Winner & Loser Patterns — 580-Commit Impact Analysis

_source: scripts/jakx_watch/commit_impact_log.py · analyzed: 2026-04-24_

## Executive Summary

**35 ✅ winners**, **103 ❌ losers**, **426 neutral** commits analyzed. Top 3 patterns by total Δerr impact:

| Rank | Pattern | Verdict | Count | Total Δerr | Mean Δerr | Impact |
|------|---------|---------|-------|-----------|-----------|--------|
| 1 | OTHER (scripts, entity, FMV, tooling) | ✅ | 14 | -3665 | -262 | Highest ROI unclassified |
| 2 | :methods return-type fixes | ✅ | 5 | -3295 | -659 | **Highest per-commit impact** |
| 3 | mips2c porting | ✅ | 2 | -504 | -252 | Rare but effective |
| – | **LOSER: Reverts of bad activations** | ❌ | 12 | +9185 | +765 | Largest aggregate regression |
| – | **LOSER: Failed type_casts experiments** | ❌ | 4 | +6160 | +1540 | Highest per-commit regression |

---

## ✅ WINNERS (35 commits, error-reducing)

Sorted by total Δerr impact (most negative = best):

### 1. OTHER (unclassified) — **-3665 Δerr** (14 commits)

Includes: scripts/jakx_watch improvements, FMV player port, entity birth system, race-control fixes, tooling, offline-test bootstrap.

| Count | Mean Δerr | Top Commit |
|-------|-----------|-----------|
| 14 | -262 | `feat(jakx/entity): port entity birth/kill system — atoll sta` (-314) |

**Pattern insight:** High-leverage non-deftype work (porting features, fixing decomp tooling, wiring game systems) produces consistent error reduction. These aren't pattern-driven repetitive fixes; they're structural enables.

---

### 2. :methods RETURN-TYPE FIXES — **-3295 Δerr** (5 commits)

`subject` contains `:methods` or `method return` or `return type`.

| Count | Mean Δerr | Top Commits |
|-------|-----------|-----------|
| 5 | -659 | `jakx all-types: fix mysql-nav-graph + vehicle method return` (-1330) |
| | | `jakx decomp: :methods sweep (none→int ×79, none→symbol ×48)` (-495) |
| | | `decompiler/jakx/all-types: more :methods sweep + revert inst` (-490) |

**Pattern insight:** Fixing `:methods` return-type declarations (correcting declared vs actual return types in deftype blocks) is the **highest-ROI pattern per commit** (-659 mean). Bulk method return-type corrections yield -1330+ error drops.

---

### 3. mips2c PORTING — **-504 Δerr** (2 commits)

Hand-porting MIPS→C++ functions for asm-heavy code.

| Count | Mean Δerr | Top Commits |
|-------|-----------|-----------|
| 2 | -252 | `game/mips2c/jakx: port sparticle-motion-blur-dirt (target ca` (-490) |
| | | `mips2c: port (method 10 font-context) for jakx hvdf/calc-mat` (-14) |

**Pattern insight:** Each mips2c port unblocks a specific function's full decompilation. High per-commit impact (-252 mean). Only 2 winners in this category suggests mips2c selections are careful (not bulk).

---

### 4. ACTIVATION (deftype uncomments) — **-213 Δerr** (6 commits)

Activating block-commented deftypes or parent-first clusters.

| Count | Mean Δerr | Top Commits |
|-------|-----------|-----------|
| 6 | -36 | `decompiler/jakx: activate potentially_useful configs into nt` (-893) |
| | | `jakx all-types: activate lightning-tracker` (-42) |
| | | `jakx all-types: activate nav-mesh-editable + nav-mesh-editor` (-34) |

**Pattern insight:** Activation work has **high variance** (-893 down to -34). Strategic cluster activations (like `potentially_useful`) yield large drops. Single-type activations are marginal.

---

### 5. type_casts CONFIG WORK — **+558 Δerr** (3 commits)

NOTE: Positive Δerr but still marked ✅; likely due to `Δreal_clean ≥ 0` (no regression in clean files).

| Count | Mean Δerr | Commits |
|-------|-----------|---------|
| 3 | +186 | `fix: restore curve :inline at offset 20, add font-context ty` (-29) |
| | | `fix(jakx/type_casts): race-control method-9 a1 cast pointer→` (-19 & +606 duplicates?) |

**Pattern insight:** Three type_casts commits in winners; one reduced errors (-29), others had mixed impact. Small sample size; not a reliable pattern yet.

---

### 6. C++ DECOMPILER PATCHES — **+3 Δerr** (2 commits)

Generic decompiler fixes (strip trailing ret-none, bounding-box methods).

| Count | Mean Δerr | Commits |
|-------|-----------|---------|
| 2 | +1.5 | `decompiler: strip trailing (ret-none)…` (+0) |
| | | `decompiler/jakx/all-types: bounding-box…` (+3) |

**Pattern insight:** Minimal impact; small tactical fixes that don't move the needle much.

---

### 7. REVERTS (single win) — **-13 Δerr** (1 commit)

| Count | Mean Δerr | Commit |
|-------|-----------|--------|
| 1 | -13 | `jakx all-types: revert vehicle-reticle-base` |

**Pattern insight:** Rare — reverting a bad change that helped. Most reverts are losers.

---

## ❌ LOSERS (103 commits, error-increasing)

### 1. REVERTS OF ACTIVATION ATTEMPTS — **+9185 Δerr** (12 commits)

Commits that revert prior activation or bulk-fix attempts when they introduced more errors than they solved.

| Count | Mean Δerr | Worst Commits |
|-------|-----------|-----------|
| 12 | +765 | `Revert "jakx label_types: merge 179 confirmed jak3 copy-port` (+5717) |
| | | `fix(jakx/all-types): revert touching-list to correct method-` (+5254) |
| | | `jakx all-types: revert sky-work (vector4w N :inline crashes` (+4903) |

**Root causes:**
- Label_types bulk copy-port matched on name only, not type → applied wrong hints
- Touching-list :methods batch had method-count assertion mismatch
- Sky-work vector4w inline struct caused crash

**Pattern insight:** Bulk activations without per-item validation → high revert cost. **This is the biggest loser category** (+765 mean). Activations need sampling + validation before committing.

---

### 2. type_casts EXPERIMENTS (mostly reverted) — **+6160 Δerr** (4 commits)

Range casts and experiments that backfired.

| Count | Mean Δerr | Worst Commits |
|-------|-----------|-----------|
| 4 | +1540 | `fix(jakx/type_casts): revert nav-control range casts` (±6762) |
| | | `fix(jakx/type_casts): revert nav-control range casts` (±5561) |

**Root cause:** Nav-control range casts enabled type_prop to walk recursive type cycle (nav-control ↔ nav-state ↔ nav-mesh) → exponential form-builder recursion → OOM. Reverted to single-op casts.

**Pattern insight:** Range casts on recursive types are dangerous. **Per-commit regression is highest in this category** (+1540 mean). Validate type cycle before range-casting.

---

### 3. :methods RETURN-TYPE MISMATCHES (batch fixes) — **+2948 Δerr** (6 commits)

Bulk `:methods` return-type corrections that overcorrected or applied to wrong types.

| Count | Mean Δerr | Worst Commits |
|-------|-----------|-----------|
| 6 | +491 | `fix(jakx/all-types): fix 58 return type mismatches from retu` (+7071) |
| | | `jakx all-types: fix mysql-nav-graph + vehicle method return` (+1425) |

**Root cause:** Session 16 applied inverted return-type corrections (int→none when should be none→int, or vice versa). Manual fixes looked correct but were applied backwards.

**Pattern insight:** Return-type corrections are **highest-risk even when they win** (winners are -3295, but 6 losers added +2948 back). Needs peer review or automated validation.

---

### 4. ACTIVATION ATTEMPTS (mostly bulk) — **+75 Δerr** (46 commits)

Large cluster of activation attempts that increased errors (but usually small per-commit).

| Count | Mean Δerr | Worst Commits |
|-------|-----------|-----------|
| 46 | +2 (!) | `jakx all-types: fix mysql-nav-graph alignment + activate col` (+5366) |
| | | `jakx all-types: activate artifact-location-array + hud-sprit` (+5192) |

**Pattern insight:** Single-type or small-cluster activations have **near-zero aggregate impact** (+2 mean). Bulk activations w/o ordering/validation blow up (worst ones +5000+). The 46-commit group mostly neutral/slightly negative—lots of unproductive churn.

---

### 5. C++ DECOMPILER PATCHES (missed root causes) — **+490 Δerr** (5 commits)

Decompiler changes that introduced new malformed emissions or broke edge cases.

| Count | Mean Δerr | Worst Commits |
|-------|-----------|-----------|
| 5 | +98 | `decompiler: lazy-decompile static data on form emit` (+5396) |
| | | `decompiler: emit #f for failed static-data + lambda decomp` (+4465) |

**Root cause:** Lazy decompilation and #f placeholders introduced new "function was not converted" errors and stack-slot type mismatches downstream.

**Pattern insight:** Decompiler-level changes have **high blast radius**. Fixes to form emission or static-data handling can cascade into hundreds of new errors if not validated end-to-end.

---

## SUMMARY TABLE: HIGH-ROI vs HIGH-RISK PATTERNS

| Pattern | Verdict | Avg Δerr | Risk Level | Recommendation |
|---------|---------|----------|-----------|----------------|
| **:methods return-type fixes** | ✅ | -659 | 🔴 HIGH | High ROI but needs per-method validation; avoid batch-without-review |
| **mips2c porting** | ✅ | -252 | 🟢 LOW | Rare opportunities, always effective; pursue when caller is split-failed |
| **Feature/system ports** (other) | ✅ | -262 | 🟢 LOW | Entity birth, FMV, race-control; structural enables with side benefits |
| **Strategic clusters** (activation) | ✅ | -36 | 🟡 MED | High variance; `potentially_useful` batch >= 10-type enables; single types marginal |
| **Revert bad activations** | ❌ | +765 | 🔴 CRITICAL | Don't attempt bulk activation without sampling validation first |
| **Recursive type range-casts** | ❌ | +1540 | 🔴 CRITICAL | NEVER use range casts on nav-control, net-*, vehicle cycles; crashes decomp |
| **Blind :methods corrections** | ❌ | +491 | 🔴 CRITICAL | Validate each method-fix against actual bytecode before batch-applying |

---

## NEXT-CYCLE TASK ROUTING

**For max Δerr reduction, prioritize in this order:**

1. **:methods return-type sweeps** (if can validate each one) → -659/commit potential
2. **Identify + port mips2c candidates** → -252/commit, higher reliability than activation
3. **Feature ports** (FMV, entity, race systems) → -262/commit, structural benefits
4. **Strategic cluster activation** (10+ types at once, with forward-ref resolution) → -36/commit but high volume
5. **AVOID:** Bulk activation without per-item sampling; range casts on recursive types; blind batch :methods corrections

**Commit templates that WIN:**
- `fix(jakx/all-types): :methods sweep (type-A method-N X→Y ×K, …)`
- `feat(jakx): port <system> — …` (structural feature ports)
- `game/mips2c: port <function> (caller split-failed)`
- `fix(jakx/all-types): activate <cluster> (parent-first chain)`

**Commit templates that LOSE:**
- `jakx all-types: bulk activate 50+ types` (without validation)
- `fix(jakx/type_casts): add range cast <recursive-type>` (nav-control, net-*, vehicle)
- `jakx all-types: fix <N> method return types` (without per-method review)
