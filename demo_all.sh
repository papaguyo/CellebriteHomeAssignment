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

# Create virtual environment if it doesn't exist
if [ ! -d "$DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$DIR/.venv"
fi

# Install Python dependencies if not yet installed
if ! "$DIR/.venv/bin/python" -c "import pytest" 2>/dev/null; then
    echo "Installing dependencies..."
    "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
fi

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
