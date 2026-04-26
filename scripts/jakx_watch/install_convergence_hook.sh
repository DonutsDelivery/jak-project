#!/usr/bin/env bash
# Install a git post-commit hook that auto-appends a convergence_metric
# snapshot to .compound_loop/convergence.jsonl after every commit.
#
# Closes the gap that apply_guard's auto-snap leaves: manual commits that
# don't go through apply_guard (e.g. Sonnet's cascade-fix commits) wouldn't
# otherwise contribute trend data. With this hook installed, every commit
# — automated or manual — gets a row.
#
# Idempotent: re-running this script overwrites the hook with the current
# version. Hook is per-checkout (.git/hooks/post-commit), not tracked in
# git, so each contributor must run this once.
#
# Usage:
#   bash scripts/jakx_watch/install_convergence_hook.sh
#   # then: any git commit will auto-snap convergence

set -eu
cd "$(dirname "$0")/../.."
ROOT="$PWD"

HOOK_PATH="$ROOT/.git/hooks/post-commit"
SCRIPT_PATH="$ROOT/scripts/jakx_watch/convergence_metric.py"

if [ ! -d "$ROOT/.git" ]; then
    echo "ERROR: not a git repo (no .git/ at $ROOT)" >&2
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: convergence_metric.py not found at $SCRIPT_PATH" >&2
    exit 1
fi

mkdir -p "$ROOT/.git/hooks"

cat > "$HOOK_PATH" <<'EOF'
#!/usr/bin/env bash
# Auto-installed by scripts/jakx_watch/install_convergence_hook.sh
# Snapshots convergence_metric for jakx after each commit so manual fixes
# (not gated by apply_guard) still contribute trend data to
# .compound_loop/convergence.jsonl
#
# Runs in background to avoid slowing down commits. Failure is silent
# (no point blocking commits on metric unavailability).

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$ROOT" ]; then exit 0; fi

SCRIPT="$ROOT/scripts/jakx_watch/convergence_metric.py"
if [ ! -f "$SCRIPT" ]; then exit 0; fi

# Run for jakx only — sister games change less frequently, less signal
# per snapshot. Add jak2/jak3 here if you want denser cross-game trend.
(
    cd "$ROOT"
    python3 "$SCRIPT" --game jakx >/dev/null 2>&1 || true
) &

# Don't wait — let commit return immediately
disown $! 2>/dev/null || true
exit 0
EOF

chmod +x "$HOOK_PATH"
echo "[install] post-commit hook → $HOOK_PATH"
echo "[install] runs convergence_metric on jakx after every commit"
echo "[install] background-detached so commits don't slow down"
echo ""
echo "Test it:"
echo "  git commit --allow-empty -m 'test convergence hook'"
echo "  python3 scripts/jakx_watch/convergence_metric.py --game jakx --trend 5"
