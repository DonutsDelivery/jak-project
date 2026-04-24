# jakx_watch tool / queue utilization matrix

_orchestrator snapshot · updated 2026-04-24 post-recovery cycle_

Lets sessions see at a glance which tools have active consumers and which queues are sitting idle. If your session ends up with spare context and no assignment, pick an IDLE queue with high-value rows.

## Legend

- **ACTIVE** — script runs every scanner cycle, output consumed by a session this week
- **RECENT** — consumed within last ~10 commits
- **IDLE** — output exists, rich content, no recent consumer
- **DORMANT** — output stale/empty/requires manual trigger, awaiting user decision
- **COMPLETE** — queue drained, no remaining work

## Appliers (apply fixes → auto-commit via apply_guard)

| Tool | Status | Notes |
|---|---|---|
| `return_mismatch_apply.py` | **ACTIVE** | Now uses apply_guard; 1 edit → -4160 errors cascade win (e39d46a3a); 718 patterns remain |
| `asm_func_apply.py` | **RECENT** | Extended with PS2-opcode veto (mtlo1/mula.s family); next batch needs apply_guard integration |
| `inspect_to_type_casts.py` | **RECENT** | Expanded offs=12 scanner (936c3736a, 200c4a316); offs=-4 batch complete |
| `migrate_green_files.py` | **ACTIVE** | 3f676ba9 built + uses; 173 files migrated across batches 1-3 |
| `size_assert_apply.py` | **PENDING** | Being authored by 2881c39d this cycle — unblocks 262 entries in size_assert_fixable.md |
| `split_store_fix.py` | **PENDING** | Being authored by ff51092d this cycle — targets 156 Failed-store errors |

## Detection / triage scanners

| Tool | Status | Output queue | Notes |
|---|---|---|---|
| `commit_impact_log.py` | **ACTIVE** | `history/commit_impact.md` + `winner_patterns.md` | 580-commit history; routes ROI prioritization |
| `near_clean_scan.py` | **IDLE → ACTIVE** | `near_clean_queue.md` (24 files, ≤1 err each) | Just dispatched 1844e6a1 to drain |
| `gotcha_miner.py` | **RECENT** | `gotchas_candidates.md` | 15 patterns mined; top promoted (#6, #8, #10, #19) |
| `offline_test_sweep.py` | **ACTIVE** | `offline_test_results.md` | 3f676ba9's primary tool; 88→100% pass rate |
| `block_comment_audit.py` | **COMPLETE** | `accidentally_swallowed.md` | 596fb14e resolved 87 DEAD / 19 UNCERTAIN |
| `return_mismatch_scan.py` | **ACTIVE** | `return_mismatch_queue.md` (254 lines) | Powers return_mismatch_apply; 718 patterns still queued |
| `size_assert_audit.py` | **IDLE** | `size_assert_fixable.md` (599 lines, **262 entries**) | **Biggest unused leverage.** Applier being built. |
| `clobber_scan.py` | **COMPLETE** | `clobber_queue.md` | 1844e6a1 drained 507 define-extern stubs in prior cycle |

## Cross-port scanners

| Tool | Status | Output | Notes |
|---|---|---|---|
| `label_types_copy_scan.py` | **IDLE** | `label_types_copy_queue.md` (**142 confirmed copy-ports from jak3**) | No active consumer. Haiku-shape work. Route next idle haiku. |
| `mips2c_candidate_scan.py` | **IDLE** | `mips2c_candidates.md` (1 real: draw-string-asm) | Detection works; gap-to-jak3 is 2 fns; low priority |
| `mips2c_candidates.py` | **IDLE** | `mips2c_queue.md` (0 actionable) | Correct behavior — no split-failed blockers reference jakx |
| `ref_drift_scan.py` | **IDLE** | `ref_drift_queue.md` (**11 real regressions + 1 stale_ref + 16 changed**) | `mood-tables2` -358 lines worst; most regressions are stale REFs — `seed_refs.py --force` clears them |
| `field_drift_scan.py` | **IDLE** | `field_drift_queue.md` (**1689 drifted types, top: process sub=610**) | Sonnet-shape work (high cascade potential). Not currently routed. |
| `cluster_impact.py` | **DORMANT** | `cluster_impact.md` (10 clusters, all net_sf=0) | Current run shows zero split-failed leverage from any cluster; re-run after big activation pushes |
| `discovery_queue.py` / `rank_discovery.py` | **DORMANT** | `discovery_queue.md` (empty until regen) | Requires `JAKX_WATCH_FORCE=1 bash scripts/jakx_watch/run.sh` to populate |
| `cpp_patch_queue.py` | **IDLE** | `cpp_patch_queue_candidates.md` (164 lines) | No active consumer |
| `static_data_scan.py` | **IDLE** | — | Output unclear; investigate or deprecate |
| `types_drift.py` | **IDLE** | — | Output unclear |
| `unknown_call_scan.py` | **IDLE** | — | Output unclear |
| `add_failed_scan.py` | **IDLE** | — | Output unclear |
| `amber_categorize.py` | **RECENT** | `amber_categorized.md` | 596fb14e consumed for batch-1 AMBER audit |
| `activation_blocker_scan.py` | **IDLE** | `activation_blocker_queue.md` | No active consumer |

## Queue-consumption routing guide (for idle sessions)

**Haikus** (mechanical wiring, no applier authoring):
1. `label_types_copy_queue.md` — copy 142 confirmed jak3→jakx entries (cheapest unblock)
2. `near_clean_queue.md` — fix 1 error per file → promote to real-clean (24 files)
3. Drain return_mismatch_queue via `return_mismatch_apply.py --top N --commit`
4. Drain size_assert_fixable via `size_assert_apply.py` (once 2881c39d ships)

**Sonnets** (applier authoring, deep analysis):
1. `field_drift_queue.md` row #1 (`process`, sub=610) — highest cascade in the project; needs careful :methods merge with parent inheritance check
2. `ref_drift_queue.md` regressions — most are stale REFs; `seed_refs.py --force` should reseed all 11 in one command (investigate first)
3. `split_store_fix.py` applier (ff51092d owns this cycle)
4. `size_assert_apply.py` applier (2881c39d owns this cycle)

**Decision tree when all above drained:**
- Biggest remaining bucket: `field_drift_queue.md` — 1689 drifted types across 5 complexity tiers
- Complexity ladder: clean-methods (862, easiest) → size-change (501) → multi (237) → methods-restructure (75)
- Start with clean-methods; only escalate when that tier empties

## Anti-patterns (what NOT to route)

Per winner_patterns.md + gotchas.md:
- 🔴 Bulk activation (>5 types/commit) — +9185 errors historical, banned
- 🔴 Recursive range-casts — +6160 errors, OOM risk, banned
- 🔴 Blind method return-type corrections — +7071 errors when inverted, must read body first
- 🔴 mips2c bulk-suppress without opcode vetting — c5f7ff573 post-mortem
