#!/usr/bin/env python3
"""Interactive test runner — pick a suite, see the verdict, loop."""
from __future__ import annotations

import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTEST = os.path.join(ROOT, ".venv", "bin", "pytest")

_TTY  = sys.stdout.isatty()
_G    = "\033[32m"  if _TTY else ""
_R    = "\033[31m"  if _TTY else ""
_Y    = "\033[33m"  if _TTY else ""
_B    = "\033[1m"   if _TTY else ""
_DIM  = "\033[2m"   if _TTY else ""
_RST  = "\033[0m"   if _TTY else ""

SUITES = [
    ("All tests",             ["tests/"]),
    ("All unit tests",        ["tests/test_selector.py",
                               "tests/test_orchestrator.py",
                               "tests/test_extractor.py"]),
    ("Selector (unit)",       ["tests/test_selector.py"]),
    ("Orchestrator (unit)",   ["tests/test_orchestrator.py"]),
    ("Extractor (unit)",      ["tests/test_extractor.py"]),
    ("Integration (real sim)", ["tests/test_integration.py"]),
]


def header() -> None:
    title = "  Test Runner  "
    bar = "═" * len(title)
    print(f"\n{_B}╔{bar}╗\n║{title}║\n╚{bar}╝{_RST}\n")


def menu() -> int | None:
    print(f"{_B}Select a test suite:{_RST}\n")
    for i, (name, _) in enumerate(SUITES, 1):
        tag = f"{_DIM}(starts simulator subprocess){_RST}" if "Integration" in name else ""
        print(f"  {_B}[{i}]{_RST} {name}  {tag}")
    print(f"\n  {_B}[q]{_RST} Quit\n")

    try:
        raw = input("Choice: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None

    if raw == "q":
        return None
    try:
        choice = int(raw)
        if 1 <= choice <= len(SUITES):
            return choice - 1
    except ValueError:
        pass
    print(f"{_Y}Invalid choice.{_RST}")
    return -1  # sentinel: re-show menu


def run_suite(idx: int) -> bool:
    name, paths = SUITES[idx]
    print(f"\n{_B}Running: {name}{_RST}\n{'─' * 50}")
    result = subprocess.run(
        [PYTEST, "-v", "--tb=short"] + paths,
        cwd=ROOT,
    )
    passed = result.returncode == 0
    bar = "─" * 50
    if passed:
        print(f"{bar}\n{_G}{_B}  ✓ ALL PASSED{_RST}\n")
    else:
        print(f"{bar}\n{_R}{_B}  ✗ SOME FAILED{_RST}\n")
    return passed


def again() -> bool:
    try:
        ans = input("Run again? [Y/n]: ").strip().lower()
        return ans in ("", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def main() -> None:
    header()
    while True:
        idx = menu()
        if idx is None:
            print("Bye.")
            break
        if idx == -1:
            continue
        run_suite(idx)
        if not again():
            print("Bye.")
            break
        print()


if __name__ == "__main__":
    main()
