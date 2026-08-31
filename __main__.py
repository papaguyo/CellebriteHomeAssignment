#!/usr/bin/env python3
"""
Interactive CLI — run a demo attack against the C simulator.

Usage:
    python run.py                          # auto-starts simulator
    python run.py --fail-stage 1          # scripted stage failure
    python run.py --drop-after-stage 0   # scripted connection drop
    python __main__.py --port 9000        # connect to a running simulator
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Callable

from attacks import ATTACKS
from client.tcp_client import SimulatedDeviceClient
from framework import Attack
from framework.device import ConnectionLostError, DeviceState
from framework.extractor import Extractor
from framework.selector import Selector
from framework.selectors import ProbabilitySelector, PrioritySelector, WeightedRandomSelector
from menu import arrow_select

SELECTORS: dict[str, type[Selector]] = {
    "probability": ProbabilitySelector,
    "priority":    PrioritySelector,
    "weighted":    WeightedRandomSelector,
}


# ---------------------------------------------------------------------------
# Terminal UI helpers
# ---------------------------------------------------------------------------

_TTY = sys.stdout.isatty()

_G  = "\033[32m"   if _TTY else ""   # green
_R  = "\033[31m"   if _TTY else ""   # red
_Y  = "\033[33m"   if _TTY else ""   # yellow
_B  = "\033[1m"    if _TTY else ""   # bold
_DIM = "\033[2m"   if _TTY else ""   # dim
_RST = "\033[0m"   if _TTY else ""   # reset
_CL  = "\r\033[K"  if _TTY else "\r" # carriage return + clear line


def _header() -> None:
    title = "  Multi-Stage Attack Orchestrator  "
    bar = "═" * len(title)
    print(f"\n{_B}╔{bar}╗")
    print(f"║{title}║")
    print(f"╚{bar}╝{_RST}\n")


def _section(label: str) -> None:
    print(f"\n{_B}[*]{_RST} {label}")


def _device_table(state: DeviceState) -> None:
    rows = [
        ("Model",   state.model),
        ("iOS",     state.ios_version),
        ("Battery", f"{state.battery_level}%"),
        ("Locked",  "Yes" if state.is_locked else "No"),
    ]
    for key, val in rows:
        print(f"  {_DIM}{key:<10}{_RST} {val}")


def _pick_attack(compatible: list[Attack], recommended: Attack) -> Attack | None:
    """Arrow-key attack picker. Returns chosen Attack or None to abort."""
    if not compatible:
        return None

    ranked  = sorted(compatible, key=lambda x: -x.estimated_success_probability)
    rec_idx = ranked.index(recommended)

    def _label(a: Attack) -> str:
        destr = "  DESTRUCTIVE" if a.is_destructive else "  non-destructive"
        tag   = "  ← recommended" if a is recommended else ""
        return (f"{a.name:<20} p={a.estimated_success_probability:.2f}  "
                f"{len(a.stages)} stage{'s' if len(a.stages) != 1 else ' '}{destr}{tag}")

    print()
    idx = arrow_select([_label(a) for a in ranked],
                       title=f"{len(ranked)} attack(s) compatible:",
                       default=rec_idx)
    if idx is None:
        return None
    return ranked[idx]


def _stage_line(i: int, n: int, name: str) -> Callable[[bool, str], None]:
    """Print a stage progress line. Returns a done() callable that fills in the result."""
    prefix = f"  [{i}/{n}] {name} "
    dot_w  = max(2, 52 - len(prefix))
    dots   = _DIM + ("·" * dot_w) + _RST
    sys.stdout.write(f"{prefix}{dots}")
    sys.stdout.flush()

    def done(ok: bool, reason: str = "") -> None:
        mark   = f"{_G}✓{_RST}" if ok else f"{_R}✗{_RST}"
        suffix = f"  {_DIM}{reason}{_RST}" if reason else ""
        sys.stdout.write(f"{_CL}{prefix}{dots} {mark}{suffix}\n")
        sys.stdout.flush()

    return done


def _outcome_success(name: str) -> None:
    print(f"\n{_G}{_B}[✓] Attack '{name}' succeeded!{_RST}")


def _outcome_failure(attack_name: str, stage_idx: int, stage_name: str,
                     reason: str = "", error: Exception | None = None) -> None:
    print(f"\n{_R}{_B}[✗] Attack '{attack_name}' failed at "
          f"stage {stage_idx} '{stage_name}'.{_RST}")
    if reason:
        print(f"    Reason : {reason}")
    if error:
        print(f"    Error  : {error}")
    print(f"    {_DIM}Tip: re-run with --log-level DEBUG for the full framework trace.{_RST}")


def _no_attacks() -> None:
    print(f"\n{_Y}[!] No compatible attack found for this device.{_RST}")
    print("    Check model, iOS version, and battery level.")


def _file_table(files: dict[str, bytes]) -> None:
    if not files:
        print(f"  {_DIM}(no files found){_RST}")
        return
    for path in sorted(files):
        print(f"  {path:<44} {len(files[path]):>5} B")
    total = sum(len(v) for v in files.values())
    print(f"\n  {_DIM}{len(files)} file{'s' if len(files) != 1 else ''} · {total} bytes total{_RST}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-stage attack orchestrator")
    parser.add_argument("--host",      default="127.0.0.1")
    parser.add_argument("--port",      type=int, default=9000)
    parser.add_argument("--log-level", default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Framework log level (default: WARNING — use DEBUG for full trace)")
    parser.add_argument("--no-extract", dest="extract", action="store_false", default=True)
    parser.add_argument("--selector", default="probability",
                        choices=list(SELECTORS),
                        help="Attack selection strategy (default: probability)")
    parser.add_argument("--auto", action="store_true",
                        help="Skip the attack picker and run the recommended attack automatically")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    _header()

    try:
        with SimulatedDeviceClient(args.host, args.port) as client:

            # 1. Device state
            _section("Querying device state...")
            state = client.get_state()
            _device_table(state)

            # 2. Attack selection
            _section("Evaluating compatible attacks...")
            selector = SELECTORS[args.selector]()
            compatible = [a for a in ATTACKS if a.is_compatible(state)]
            winner = selector.select(ATTACKS, state)

            if winner is None:
                _no_attacks()
                return 1

            if args.auto:
                chosen = winner
                print(f"\n  Auto-selected: {_B}{chosen.name}{_RST}  "
                      f"(p={chosen.estimated_success_probability:.2f})\n")
            else:
                chosen = _pick_attack(compatible, winner)
                if chosen is None:
                    print("\nAborted.")
                    return 0

            # 4. Run stages
            print(f"\n[*] Running '{chosen.name}' ({len(chosen.stages)} stages)...\n")
            n = len(chosen.stages)
            for i, stage in enumerate(chosen.stages):
                done = _stage_line(i + 1, n, stage.name)
                try:
                    result = client.run_stage(chosen.id, i)
                except ConnectionLostError as exc:
                    done(False, "connection lost")
                    _outcome_failure(chosen.name, i, stage.name, error=exc)
                    return 1

                done(result.success, result.reason if not result.success else "")

                if not result.success:
                    _outcome_failure(chosen.name, i, stage.name, reason=result.reason)
                    return 1

            _outcome_success(chosen.name)

            # 5. Extraction
            if args.extract:
                _section("Extracting files from /...")
                print()
                extractor = Extractor(client)
                files = extractor.extract_all("/")
                _file_table(files)

    except ConnectionRefusedError:
        print(f"{_R}[ERROR]{_RST} Could not connect to {args.host}:{args.port}")
        print(f"        Start the simulator first:  ./simulator/simulator --port {args.port}")
        print(f"        Or use run.py which starts it automatically.")
        return 1

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
