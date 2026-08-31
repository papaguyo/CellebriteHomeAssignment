#!/bin/bash
# interactive.sh — arrow-key menu explorer (selector picker, attack picker, test runner).
# Usage: ./interactive.sh [--fail-stage N] [--drop-after-stage N] ...

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

# Build the C simulator if the binary is missing
if [ ! -f "$DIR/simulator/simulator" ]; then
    echo "Building simulator..."
    make -C "$DIR/simulator"
fi

exec "$DIR/.venv/bin/python" "$DIR/launcher.py" "$@"
