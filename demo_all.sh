#!/bin/bash
# demo_all.sh — run all three attack scenarios in sequence.
# Shows: happy path, scripted stage failure, and connection drop.

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"

header() {
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "  %s\n" "$1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Build simulator once if needed
if [ ! -f "$DIR/simulator/simulator" ]; then
    echo "Building simulator..."
    make -C "$DIR/simulator"
fi

header "Scenario 1 — Happy path (all stages succeed)"
"$PY" "$DIR/run.py"

header "Scenario 2 — Stage failure (stage index 1 is scripted to fail)"
"$PY" "$DIR/run.py" --fail-stage 1 || true

header "Scenario 3 — Connection drop (TCP dropped after stage 0)"
"$PY" "$DIR/run.py" --drop-after-stage 0 || true

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  All scenarios complete."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
