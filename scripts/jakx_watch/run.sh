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

# Serialize concurrent run.sh invocations. Multiple agents running this in parallel
# spawns N decompilers that thrash memory (~13GB each) and race on decomp_out/.
# Default: skip-if-locked — if another run is in progress, exit early and let the
# in-flight run's output be the measurement. Set JAKX_WATCH_WAIT=1 to queue instead.
mkdir -p "$ROOT/.jakx_watch"
LOCK="$ROOT/.jakx_watch/.run.lock"
exec 9>"$LOCK"
if [ "${JAKX_WATCH_WAIT:-0}" = "1" ]; then
    flock 9
else
    if ! flock -n 9; then
        echo "[run.sh] another jakx_watch run is in progress — skipping this invocation." >&2
        echo "         set JAKX_WATCH_WAIT=1 to queue instead of skip." >&2
        exit 0
    fi
fi
# lock held via fd 9 for the remainder of this shell

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
        # Re-render status.md from existing latest.json (don't overwrite it with
        # a bare snapshot from the default decompiler_out/jakx path).
        LATEST="$ROOT/.jakx_watch/history/latest.json"
        if [ -f "$LATEST" ]; then
            python3 scripts/jakx_watch/measure.py --restatus-only 2>&1 | tee -a "$RUN_LOG"
        elif [ -d "$OUT_DIR/jakx" ]; then
            python3 scripts/jakx_watch/measure.py --decomp-out "$OUT_DIR/jakx" 2>&1 | tee -a "$RUN_LOG"
        fi
        exit 0
    fi
fi

# Scoped-decomp support (apply_guard's --scope flag):
#   JAKX_WATCH_ALLOWED_OBJECTS — JSON array of object names (default: []).
#                                Passed to decompiler's allowed_objects to
#                                restrict re-decomp to a subset (~30 sec for
#                                ~50 files vs ~10 min for the full ~600).
#   JAKX_WATCH_NO_WIPE         — if "1", do NOT wipe OUT_DIR before decomp.
#                                Required for scoped runs so unscoped IR2
#                                files retain their state and measure.py
#                                reports cumulative metrics.
ALLOWED_OBJECTS_JSON="${JAKX_WATCH_ALLOWED_OBJECTS:-[]}"
NO_WIPE="${JAKX_WATCH_NO_WIPE:-0}"

if [ "$NO_WIPE" != "1" ] && [ -d "$OUT_DIR/jakx" ]; then
    rm -rf "$OUT_DIR/jakx"
    echo "wiped previous $OUT_DIR/jakx" | tee -a "$RUN_LOG"
elif [ "$NO_WIPE" = "1" ]; then
    echo "NO_WIPE=1 — preserving existing $OUT_DIR/jakx for scoped re-decomp" \
      | tee -a "$RUN_LOG"
fi

# Run decomp. The decompiler appends its own timestamped log in $LOG_DIR;
# we mirror stdout/stderr to our run log so we have a stable handle.
echo "-- running decompiler --" | tee -a "$RUN_LOG"
echo "allowed_objects: $ALLOWED_OBJECTS_JSON" | tee -a "$RUN_LOG"
OVERRIDE_JSON=$(printf '{"decompile_code": true, "levels_extract": false, "allowed_objects": %s, "generate_all_types": false}' "$ALLOWED_OBJECTS_JSON")
# Sentinel for "files actually emitted by THIS run" check (NO_WIPE-safe).
SENTINEL="$ROOT/.jakx_watch/.run_sentinel.$$"
touch "$SENTINEL"
set +e
"$BIN" "$CFG" "$ISO" "$OUT_DIR" \
    --version ntsc_v1 \
    --config-override "$OVERRIDE_JSON" \
    >>"$RUN_LOG" 2>&1
RC=$?
set -e

END=$(date +%s)
ELAPSED=$((END - START))
echo "-- decompiler exited rc=$RC (elapsed ${ELAPSED}s) --" | tee -a "$RUN_LOG"

# Pick up the freshest decompiler log it wrote (to feed into measure).
DECOMP_LOG=$(ls -t "$LOG_DIR"/decompiler.*.log 2>/dev/null | head -1)

# Success-ish: if we emitted any _disasm.gc files, measurement is meaningful.
# Use sentinel-newer count so NO_WIPE runs don't falsely pass on stale files.
N_OUT_FRESH=$(find "$OUT_DIR/jakx" -name '*_disasm.gc' -newer "$SENTINEL" 2>/dev/null | wc -l)
N_OUT_TOTAL=$(find "$OUT_DIR/jakx" -name '*_disasm.gc' 2>/dev/null | wc -l)
rm -f "$SENTINEL"
echo "emitted $N_OUT_FRESH new (of $N_OUT_TOTAL total) _disasm.gc files" | tee -a "$RUN_LOG"
# Backwards-compat: full-decomp paths use N_OUT below.
N_OUT="$N_OUT_FRESH"

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
        echo ""
        # Auto-triage: if the run log has a "Type X is unknown" banner, surface
        # the ref finder's output so agents 1/2 see blast radius immediately.
        FATAL_TYPE=$(grep -oE 'Type [^ ]+ is unknown' "$RUN_LOG" 2>/dev/null | head -1 | awk '{print $2}')
        if [ -n "$FATAL_TYPE" ]; then
            echo "## auto-triage: type_ref_finder.py for '$FATAL_TYPE'"
            echo ""
            python3 "$ROOT/scripts/jakx_watch/type_ref_finder.py" "$FATAL_TYPE" 2>/dev/null \
              | head -40
        fi
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

    echo "" | tee -a "$RUN_LOG"
    echo "-- field-drift queue --" | tee -a "$RUN_LOG"
    python3 scripts/jakx_watch/field_drift_scan.py \
        --regen "$NEW_TYPES" 2>&1 | tee -a "$RUN_LOG" || true
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

# --- return-type-mismatch clustering (:methods return type vs body actual) ---
echo "" | tee -a "$RUN_LOG"
echo "-- return-mismatch clustering --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/return_mismatch_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- discovery queue (ranked pure-discovery deftypes for new-type work) ---
echo "" | tee -a "$RUN_LOG"
echo "-- discovery queue --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/discovery_queue.py 2>&1 | tee -a "$RUN_LOG" || true

# --- mips2c port queue (ranked jak3 mips2c functions by jakx unblock) ---
echo "" | tee -a "$RUN_LOG"
echo "-- mips2c queue (legacy) --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/mips2c_candidates.py 2>&1 | tail -40 | tee -a "$RUN_LOG" || true

# --- mips2c candidate scan (dual-signal: jak3-has-it + asm-error markers) ---
echo "" | tee -a "$RUN_LOG"
echo "-- mips2c candidate scan (dual-signal) --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/mips2c_candidate_scan.py 2>&1 | tail -30 | tee -a "$RUN_LOG" || true

# --- C++ decompiler patch queue (malformed emission clusters) ---
echo "" | tee -a "$RUN_LOG"
echo "-- C++ patch queue --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/cpp_patch_queue.py 2>&1 | tee -a "$RUN_LOG" || true

# --- cluster impact (commented-deftype activation clusters ranked by unblock/cost) ---
echo "" | tee -a "$RUN_LOG"
echo "-- cluster impact --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/cluster_impact.py 2>&1 | tail -20 | tee -a "$RUN_LOG" || true

# --- clobber scan (define-extern stubs that clobber active deftypes at L>59000) ---
echo "" | tee -a "$RUN_LOG"
echo "-- clobber scan --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/clobber_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- label_types copy-port candidates (jak3→jakx confirmed copy-portables) ---
echo "" | tee -a "$RUN_LOG"
echo "-- label_types copy-port scan --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/label_types_copy_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- auto-seed _REF.gc for newly-real-clean files (no-op if coverage complete) ---
if [ -f "$ROOT/test/offline/config/jakx/config.jsonc" ]; then
    echo "" | tee -a "$RUN_LOG"
    echo "-- auto-seed _REF.gc for new real-clean files --" | tee -a "$RUN_LOG"
    python3 scripts/jakx_watch/seed_refs.py 2>&1 | tee -a "$RUN_LOG" || true
fi

# --- activation blocker queue (ranks block-commented deftypes by activation difficulty) ---
echo "" | tee -a "$RUN_LOG"
echo "-- activation blocker queue --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/activation_blocker_scan.py 2>&1 | tee -a "$RUN_LOG" || true

# --- REF drift scan (detects regressions + stale REFs after each decomp) ---
echo "" | tee -a "$RUN_LOG"
echo "-- REF drift scan --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/ref_drift_scan.py 2>&1 | tee -a "$RUN_LOG" || true

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

# --- commit impact log (empirical commit ranking by metric delta) ---
echo "" | tee -a "$RUN_LOG"
echo "-- commit impact log --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/commit_impact_log.py 2>&1 | tee -a "$RUN_LOG" || true

# Re-render status.md now that types_drift.py + offline_test_pass.py have
# augmented latest.json. measure.py wrote status.md earlier, before those ran.
echo "" | tee -a "$RUN_LOG"
echo "-- re-rendering status.md with augmented data --" | tee -a "$RUN_LOG"
python3 scripts/jakx_watch/measure.py --restatus-only 2>&1 | tee -a "$RUN_LOG"

# Guard: if offline_test is missing from latest.json (can happen when a
# concurrent run.sh call races and overwrites latest.json between
# offline_test_pass.py's read and write), re-run it now so status.md is
# fully populated.
if [ -f "$ROOT/test/offline/config/jakx/config.jsonc" ]; then
    LATEST="$ROOT/.jakx_watch/history/latest.json"
    if [ -f "$LATEST" ]; then
        HAS_OT=$(python3 -c "import json,sys; d=json.load(open('$LATEST')); sys.exit(0 if 'offline_test' in d else 1)" 2>/dev/null; echo $?)
        if [ "$HAS_OT" != "0" ]; then
            echo "" | tee -a "$RUN_LOG"
            echo "-- offline-test: re-running (offline_test key missing from latest.json — race recovery) --" | tee -a "$RUN_LOG"
            python3 scripts/jakx_watch/offline_test_pass.py 2>&1 | tee -a "$RUN_LOG" || true
            python3 scripts/jakx_watch/measure.py --restatus-only 2>&1 | tee -a "$RUN_LOG"
        fi
    fi
fi
