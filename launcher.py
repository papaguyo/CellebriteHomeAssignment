#!/usr/bin/env python3
"""
Top-level launcher — arrow-key menu to run an attack or the test suite.
Manages the simulator subprocess lifecycle around the attack CLI.

Usage:  ./start.sh [simulator flags]
        python launcher.py [--fail-stage N] [--drop-after-stage N] [--battery N] ...
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

from menu import arrow_select

ROOT       = os.path.dirname(os.path.abspath(__file__))
SIMULATOR  = os.path.join(ROOT, "simulator", "simulator")
PYTHON     = sys.executable
PORT       = 9000

_TTY = sys.stdout.isatty()
_B   = "\033[1m"  if _TTY else ""
_RST = "\033[0m"  if _TTY else ""


# ---------------------------------------------------------------------------
# Simulator lifecycle
# ---------------------------------------------------------------------------

_sim_proc: subprocess.Popen | None = None


def _start_simulator(extra_args: list[str]) -> bool:
    global _sim_proc
    if _sim_proc and _sim_proc.poll() is None:
        return True  # already running

    _sim_proc = subprocess.Popen(
        [SIMULATOR, "--port", str(PORT)] + extra_args,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _stop_simulator() -> None:
    global _sim_proc
    if _sim_proc and _sim_proc.poll() is None:
        _sim_proc.terminate()
        _sim_proc.wait()
    _sim_proc = None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

MENU_ITEMS = ["Run attack", "Run tests", "Quit"]


def _header() -> None:
    title = "  Multi-Stage Attack Orchestrator  "
    bar   = "═" * len(title)
    print(f"\n{_B}╔{bar}╗\n║{title}║\n╚{bar}╝{_RST}\n")


def main() -> None:
    # Collect simulator flags from argv (anything that looks like a sim flag)
    sim_flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if not os.path.isfile(SIMULATOR):
        print("Building simulator...")
        result = subprocess.run(["make", "-C", os.path.join(ROOT, "simulator")],
                                capture_output=True)
        if result.returncode != 0:
            print("Build failed:\n", result.stderr.decode())
            sys.exit(1)

    while True:
        _header()
        choice = arrow_select(MENU_ITEMS)

        if choice is None or choice == 2:   # Quit or Esc
            print("Bye.")
            break

        if choice == 0:   # Run attack
            if not _start_simulator(sim_flags):
                print("Simulator failed to start.")
                continue
            subprocess.run([PYTHON, os.path.join(ROOT, "__main__.py"),
                            "--port", str(PORT)])
            _stop_simulator()

        elif choice == 1:   # Run tests
            subprocess.run([PYTHON, os.path.join(ROOT, "test_runner.py")])

        print()


if __name__ == "__main__":
    main()
