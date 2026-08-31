#!/usr/bin/env python3
"""Interactive test runner — pick a suite with arrow keys, see the verdict, loop."""
from __future__ import annotations

import subprocess
import sys
import os

from menu import arrow_select

ROOT   = os.path.dirname(os.path.abspath(__file__))
PYTEST = os.path.join(ROOT, ".venv", "bin", "pytest")

_TTY = sys.stdout.isatty()
_G   = "\033[32m" if _TTY else ""
_R   = "\033[31m" if _TTY else ""
_B   = "\033[1m"  if _TTY else ""
_DIM = "\033[2m"  if _TTY else ""
_RST = "\033[0m"  if _TTY else ""

SUITES = [
    ("All tests",              ["tests/"]),
    ("All unit tests",         ["tests/test_selector.py",
                                "tests/test_orchestrator.py",
                                "tests/test_extractor.py"]),
    ("Selector        (unit)", ["tests/test_selector.py"]),
    ("Orchestrator    (unit)", ["tests/test_orchestrator.py"]),
    ("Extractor       (unit)", ["tests/test_extractor.py"]),
    ("Integration     (real simulator)", ["tests/test_integration.py"]),
]


def header() -> None:
    title = "  Test Runner  "
    bar = "═" * len(title)
    print(f"\n{_B}╔{bar}╗\n║{title}║\n╚{bar}╝{_RST}\n")


def run_suite(idx: int) -> bool:
    name, paths = SUITES[idx]
    print(f"\n{_B}Running: {name}{_RST}\n{'─' * 50}")
    result = subprocess.run([PYTEST, "-v", "--tb=short"] + paths, cwd=ROOT)
    passed = result.returncode == 0
    if passed:
        print(f"{'─' * 50}\n{_G}{_B}  ✓ ALL PASSED{_RST}\n")
    else:
        print(f"{'─' * 50}\n{_R}{_B}  ✗ SOME FAILED{_RST}\n")
    return passed


def again() -> bool:
    idx = arrow_select(["Yes, run another suite", "No, go back"], default=0)
    return idx == 0


def main() -> None:
    header()
    while True:
        labels = [name for name, _ in SUITES]
        idx = arrow_select(labels, title="Select a test suite:")
        if idx is None:
            break
        run_suite(idx)
        if not again():
            break
        print()
    print("\033[2J\033[H", end="", flush=True)


if __name__ == "__main__":
    main()
