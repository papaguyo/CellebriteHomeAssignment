#!/usr/bin/env python3
"""
CLI entry point — run a demo attack against the C simulator.

Usage:
    # Start the simulator first (in another terminal):
    ./simulator/simulator --port 9000

    # Then run this:
    python -m CellebriteHomeAssignment --port 9000
    python -m CellebriteHomeAssignment --port 9000 --log-level DEBUG
"""
from __future__ import annotations

import argparse
import logging
import sys

from client.tcp_client import SimulatedDeviceClient
from framework.attack import Attack
from framework.extractor import Extractor
from framework.orchestrator import Orchestrator
from framework.stage import Stage


# ---------------------------------------------------------------------------
# Demo attack catalogue — mirrors what the simulator supports by default
# ---------------------------------------------------------------------------

ATTACKS = [
    Attack(
        id="bootrom_exploit",
        name="Bootrom Exploit",
        stages=[
            Stage(id="s0", name="USB handshake",         success_probability=0.95),
            Stage(id="s1", name="Bootrom overflow",      success_probability=0.85),
            Stage(id="s2", name="Privilege escalation",  success_probability=0.90),
        ],
        compatible_models=["iPhone14,2", "iPhone14,3"],
        min_ios=(16, 0),
        max_ios=(16, 9),
        min_battery=20,
        is_destructive=False,
    ),
    Attack(
        id="checkm8",
        name="checkm8",
        stages=[
            Stage(id="s0", name="DFU mode trigger",      success_probability=0.80),
            Stage(id="s1", name="Heap overflow",         success_probability=0.75),
        ],
        compatible_models=["iPhone14,2", "iPhone13,4"],
        min_ios=(15, 0),
        max_ios=(17, 9),
        min_battery=10,
        is_destructive=True,
    ),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Attack orchestrator demo")
    parser.add_argument("--host",      default="127.0.0.1")
    parser.add_argument("--port",      type=int, default=9000)
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--extract",   action="store_true", default=True,
                        help="Extract files after a successful attack (default: on)")
    parser.add_argument("--no-extract", dest="extract", action="store_false")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"\nConnecting to simulator at {args.host}:{args.port} ...\n")

    try:
        with SimulatedDeviceClient(args.host, args.port) as client:
            orchestrator = Orchestrator(client, ATTACKS)
            outcome = orchestrator.run()

            print()
            if outcome.success:
                print(f"[OK] Attack '{outcome.attack.name}' succeeded.")
            elif outcome.attack is None:
                print("[FAIL] No compatible attack found for this device.")
                return 1
            else:
                stage_name = outcome.attack.stages[outcome.failed_stage].name
                err = f" ({outcome.error})" if outcome.error else ""
                print(f"[FAIL] Attack '{outcome.attack.name}' failed at "
                      f"stage {outcome.failed_stage} '{stage_name}'{err}.")
                return 1

            if args.extract and outcome.success:
                print()
                extractor = Extractor(client)
                files = extractor.extract_all("/")

                if not files:
                    print("No files found on device.")
                else:
                    print("=== Extracted files ===")
                    for path, data in sorted(files.items()):
                        print(f"  {path:<40} {len(data):>6} B")
                    print(f"\n  Total: {len(files)} file(s), "
                          f"{sum(len(v) for v in files.values())} bytes")

    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to simulator at {args.host}:{args.port}")
        print("        Is the simulator running? Start it with:")
        print(f"        ./simulator/simulator --port {args.port}")
        return 1

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
