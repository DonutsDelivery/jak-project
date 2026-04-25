#!/bin/bash
# Re-install the flock wrapper after a cmake rebuild has overwritten it.
# Call this any time you run `cmake --build` and rebuild the decompiler target.
set -e
DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BIN_DIR="$DIR/build/Release/decompiler"
WRAPPER="$BIN_DIR/decompiler"
REAL="$BIN_DIR/decompiler.real"

if [ ! -f "$WRAPPER" ]; then
  echo "ERROR: $WRAPPER does not exist - was the decompiler built?" >&2
  exit 1
fi

# Detect if WRAPPER is currently the binary (size > 100k = ELF) or already the wrapper
SIZE=$(stat -c%s "$WRAPPER")
if [ "$SIZE" -gt 100000 ]; then
  # It's the real binary — swap in the wrapper
  echo "Installing wrapper (binary detected at $WRAPPER, size $SIZE)..."
  mv "$WRAPPER" "$REAL"
  cat > "$WRAPPER" << 'EOF'
#!/bin/bash
# jakx decomp serializer wrapper.
# Forwards to decompiler.real but holds /tmp/jakx-decomp.lock so concurrent
# invocations don't OOM the box. If the lock is already held, exits 1
# immediately with a clear stderr message — caller should retry later.
# To bypass (debugging only): JAKX_DECOMP_NO_LOCK=1 ./decompiler ...
REAL="$(dirname "$0")/decompiler.real"
if [ "${JAKX_DECOMP_NO_LOCK:-0}" = "1" ]; then
  exec "$REAL" "$@"
fi
exec 9>/tmp/jakx-decomp.lock
if ! flock -n 9; then
  echo "[decomp-wrapper] another decomp holds /tmp/jakx-decomp.lock — skipping. Set JAKX_DECOMP_NO_LOCK=1 to override." >&2
  exit 1
fi
"$REAL" "$@"
rc=$?
flock -u 9
exit $rc
EOF
  chmod +x "$WRAPPER"
  echo "Wrapper installed: $WRAPPER -> flock-then-exec '$REAL'"
elif [ -f "$REAL" ]; then
  echo "Wrapper already installed (size $SIZE, decompiler.real present). No-op."
else
  echo "ERROR: $WRAPPER is small (size $SIZE) but $REAL is missing. State is broken." >&2
  exit 1
fi
