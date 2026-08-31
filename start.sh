#!/bin/bash
exec "$(dirname "$0")/.venv/bin/python" "$(dirname "$0")/launcher.py" "$@"
