# jakx_watch — decomp regression / impact lane

Feedback loop for the two sessions editing `decompiler/config/jakx/*` to fix
Jak X decompilation. Runs a clean decomp into a private output dir, classifies
each file, diffs against the previous snapshot, and reports which config
levers would unblock the most files.

## What it measures

Per decomp run it tells you:

- **bucket counts** — how many files ended up in each health bucket:
  - `real-clean`    — decompiled, no ERROR/stub markers
  - `real-partial`  — decompiled, but has some errors/warns
  - `split-failed`  — 0 defuns/defmethods; top-level splitting never ran
                      (classic `types_succeeded=false` symptom)
  - `static-only`   — legitimately code-free (headers/data-only files)
- **totals**: defun, defmethod, `;; failed to figure out` stub markers,
  inline `;; ERROR` / `;; WARN` markers
- **log signals** from the decompiler:
  - top unknown symbols (fix these in `all-types.gc` — biggest unblock)
  - unknown types that FATAL-crashed the run (fixing one uncrashes decomp)
  - last-processed index / files blocked by crash
- **deltas** vs previous snapshot with matching output-dir
- **category transitions** per file (who regressed / who got better)
- **top 10 offender files** by (failed+error) density

## Files

- `measure.py` — scans `decompiler_out/jakx/` or a `--decomp-out` path,
  writes a snapshot into `.jakx_watch/history/snap-TS.json`, also updates
  `.jakx_watch/status.md` with the formatted summary.
- `run.sh` — wipes a private output dir, runs the decompiler against current
  config, then invokes `measure.py`. Short-circuits if config hash hasn't
  changed since last run (override with `JAKX_WATCH_FORCE=1`).
- `types_drift.py` — diffs `new-all-types.gc` (generate_all_types regen) vs
  current `all-types.gc`. Surfaces activation / discovery / field-drift sets.
- `rank_discovery.py` — scores activation candidates by (parent_ok, jak3
  similarity, reference count, dependency depth, tier) and writes
  `.jakx_watch/activation_queue.md` (top 30 priority list).
- `emit_stub.py` — extracts a `(deftype NAME ...)` body from jak3 / jak2 /
  regen for a requested type, paste-ready for all-types.gc. `--top N`
  batch-emits the ranked queue; `--min` emits a skeleton-only stub.
- `seed_refs.py` — auto-dumps `_REF.gc` files for real-clean jakx outputs
  that don't yet have coverage (uses `offline-test --dump_current_output`).
- `offline_test_pass.py` — runs the offline-test over the real-clean bucket,
  splits into green (passes) / amber (compile or REF-mismatch fails). Has a
  pre-flight to surface setup blockers (type errors in all-types.gc etc.).
- `static_data_scan.py` — counts `(define *X* <static-data LN>)` occurrences
  across decomp output. This pattern fails goalc compilation (arg mismatch)
  and is a high-priority C++ decompiler patch target.
- `unknown_call_scan.py` — clusters `;; ERROR: ... Called a function, but we do
  not know its type` by parent type / method. A type with many clustered errors
  indicates its `:methods` block in all-types.gc needs better signatures so
  type-prop can resolve jr-t9 callees.
- `load_offset_scan.py` — clusters `;; ERROR: ... Could not figure out load:
  (set! DST (OP (+ REG OFFS)))` by offset + caller. Surfaces struct-field
  offsets that aren't resolving (type_casts.jsonc candidates) and global
  (gp+OFFS) references that are missing from the symbol table.
- `add_failed_scan.py` — clusters `;; ERROR: ... add failed: LHS <integer N>`
  into two buckets: `<uninitialized>` (method arg signatures missing in
  all-types.gc) and typed LHS (deftype field missing or type_casts entry
  needed).
- `return_mismatch_scan.py` — clusters `;; WARN: Return type mismatch
  DECLARED vs ACTUAL` by pattern and by parent type. Each mismatch is a
  stance disagreement between an `:methods` entry in all-types.gc and the
  decompiled body — fixable by editing the declaration (most common) or the
  body. Top clusters surface types whose `:methods` block can be
  batch-corrected in one edit.
- `discovery_queue.py` — ranked top-20 PURE-DISCOVERY deftypes (types emitted
  by regen's new-all-types.gc but absent from jakx in any form — neither
  active, line-commented, nor block-commented). Per-entry: parent status,
  dependent-count weighted toward failing files, copy-port complexity (clean
  copy vs minor/major surgery), parent-first prerequisites. Writes
  `.jakx_watch/discovery_queue.md`.
- `mips2c_candidates.py` — writes `.jakx_watch/mips2c_queue.md` with a
  ranked per-function port list (jak3 fn → missing in jakx_functions/). Shows
  block count (porting complexity proxy), whether any split-failed caller
  depends on the function, and caller-file detail for the top-3.
- `cpp_patch_queue.py` — cross-file pattern clustering for C++ decompiler-emitter
  bugs. Probes ~12 known malformed emissions (static-data variants, escaped
  `<uninitialized>` tokens, leaked raw asm ops, empty defmethod arg lists,
  etc.) and ranks by `count × severity`. Writes `.jakx_watch/cpp_patch_queue.md`
  — each row is a **single emitter patch** that, once fixed, clears the whole
  cluster.
- `type_ref_finder.py` — triage helper. `--auto` scrapes the FAILED
  status.md banner for the unknown type, then finds every reference
  (LIVE vs commented) in jakx all-types.gc, decomp output, and checks
  jak3/jak2 for a copy-port source. Auto-invoked from run.sh when decomp
  fatal-crashes so agents 1/2 land on triage info, not just a log tail.
- `field_drift_scan.py` — ranks the 933 deftypes active in both current
  `all-types.gc` and the decompiler regen but with differing bodies. Classifies
  each as `clean-methods` (return/arg types only — lowest effort), `size-change`
  (layout changed), `multi`, or `methods-restructure`. Scores by
  `4·failing_refs + all_refs − complexity_penalty`. Writes
  `.jakx_watch/field_drift_queue.md`; the `clean-methods` sub-list is the
  batch return-type-sweep queue for Agent 1.
- `cluster_impact.py` — groups the 1126 commented deftypes into activation clusters
  (one cluster per active root type). Ranks by `f_refs / depth` — files potentially
  unblocked per unit of parent-first ordering work. Top clusters for Agent 2:
  `driver` (r/cost=23), `process` (r/cost=22), `wcar-base` (r/cost=18).
  Writes `.jakx_watch/cluster_impact.md`.
- `migration_candidates.py` — audits `goal_src/jakx/engine/**/*.gc` hand-ports
  against current decomp state. A hand-port is a deletion candidate when its
  decomp is real-clean / real-partial. Flags update-from-decomp append-bug
  risk (hand-port defines named methods whose jakx all-types.gc deftype
  doesn't declare them). Writes `.jakx_watch/migration_candidates.md`.

## Usage

```bash
# One cycle: run decomp, measure, emit summary + snapshot.
bash scripts/jakx_watch/run.sh

# Measure only (reuses existing .jakx_watch/decomp_out/jakx).
python3 scripts/jakx_watch/measure.py --decomp-out .jakx_watch/decomp_out/jakx

# Diff two arbitrary snapshots.
python3 scripts/jakx_watch/measure.py \
    --decomp-out .jakx_watch/decomp_out/jakx \
    --compare .jakx_watch/history/snap-20260417T203416-845479809a.json \
    --no-write
```

## Output locations

- `.jakx_watch/decomp_out/jakx/`  — private decompiler output (gitignored)
- `.jakx_watch/history/snap-*.json` — per-run snapshots (gitignored)
- `.jakx_watch/history/latest.json` — most recent snapshot
- `.jakx_watch/status.md`           — human-readable latest summary
- `.jakx_watch/activation_queue.md` — ranked queue of activation candidates
- `.jakx_watch/field_drift_queue.md`     — ranked field-drift deftype update queue
- `.jakx_watch/migration_candidates.md` — ranked hand-ports ready for deletion
- `.jakx_watch/discovery_queue.md`       — ranked pure-discovery deftype queue
- `.jakx_watch/mips2c_queue.md`          — ranked jak3→jakx port queue
- `.jakx_watch/cpp_patch_queue.md`       — ranked C++ decompiler-emitter patches
- `.jakx_watch/cluster_impact.md`        — commented-deftype clusters ranked by unblock/cost
- `.jakx_watch/run-TS.log`          — combined stdout+stderr of a run.sh invocation
- `log/decompiler.*.log`            — native decompiler logs (shared dir)
- `test/decompiler/reference/jakx/` — `_REF.gc` baseline corpus (checked in)

## What NOT to edit from this tool

`scripts/jakx_watch/*` is read-only on everything that sessions 1/2 own:
- `decompiler/config/jakx/all-types.gc`
- `decompiler/config/jakx/jakx_config.jsonc`
- `decompiler/config/jakx/potentially_useful/*.jsonc`
- decompiler C++ source

If measurements reveal a decompiler bug, report it — don't patch.
