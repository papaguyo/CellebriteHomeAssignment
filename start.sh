#!/bin/bash
# start.sh — build everything and run the full demo (non-interactive).
# Usage: ./start.sh [--fail-stage N] [--drop-after-stage N] [--battery N] ...

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# Create virtual environment if it doesn't exist
if [ ! -d "$DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$DIR/.venv"
fi

# Build the C simulator if the binary is missing
if [ ! -f "$DIR/simulator/simulator" ]; then
    echo "Building simulator..."
    make -C "$DIR/simulator"
fi

# Install Python dependencies if not yet installed
if ! "$DIR/.venv/bin/python" -c "import pytest" 2>/dev/null; then
    echo "Installing dependencies..."
    "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
fi

exec "$DIR/.venv/bin/python" "$DIR/run.py" "$@"
