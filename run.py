#!/usr/bin/env python3
"""
Starts the simulator in the background and runs the attack CLI.
Usage: python run.py [--log-level DEBUG] [--fail-stage 1] [--drop-after-stage 0]
"""
import argparse
import subprocess
import socket
import sys
import time
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
SIMULATOR = os.path.join(ROOT, "simulator", "simulator")
PORT = 9000


def wait_for_port(port: int, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def main():
    parser = argparse.ArgumentParser(description="Run simulator + attack CLI in one command")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    parser.add_argument("--fail-stage", type=int, default=None, help="Force this stage index to fail")
    parser.add_argument("--drop-after-stage", type=int, default=None, help="Drop connection after this stage")
    parser.add_argument("--battery", type=int, default=None, help="Override simulator battery level")
    parser.add_argument("--model", default=None, help="Override simulator device model")
    parser.add_argument("--ios", default=None, help="Override simulator iOS version")
    args = parser.parse_args()

    if not os.path.isfile(SIMULATOR):
        print("Simulator binary not found — building it...")
        result = subprocess.run(["make", "-C", os.path.join(ROOT, "simulator")], capture_output=True)
        if result.returncode != 0:
            print("Build failed:\n", result.stderr.decode())
            sys.exit(1)

    sim_args = [SIMULATOR, "--port", str(PORT)]
    if args.fail_stage is not None:
        sim_args += ["--fail-stage", str(args.fail_stage)]
    if args.drop_after_stage is not None:
        sim_args += ["--drop-after-stage", str(args.drop_after_stage)]
    if args.battery is not None:
        sim_args += ["--battery", str(args.battery)]
    if args.model is not None:
        sim_args += ["--model", args.model]
    if args.ios is not None:
        sim_args += ["--ios", args.ios]

    sim = subprocess.Popen(sim_args, stderr=subprocess.PIPE)

    if not wait_for_port(PORT):
        print("Simulator did not start in time.")
        sim.terminate()
        sys.exit(1)

    try:
        subprocess.run([sys.executable, "__main__.py", "--port", str(PORT), "--log-level", args.log_level])
    finally:
        sim.terminate()
        sim.wait()


if __name__ == "__main__":
    main()
