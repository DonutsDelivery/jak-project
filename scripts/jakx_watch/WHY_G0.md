# Why G0 Exists

## The critique

On 2026-04-26, water111 (OpenGOAL maintainer) flagged on Discord: rc (zero ERROR text markers in IR2) is a text-scan proxy, not a correctness measure. AI tooling can produce "signs of good progress" — moves rc, looks like compounding — without producing decompilation that actually works. The decompiler's output in jak1/2/3 is "very carefully checked in a way that ai tools are not good at today."

G0 is the project's structural response to this critique.

## The complete answer

Success is bytematch against the original PS2 binary, transitively verified via _REF.gc reference files. Coverage of the verifiable subset is a separate dial. Everything else — rc, goalc-compiles-without-throwing, applier candidate counts — is a leading indicator only.

The two primary metrics are:
- **verifiable_correctness_rate** = pass / test_scope. Of the files under measurement, what fraction match.
- **total_verified_coverage** = pass / emitted. Of all emitted files, what fraction are verified-correct.

Both must climb for the project to be done. A lane that improves correctness within coverage without expanding coverage is polishing the easy fraction. A lane that expands coverage but tanks correctness within it is bringing in files that don't compile. The split is permanent and not to be merged into a single headline.

## The informative vs. silencing distinction

"We configure the decompiler rather than patch its output" is a partial defense against the critique, not a complete one. The configuration system has two kinds of knobs:

**Informative knobs** (survive G0 cleanly):
- Real :offset deftype entries from observed offset clusters
- Real method signatures from cross-port positive evidence
- Type casts cleared by the drift filter (matching IR2 shape across games)
- Field layout corrections from substantive analysis (e.g., bef77ccce state@68 vs level@68)

**Silencing knobs** (G0 risk — Δrc-positive, Δpass-flat or worse):
- method-count-assert raises (canonical case: wvehicle sha 3b105e769c, +35 rc, untyped methods emitted)
- Plain-object wildcard signatures in sig_passthrough
- Type casts without positive evidence

Any new applier proposed must declare which category it falls into. Silencing-category appliers require explicit gating against Δpass before they are allowed to land batches.

## Decision rule

Δpass alone determines whether a lane is real. Δrc adds no information beyond what Δpass already provides. There is no scenario where a lane with Δpass=0 should be defended on the basis of Δrc movement. If pass cannot be measured (stale offline-test data), no lane-effectiveness claim is made that cycle.

## Epoch boundary

Pre-G0 work is in a different reference frame than post-G0 work. Per-applier yield attributions from before snapshot 2124aea66 are not retrocomputable against pass and remain provisional. Historical large-rc commits (>10 Δrc) get Δpass retrospectives when methodology permits; the wvehicle case is the canonical first re-evaluation.
