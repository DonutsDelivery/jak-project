#!/usr/bin/env bash
# Run a clean jakx decomp into a private output dir, then measure it.
#
# We use a private OUT_DIR so we don't stomp on decompiler_out/jakx/ while
# sessions 1/2 may be running their own iterations there.
#
# Exit codes:
#   0 = decomp finished (possibly with errors) and measurement succeeded
#   1 = decomp was unable to load types (fatal, config broken)
#   2 = measurement crashed

set -u
cd "$(dirname "$0")/../.."
ROOT="$PWD"

OUT_DIR="${JAKX_WATCH_OUT_DIR:-$ROOT/.jakx_watch/decomp_out}"
LOG_DIR="$ROOT/log"
BIN="$ROOT/build/Release/decompiler/decompiler"
CFG="$ROOT/decompiler/config/jakx/jakx_config.jsonc"
ISO="$ROOT/iso_data"

mkdir -p "$OUT_DIR" "$ROOT/.jakx_watch"

if [ ! -x "$BIN" ]; then
    echo "ERROR: decompiler binary missing: $BIN" >&2
    echo "Build it first:  cmake --build build/Release --target decompiler -j" >&2
    exit 1
fi

TS="$(date +%Y%m%dT%H%M%S)"
RUN_LOG="$ROOT/.jakx_watch/run-$TS.log"

echo "== jakx_watch: decomp run $TS ==" | tee "$RUN_LOG"
echo "config: $CFG" | tee -a "$RUN_LOG"
echo "iso:    $ISO" | tee -a "$RUN_LOG"
echo "out:    $OUT_DIR" | tee -a "$RUN_LOG"

START=$(date +%s)

# Hash the config inputs so we can detect "no change since last run".
CFG_HASH_FILE="$ROOT/.jakx_watch/last_config_hash"
NEW_HASH=$({
    find "$ROOT/decompiler/config/jakx" -type f \( -name '*.gc' -o -name '*.jsonc' \) -print0 \
      | sort -z \
      | xargs -0 sha1sum
} 2>/dev/null | sha1sum | awk '{print $1}')

FORCE="${JAKX_WATCH_FORCE:-0}"
if [ "$FORCE" != "1" ] && [ -f "$CFG_HASH_FILE" ]; then
    OLD_HASH=$(cat "$CFG_HASH_FILE" 2>/dev/null || echo "")
    if [ "$OLD_HASH" = "$NEW_HASH" ]; then
        echo "config unchanged since last run (hash=$NEW_HASH); skipping decomp." \
          | tee -a "$RUN_LOG"
        python3 scripts/jakx_watch/measure.py
        exit 0
    fi
fi

# Wipe output so stale files from earlier (maybe-deeper) runs don't pollute
# the measurement. Our out dir lives entirely under .jakx_watch/, so this is
# safe — it's never where sessions 1/2 write.
if [ -d "$OUT_DIR/jakx" ]; then
    rm -rf "$OUT_DIR/jakx"
    echo "wiped previous $OUT_DIR/jakx" | tee -a "$RUN_LOG"
fi

# Run decomp. The decompiler appends its own timestamped log in $LOG_DIR;
# we mirror stdout/stderr to our run log so we have a stable handle.
echo "-- running decompiler --" | tee -a "$RUN_LOG"
set +e
"$BIN" "$CFG" "$ISO" "$OUT_DIR" \
    --version ntsc_v1 \
    --config-override '{"decompile_code": true, "levels_extract": false, "allowed_objects": [], "generate_all_types": true}' \
    >>"$RUN_LOG" 2>&1
RC=$?
set -e

END=$(date +%s)
ELAPSED=$((END - START))
echo "-- decompiler exited rc=$RC (elapsed ${ELAPSED}s) --" | tee -a "$RUN_LOG"

# Pick up the freshest decompiler log it wrote (to feed into measure).
DECOMP_LOG=$(ls -t "$LOG_DIR"/decompiler.*.log 2>/dev/null | head -1)

# Success-ish: if we emitted any _disasm.gc files, measurement is meaningful.
N_OUT=$(find "$OUT_DIR/jakx" -maxdepth 1 -name '*_disasm.gc' 2>/dev/null | wc -l)
echo "emitted $N_OUT _disasm.gc files" | tee -a "$RUN_LOG"

if [ "$N_OUT" = "0" ]; then
    echo "NO output files emitted — types likely failed to load." | tee -a "$RUN_LOG"
    # Write an error banner into status.md so other sessions don't fly blind.
    STATUS="$ROOT/.jakx_watch/status.md"
    mkdir -p "$(dirname "$STATUS")"
    {
        echo '```'
        echo "# jakx_watch status — FAILED"
        echo "last updated @ git $(git rev-parse HEAD 2>/dev/null | head -c 12)  ·  ts $(date -Iseconds)"
        echo ""
        echo "## ERROR: decomp emitted zero files"
        echo ""
        echo "Decompiler couldn't load types — likely a broken deftype in all-types.gc."
        echo "Tail of run log ($RUN_LOG):"
        echo ""
        tail -20 "$RUN_LOG" 2>/dev/null
        echo '```'
    } > "$STATUS"
    exit 1
fi

# Remember the config hash we decompiled against.
echo "$NEW_HASH" > "$CFG_HASH_FILE"

echo "-- measuring --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/measure.py \
    --decomp-out "$OUT_DIR/jakx" \
    --log "$DECOMP_LOG" 2>&1 | tee -a "$RUN_LOG"

# --- types drift (generate_all_types regression detection) ---
NEW_TYPES="$OUT_DIR/jakx/new-all-types.gc"
if [ -f "$NEW_TYPES" ]; then
    echo "" | tee -a "$RUN_LOG"
    echo "-- types drift --" | tee -a "$RUN_LOG"
    python3 scripts/jakx_watch/types_drift.py \
        --current "$ROOT/decompiler/config/jakx/all-types.gc" \
        --regen   "$NEW_TYPES" 2>&1 | tee -a "$RUN_LOG"

    echo "" | tee -a "$RUN_LOG"
    echo "-- rank activation candidates --" | tee -a "$RUN_LOG"
    python3 scripts/jakx_watch/rank_discovery.py 2>&1 | tee -a "$RUN_LOG"
fi

# --- static-data decomp bug scanner ---
echo "" | tee -a "$RUN_LOG"
echo "-- static-data decomp bug scan --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/static_data_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- migration candidates (hand-port debt deletion audit) ---
echo "" | tee -a "$RUN_LOG"
echo "-- migration candidates audit --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/migration_candidates.py 2>&1 | tee -a "$RUN_LOG" || true

# --- unknown-call clustering (which types have methods w/ unknown callees) ---
echo "" | tee -a "$RUN_LOG"
echo "-- unknown-call clustering --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/unknown_call_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- load-offset clustering (which struct offsets are type-prop-unresolved) ---
echo "" | tee -a "$RUN_LOG"
echo "-- load-offset clustering --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/load_offset_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- add-failed clustering (uninit-arg + typed-ptr-arith failures) ---
echo "" | tee -a "$RUN_LOG"
echo "-- add-failed clustering --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/add_failed_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- auto-seed _REF.gc for newly-real-clean files (no-op if coverage complete) ---
if [ -f "$ROOT/test/offline/config/jakx/config.jsonc" ]; then
    echo "" | tee -a "$RUN_LOG"
    echo "-- auto-seed _REF.gc for new real-clean files --" | tee -a "$RUN_LOG"
    python3 scripts/jakx_watch/seed_refs.py 2>&1 | tee -a "$RUN_LOG" || true
fi

# --- offline-test pass (only if jakx corpus exists) ---
if [ -f "$ROOT/test/offline/config/jakx/config.jsonc" ]; then
    echo "" | tee -a "$RUN_LOG"
    echo "-- offline-test pass --" | tee -a "$RUN_LOG"
    python3 scripts/jakx_watch/offline_test_pass.py 2>&1 | tee -a "$RUN_LOG"
else
    echo "" | tee -a "$RUN_LOG"
    echo "-- offline-test: SKIPPED (no jakx config or reference corpus yet) --" | tee -a "$RUN_LOG"
    echo "   to enable: create test/offline/config/jakx/config.jsonc and" | tee -a "$RUN_LOG"
    echo "   test/decompiler/reference/jakx/" | tee -a "$RUN_LOG"
fi

# Re-render status.md now that types_drift.py + offline_test_pass.py have
# augmented latest.json. measure.py wrote status.md earlier, before those ran.
echo "" | tee -a "$RUN_LOG"
echo "-- re-rendering status.md with augmented data --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/measure.py --restatus-only 2>&1 | tee -a "$RUN_LOG"
