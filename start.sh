#!/bin/bash
# Starts the simulator in the background, then launches the interactive CLI.
# Run stop.sh to kill the simulator when you're done.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.simulator.pid"
PORT=9000

# Kill any leftover simulator from a previous run
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    kill "$OLD_PID" 2>/dev/null
    rm -f "$PID_FILE"
fi

# Start simulator in background
"$SCRIPT_DIR/simulator/simulator" --port $PORT "$@" &
SIM_PID=$!
echo $SIM_PID > "$PID_FILE"
echo "Simulator started (PID $SIM_PID, port $PORT)"

# Wait for it to be ready
for i in $(seq 1 30); do
    nc -z 127.0.0.1 $PORT 2>/dev/null && break
    sleep 0.1
done

# Launch the CLI
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/__main__.py" --port $PORT
