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
    --config-override '{"decompile_code": true, "levels_extract": false, "allowed_objects": []}' \
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
    tail -20 "$RUN_LOG" | tee -a "$RUN_LOG"
    exit 1
fi

# Remember the config hash we decompiled against.
echo "$NEW_HASH" > "$CFG_HASH_FILE"

echo "-- measuring --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/measure.py \
    --decomp-out "$OUT_DIR/jakx" \
    --log "$DECOMP_LOG" 2>&1 | tee -a "$RUN_LOG"
