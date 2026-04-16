#!/bin/bash
# Collect ALL compilation errors by iteratively compiling and skipping failed files
# Saves originals, empties failing files, recompiles, repeats until no more errors

ERRORS_FILE="/tmp/jakx_all_errors.txt"
EMPTIED_FILES="/tmp/jakx_emptied_files.txt"
> "$ERRORS_FILE"
> "$EMPTIED_FILES"

MAX_ITERS=200
iter=0

while [ $iter -lt $MAX_ITERS ]; do
    iter=$((iter + 1))

    # Compile and capture output
    output=$(build/Release/bin/goalc/goalc -g jakx --cmd "(begin (load-project \"goal_src/jakx/game.gp\") (make \"out/jakx/iso/GAME.CGO\" :force #f))" 2>&1)

    # Check if build succeeded
    if ! echo "$output" | grep -q "Build failed"; then
        echo "BUILD SUCCEEDED after $iter iterations!"
        break
    fi

    # Extract the failing file
    failing_file=$(echo "$output" | grep "Build failed on" | head -1 | sed 's/.*Build failed on //')

    if [ -z "$failing_file" ]; then
        echo "Could not find failing file in iteration $iter"
        break
    fi

    # Extract the error message (lines between last Type Error/Compilation Error and "Compilation failed")
    error_msg=$(echo "$output" | grep -E "Type Error|has no field|has no method|Could not|Undefined|unknown|not found" | head -3)

    # Also get the specific error location
    error_loc=$(echo "$output" | grep -B2 "Compilation failed" | head -3)

    echo "=== ITER $iter: $failing_file ===" >> "$ERRORS_FILE"
    echo "$error_msg" >> "$ERRORS_FILE"
    echo "$error_loc" >> "$ERRORS_FILE"
    echo "" >> "$ERRORS_FILE"

    echo "[$iter] $failing_file"

    # Save original and empty the file
    if [ ! -f "${failing_file}.orig" ]; then
        cp "$failing_file" "${failing_file}.orig"
    fi
    echo ';;-*-Lisp-*-
(in-package goal)
' > "$failing_file"
    echo "$failing_file" >> "$EMPTIED_FILES"
done

echo ""
echo "=== SUMMARY ==="
echo "Total failing files: $(wc -l < "$EMPTIED_FILES")"
echo "Errors saved to: $ERRORS_FILE"
echo "Emptied files list: $EMPTIED_FILES"

# Restore all originals
echo ""
echo "Restoring originals..."
while read f; do
    if [ -f "${f}.orig" ]; then
        cp "${f}.orig" "$f"
        rm "${f}.orig"
    fi
done < "$EMPTIED_FILES"
echo "Done restoring."
