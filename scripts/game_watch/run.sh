#!/usr/bin/env bash
# Game-aware decomp + measure wrapper for jak1/jak2/jak3.
# (jakx has its own scripts/jakx_watch/run.sh with the full scanner suite.
# This script is the minimal cross-game equivalent — decomp + measure_minimal,
# nothing else — to support apply_guard's regression-gate on those games.)
#
# Locks at .<game>_watch/.run.lock. Outputs to .<game>_watch/decomp_out/<game>/.
# Generates .<game>_watch/status.md via scripts/game_watch/measure_minimal.py.
#
# Usage:
#   bash scripts/game_watch/run.sh --game jak3
#   GAME_WATCH_FORCE=1 bash scripts/game_watch/run.sh --game jak2
#   GAME_WATCH_WAIT=1  bash scripts/game_watch/run.sh --game jak3
#
# Exit codes:
#   0 = decomp + measurement succeeded
#   1 = decomp couldn't load types / emitted zero files
#   2 = lock contention (skipped — set GAME_WATCH_WAIT=1 to queue)

set -u
cd "$(dirname "$0")/../.."
ROOT="$PWD"

GAME=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --game)
            GAME="$2"; shift 2;;
        --game=*)
            GAME="${1#--game=}"; shift;;
        *)
            echo "ERROR: unknown arg: $1" >&2; exit 2;;
    esac
done

case "$GAME" in
    jak1|jak2|jak3) ;;
    jakx)
        echo "ERROR: --game=jakx not supported here. Use scripts/jakx_watch/run.sh" >&2
        exit 2;;
    *)
        echo "ERROR: --game must be jak1, jak2, or jak3 (got: '$GAME')" >&2
        exit 2;;
esac

WATCH_DIR="$ROOT/.${GAME}_watch"
mkdir -p "$WATCH_DIR"

# Lock to serialize concurrent runs.
LOCK="$WATCH_DIR/.run.lock"
exec 9>"$LOCK"
if [ "${GAME_WATCH_WAIT:-0}" = "1" ]; then
    flock 9
else
    if ! flock -n 9; then
        echo "[game_watch:$GAME] another run is in progress — skipping." >&2
        echo "  set GAME_WATCH_WAIT=1 to queue instead of skip." >&2
        exit 2
    fi
fi
# lock held via fd 9 for the remainder

OUT_DIR="$WATCH_DIR/decomp_out"
LOG_DIR="$ROOT/log"
BIN="$ROOT/build/Release/decompiler/decompiler"
CFG="$ROOT/decompiler/config/$GAME/${GAME}_config.jsonc"
ISO="$ROOT/iso_data"

mkdir -p "$OUT_DIR"

if [ ! -x "$BIN" ]; then
    echo "ERROR: decompiler binary missing: $BIN" >&2
    echo "Build it first: cmake --build build/Release --target decompiler -j" >&2
    exit 1
fi

if [ ! -f "$CFG" ]; then
    echo "ERROR: game config missing: $CFG" >&2
    exit 1
fi

TS="$(date +%Y%m%dT%H%M%S)"
RUN_LOG="$WATCH_DIR/run-$TS.log"

echo "== game_watch: $GAME decomp run $TS ==" | tee "$RUN_LOG"
echo "config: $CFG" | tee -a "$RUN_LOG"
echo "iso:    $ISO" | tee -a "$RUN_LOG"
echo "out:    $OUT_DIR" | tee -a "$RUN_LOG"

START=$(date +%s)

# Hash config inputs to skip redundant decomps.
CFG_HASH_FILE="$WATCH_DIR/last_config_hash"
NEW_HASH=$({
    find "$ROOT/decompiler/config/$GAME" -type f \( -name '*.gc' -o -name '*.jsonc' \) -print0 \
      | sort -z \
      | xargs -0 sha1sum
} 2>/dev/null | sha1sum | awk '{print $1}')

FORCE="${GAME_WATCH_FORCE:-0}"
if [ "$FORCE" != "1" ] && [ -f "$CFG_HASH_FILE" ]; then
    OLD_HASH=$(cat "$CFG_HASH_FILE" 2>/dev/null || echo "")
    if [ "$OLD_HASH" = "$NEW_HASH" ]; then
        echo "config unchanged since last run (hash=$NEW_HASH); re-rendering status only." \
          | tee -a "$RUN_LOG"
        if [ -d "$OUT_DIR/$GAME" ]; then
            python3 scripts/game_watch/measure_minimal.py \
                --game "$GAME" --decomp-out "$OUT_DIR/$GAME" 2>&1 | tee -a "$RUN_LOG"
        fi
        exit 0
    fi
fi

# Wipe previous decomp output (private to .<game>_watch/, never global decompiler_out).
if [ -d "$OUT_DIR/$GAME" ]; then
    rm -rf "$OUT_DIR/$GAME"
    echo "wiped previous $OUT_DIR/$GAME" | tee -a "$RUN_LOG"
fi

echo "-- running decompiler --" | tee -a "$RUN_LOG"
set +e
"$BIN" "$CFG" "$ISO" "$OUT_DIR" \
    --version ntsc_v1 \
    --config-override '{"decompile_code": true, "levels_extract": false, "allowed_objects": [], "generate_all_types": false}' \
    >>"$RUN_LOG" 2>&1
RC=$?
set -e

END=$(date +%s)
ELAPSED=$((END - START))
echo "-- decompiler exited rc=$RC (elapsed ${ELAPSED}s) --" | tee -a "$RUN_LOG"

N_OUT=$(find "$OUT_DIR/$GAME" -name '*_disasm.gc' 2>/dev/null | wc -l)
echo "emitted $N_OUT _disasm.gc files" | tee -a "$RUN_LOG"

if [ "$N_OUT" = "0" ]; then
    echo "NO output files emitted — types likely failed to load." | tee -a "$RUN_LOG"
    STATUS="$WATCH_DIR/status.md"
    {
        echo '```'
        echo "# ${GAME}_watch status — FAILED"
        echo "last updated @ git $(git rev-parse HEAD 2>/dev/null | head -c 12)  ·  ts $(date -Iseconds)"
        echo ""
        echo "## ERROR: decomp emitted zero files"
        echo ""
        echo "Tail of run log:"
        echo ""
        tail -20 "$RUN_LOG" 2>/dev/null
        echo '```'
    } > "$STATUS"
    exit 1
fi

echo "$NEW_HASH" > "$CFG_HASH_FILE"

echo "-- measuring --" | tee -a "$RUN_LOG"
python3 scripts/game_watch/measure_minimal.py \
    --game "$GAME" --decomp-out "$OUT_DIR/$GAME" 2>&1 | tee -a "$RUN_LOG"

echo "-- done --" | tee -a "$RUN_LOG"
