#!/usr/bin/env bash
# Drain loop for ir2_type_cast_extract.py.
#
# Each iteration runs a small batch via apply_guard. On PASS, the commit lands
# and the loop keeps going. On FAIL, the bad batch's (fn|op|reg) triples are
# harvested from the log and appended to the skip-file so next iterations
# avoid them.
#
# Stop conditions:
#  - no candidates left
#  - CONSECUTIVE_FAIL reached (default 3)
#  - MAX_ITER reached (default 30)
set -u

cd "$(dirname "$0")/../.."
ROOT="$PWD"

BATCH="${BATCH:-5}"
MAX_ITER="${MAX_ITER:-30}"
CONSEC_MAX="${CONSEC_MAX:-3}"
ERR_SLACK="${ERR_SLACK:-3}"
CAST_TARGET="${CAST_TARGET:-dst}"
SKIP_FILE="${SKIP_FILE:-/tmp/p2-ir2-skip.txt}"
LOG_DIR="${LOG_DIR:-/tmp}"

touch "$SKIP_FILE"

consec_fail=0
iter=0
while [ $iter -lt $MAX_ITER ] && [ $consec_fail -lt $CONSEC_MAX ]; do
    iter=$((iter + 1))
    LOG="$LOG_DIR/p2-ir2-drain-iter${iter}.log"
    echo "=== iter $iter (consec_fail=$consec_fail) — batch=$BATCH target=$CAST_TARGET ===" >&2
    python3 scripts/jakx_watch/ir2_type_cast_extract.py \
        --apply --commit \
        --batch-size "$BATCH" \
        --err-slack "$ERR_SLACK" \
        --cast-target "$CAST_TARGET" \
        --skip-file "$SKIP_FILE" \
        2>&1 | tee "$LOG"
    rc=$?

    if grep -q "Nothing to add" "$LOG"; then
        echo "[drain] no candidates left — done" >&2
        break
    fi

    if grep -q "PASS: " "$LOG"; then
        consec_fail=0
        # On pass, harvest the committed entries into the skip-file so we
        # don't re-propose them if they ship as no-ops.
        # (Dedup check uses existing_covers already — this is belt-and-suspenders.)
        python3 -c "
import re
log = open('$LOG').read()
# Parse 'Proposing N entries across M fns' and each '(fn):\n  [op, 'reg', 'type']'
import sys
current_fn = None
skip_new = []
for line in log.splitlines():
    m = re.match(r'^  (.+):$', line)
    if m and current_fn != m.group(1):
        current_fn = m.group(1)
        continue
    m2 = re.match(r\"^    \[(\d+), '(\w+)', '[^']+'\]\$\", line)
    if m2 and current_fn:
        op = m2.group(1); reg = m2.group(2)
        skip_new.append(f'{current_fn}|{op}|{reg}')
# Don't actually append — dedup logic handles this via existing_covers
"
    elif grep -q "FAIL: " "$LOG"; then
        consec_fail=$((consec_fail + 1))
        # Extract proposed entries from the failed batch — append to skip-file
        # so the next iteration picks different ones.
        python3 <<EOF
import re
log = open('$LOG').read()
current_fn = None
entries = []
for line in log.splitlines():
    m = re.match(r'^  (.+):$', line)
    if m:
        current_fn = m.group(1)
        continue
    m2 = re.match(r"^    \[(\d+), '(\w+)', '[^']+'\]$", line)
    if m2 and current_fn:
        op = m2.group(1); reg = m2.group(2)
        entries.append(f'{current_fn}|{op}|{reg}')

with open('$SKIP_FILE', 'a') as f:
    for e in entries:
        f.write(e + '\n')
print(f'[drain] appended {len(entries)} skip entries', file=__import__('sys').stderr)
EOF
    else
        echo "[drain] unknown outcome — log tail:" >&2
        tail -10 "$LOG" >&2
        consec_fail=$((consec_fail + 1))
    fi
done

echo "=== drain complete: $iter iterations, $consec_fail consecutive failures ===" >&2
