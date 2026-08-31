#!/bin/bash
# Stops the simulator started by start.sh.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.simulator.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "Simulator is not running (no PID file found)."
    exit 0
fi

PID=$(cat "$PID_FILE")
if kill "$PID" 2>/dev/null; then
    echo "Simulator stopped (PID $PID)."
else
    echo "Simulator was already stopped."
fi
rm -f "$PID_FILE"
