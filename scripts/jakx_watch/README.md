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
- `.jakx_watch/run-TS.log`          — combined stdout+stderr of a run.sh invocation
- `log/decompiler.*.log`            — native decompiler logs (shared dir)

## What NOT to edit from this tool

`scripts/jakx_watch/*` is read-only on everything that sessions 1/2 own:
- `decompiler/config/jakx/all-types.gc`
- `decompiler/config/jakx/jakx_config.jsonc`
- `decompiler/config/jakx/potentially_useful/*.jsonc`
- decompiler C++ source

If measurements reveal a decompiler bug, report it — don't patch.
