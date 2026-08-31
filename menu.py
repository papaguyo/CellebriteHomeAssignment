"""
Arrow-key menu selector — stdlib only (termios/tty/select/os).
Falls back to numbered input when stdin/stdout is not a TTY.

Why os.read() instead of sys.stdin.read():
  Python's sys.stdin has an internal buffer.  When sys.stdin.read(1) returns
  '\x1b', the buffered layer may have already pulled the whole 3-byte arrow
  sequence (\x1b[A) out of the OS fd.  A subsequent select() on the raw fd
  then sees nothing and we mistake the prefix for a lone Esc.  Using
  os.read(fd, 1) skips the Python buffer so select() stays in sync.
"""
from __future__ import annotations

import os
import select
import sys
import termios
import tty

_TTY = sys.stdout.isatty() and sys.stdin.isatty()
_G   = "\033[32m" if _TTY else ""
_B   = "\033[1m"  if _TTY else ""
_DIM = "\033[2m"  if _TTY else ""
_RST = "\033[0m"  if _TTY else ""


def _read_key(fd: int) -> str:
    """Read one key or escape sequence via the raw file descriptor."""
    ch = os.read(fd, 1).decode("utf-8", errors="replace")
    if ch == "\x1b":
        # Arrow keys arrive as \x1b [ A/B/C/D — wait up to 150 ms per byte
        if select.select([fd], [], [], 0.15)[0]:
            ch2 = os.read(fd, 1).decode("utf-8", errors="replace")
            if ch2 == "[" and select.select([fd], [], [], 0.15)[0]:
                return "\x1b[" + os.read(fd, 1).decode("utf-8", errors="replace")
            return "\x1b" + ch2
    return ch


def arrow_select(
    items: list[str],
    title: str | None = None,
    default: int = 0,
) -> int | None:
    """
    Arrow-key navigable menu.  Returns the selected index or None (abort).
    Falls back to numbered input in non-TTY environments (pipes, CI).
    """
    if not _TTY:
        return _fallback(items, title, default)

    idx     = max(0, min(default, len(items) - 1))
    n_lines = (1 if title else 0) + len(items) + 1   # title + items + hint
    first   = True

    def render() -> None:
        nonlocal first
        if not first:
            # Move cursor up n_lines and back to column 0
            sys.stdout.write(f"\033[{n_lines}A\r")
        first = False

        if title:
            sys.stdout.write(f"  {_DIM}{title}{_RST}\033[K\n")

        for i, item in enumerate(items):
            if i == idx:
                sys.stdout.write(f"  {_G}►{_RST} {_B}{item}{_RST}\033[K\n")
            else:
                sys.stdout.write(f"    {item}\033[K\n")

        sys.stdout.write(f"  {_DIM}↑↓ navigate  ↵ select  q abort{_RST}\033[K\n")
        sys.stdout.flush()

    fd  = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)   # char-by-char; keeps Ctrl-C as SIGINT
        render()
        while True:
            try:
                key = _read_key(fd)
            except KeyboardInterrupt:
                return None

            if key == "\x1b[A":                        # ↑
                idx = max(0, idx - 1)
            elif key == "\x1b[B":                      # ↓
                idx = min(len(items) - 1, idx + 1)
            elif key in ("\r", "\n"):                  # Enter
                return idx
            elif key in ("q", "Q", "\x1b", "\x03"):   # q / Esc / Ctrl-C
                return None

            render()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _fallback(items: list[str], title: str | None, default: int) -> int | None:
    """Numbered-input fallback for non-TTY environments."""
    if title:
        print(f"  {title}")
    for i, item in enumerate(items, 1):
        suffix = "  (default)" if i - 1 == default else ""
        print(f"  [{i}] {item}{suffix}")
    print("  [q] Abort")
    try:
        raw = input(f"\nChoice [{default + 1}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw == "":
        return default
    if raw == "q":
        return None
    try:
        n = int(raw)
        if 1 <= n <= len(items):
            return n - 1
    except ValueError:
        pass
    return default
