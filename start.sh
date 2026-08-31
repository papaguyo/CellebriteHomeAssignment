#!/bin/bash
# Main launcher — choose between running an attack or the test suite.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.simulator.pid"
PYTHON="$SCRIPT_DIR/.venv/bin/python"
PORT=9000

# ANSI helpers (disabled when not a TTY)
if [ -t 1 ]; then
    B="\033[1m"; G="\033[32m"; R="\033[31m"; DIM="\033[2m"; RST="\033[0m"
else
    B=""; G=""; R=""; DIM=""; RST=""
fi

# ── simulator lifecycle ─────────────────────────────────────────────────────

start_simulator() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        return 0  # already running
    fi
    "$SCRIPT_DIR/simulator/simulator" --port $PORT "$@" &
    echo $! > "$PID_FILE"
    for i in $(seq 1 30); do
        nc -z 127.0.0.1 $PORT 2>/dev/null && return 0
        sleep 0.1
    done
    echo -e "${R}Simulator did not start.${RST}"
    return 1
}

stop_simulator() {
    if [ -f "$PID_FILE" ]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null
        rm -f "$PID_FILE"
    fi
}

# ── main menu ───────────────────────────────────────────────────────────────

while true; do
    echo ""
    echo -e "${B}╔═══════════════════════════════════════╗${RST}"
    echo -e "${B}║   Multi-Stage Attack Orchestrator     ║${RST}"
    echo -e "${B}╚═══════════════════════════════════════╝${RST}"
    echo ""
    echo -e "  ${B}[1]${RST} Run attack"
    echo -e "  ${B}[2]${RST} Run tests"
    echo -e "  ${B}[q]${RST} Quit"
    echo ""
    read -rp "Choice: " choice

    case "$choice" in
        1)
            start_simulator
            "$PYTHON" "$SCRIPT_DIR/__main__.py" --port $PORT
            stop_simulator
            ;;
        2)
            "$PYTHON" "$SCRIPT_DIR/test_runner.py"
            ;;
        q|Q)
            stop_simulator
            echo "Bye."
            break
            ;;
        *)
            echo -e "${R}Invalid choice.${RST}"
            ;;
    esac
done
