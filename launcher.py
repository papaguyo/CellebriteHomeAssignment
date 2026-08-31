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
import termios
import time
import tty

from menu import arrow_select

ROOT       = os.path.dirname(os.path.abspath(__file__))
SIMULATOR  = os.path.join(ROOT, "simulator", "simulator")
PYTHON     = sys.executable
PORT       = 9000

_TTY = sys.stdout.isatty()
_B   = "\033[1m"  if _TTY else ""
_DIM = "\033[2m"  if _TTY else ""
_RST = "\033[0m"  if _TTY else ""

# ---------------------------------------------------------------------------
# Session state — selector strategy chosen by the user
# ---------------------------------------------------------------------------

_SELECTOR_KEYS   = ["probability", "priority", "weighted"]
_SELECTOR_LABELS = [
    "Probability  — highest success chance (default)",
    "Priority     — fixed priority ranking per attack",
    "Weighted     — random, weighted by probability",
]
_current_selector_idx: int = 0   # index into _SELECTOR_KEYS


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

def _press_any_key() -> None:
    sys.stdout.write("\n  press any key to return to menu…\n")
    sys.stdout.flush()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        os.read(fd, 1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print("\033[2J\033[H", end="", flush=True)


def _header() -> None:
    title = "  Multi-Stage Attack Orchestrator  "
    bar   = "═" * len(title)
    print(f"\n{_B}╔{bar}╗\n║{title}║\n╚{bar}╝{_RST}\n")


def _configure_selector() -> None:
    global _current_selector_idx
    idx = arrow_select(
        _SELECTOR_LABELS,
        title="Choose a selector strategy:",
        default=_current_selector_idx,
    )
    if idx is not None:
        _current_selector_idx = idx
        print(f"  Selector set to: {_B}{_SELECTOR_LABELS[idx].split('—')[0].strip()}{_RST}\n")


def main() -> None:
    global _current_selector_idx

    sim_flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if not os.path.isfile(SIMULATOR):
        print("Building simulator...")
        result = subprocess.run(["make", "-C", os.path.join(ROOT, "simulator")],
                                capture_output=True)
        if result.returncode != 0:
            print("Build failed:\n", result.stderr.decode())
            sys.exit(1)

    MENU_ITEMS = ["Run attack", "Configure selector", "Run tests", "Quit"]

    while True:
        _header()
        sel_name = _SELECTOR_KEYS[_current_selector_idx]
        print(f"  {_DIM}Selector: {_SELECTOR_LABELS[_current_selector_idx].split('—')[0].strip()}{_RST}\n")
        choice = arrow_select(MENU_ITEMS)

        if choice is None or choice == 3:   # Quit or Esc
            print("Bye.")
            break

        if choice == 0:   # Run attack
            if not _start_simulator(sim_flags):
                print("Simulator failed to start.")
                continue
            subprocess.run([PYTHON, os.path.join(ROOT, "__main__.py"),
                            "--port", str(PORT),
                            "--selector", sel_name])
            _stop_simulator()

        elif choice == 1:   # Configure selector
            _configure_selector()
            continue        # skip the trailing print() — header will redraw

        elif choice == 2:   # Run tests
            subprocess.run([PYTHON, os.path.join(ROOT, "test_runner.py")])

        _press_any_key()


if __name__ == "__main__":
    main()
