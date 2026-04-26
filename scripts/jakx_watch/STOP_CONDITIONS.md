# Compound-loop stop conditions + negative-results ledger

Last reviewed: 2026-04-26 (cycle 25)

## Why this file exists

Findings from prior cycles compress into headlines between sessions
("scoped decomp = 150× speedup," "tools unwired"); the qualifications get
lost ("...and three of four produced zero standalone signal"). Plans then
optimize for the headline. This doc keeps the qualifications co-located
with the gates so the next session inherits the plan, not the headline
of the plan.

The pattern that produced this file: two consecutive cycles where the
plan was right only after re-reading the prior cycle's negative results.
The mechanism is between-session compression. The mitigation is keeping
the disqualifications next to the queue.

## Gates (must be honored before proceeding)

### G1: After wiring tool N, smoke must beat baseline yield/hour

Before wiring tool N+1, run a 3-iter smoke with the currently-wired tools
and compare net Δrc per wall-clock hour against the single-tool baseline
(`cross_game_return_mismatch_apply --commit` standalone for same budget).

**If 2-tool loop yield/hour < single-tool baseline → STOP wiring, investigate.**
Don't wire tool N+2 just because tools are unwired. The matrix-solver
metaphor pulls toward completionism; the data should override.

Wiring queue (do NOT drain without G1 evidence at each step):
1. `return_mismatch_apply` — extends the lane that already pays off
2. SMOKE + G1 GATE
3. (only if G1 passes) the others, in order of standalone signal

### G2: cross_game_config_port runs at --max-batch=10 with --dry-run first

Even batch=10 has reverted recently: `99b6d95f5` → `de7d6b282`. The cycle
prompt's `--max-batch=50` is unsafe; the candidate pool needs
re-establishment before raising.

Required sequence:
1. `--dry-run` to inspect the candidate pool — does it look like the
   reverted 99b6d95f5 batch?
2. `--max-batch=10` maximum
3. Only consider raising after **3 consecutive non-reverted commits** at
   batch=10

### G3: Auto-revert of committed iterations is permanently deferred

Today's checkpoint compare is soft-veto (logs regression, no action). Do
**not** promote to `git reset --hard` on committed iterations. Soft-veto +
alert is the permanent state. Auto-revert with manual-confirm gating could
be revisited; pure auto-revert never.

The asymmetry: false-positive cost (losing real wins to a phantom
regression) >> false-negative cost (carrying a regression to next
checkpoint, where it's still detectable).

### G4: Blacklist expiry only if observed-needed

Don't add an expiry policy speculatively. Implement only if iteration logs
show pivots that genuinely should retry (= surrounding code changed enough
that the prior failure no longer applies). Until then, manual `python3
scripts/jakx_watch/blacklist.py remove ...` is the recovery path.

## Negative-results ledger

Tools with confirmed zero or negative standalone signal as of 2026-04-26.
Wiring these into the loop gives them faster decomp validation, **not**
better candidate quality. Decomp speed was not their bottleneck.

| Tool | Signal | Why |
|---|---|---|
| `sig_passthrough_apply` | net Δ=0/0 over 4 commits incl. 1 revert (`645fa14f3`) | Cascade-breaking `object` placeholders. Opus's bounded cross-port type-guesser may unblock; don't re-wire until a standalone batch shows positive yield |
| `ir2_type_cast_extract` | ~1 candidate / round | Saturated. Auto-pattern-loop reports `delta_rc=+0` repeatedly. Pool refresh might unstick but no current evidence |
| `cross_game_consensus` ≥2-game | net-negative | Lowering agreement threshold made it worse — false positives outweigh true positives at low corroboration |
| `ir2_store_cast_extract` | 0 candidates (2026-04-26 06:15) | Saturated. Same caveat as type_cast |

Tools with confirmed positive standalone signal:

| Tool | Signal | Notes |
|---|---|---|
| `cross_game_return_mismatch_apply` | net positive across multiple commits | The one that pays off. Already wired to compounding infrastructure |
| `return_mismatch_apply` (jakx) | shares plan-fixes logic with above | Plausibly extends same lane; first wiring target after Opus WIP commits |

## Useful baselines (for G1 comparison)

To establish single-tool baseline for G1, the canonical reference is:

```
time python3 scripts/jakx_watch/cross_game_return_mismatch_apply.py \
  --game jak3 --top 10 --commit
```

Record net Δrc and wall-clock seconds. The 2-tool loop must beat this
yield/hour to justify wiring tool 3.

## When this file becomes stale

After any of:
- A tool in the negative-results ledger produces a non-revert positive
  commit standalone (move it to the positive-signal table)
- A gate is intentionally relaxed (record the evidence in this doc, not
  just the cycle prompt)
- The smoke test from G1 produces evidence that changes the wiring order
