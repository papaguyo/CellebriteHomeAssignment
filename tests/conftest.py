from __future__ import annotations

import subprocess
import socket
import time
import os
import pytest

from framework.device import DeviceState
from framework.stage import Stage
from framework.attack import Attack
from client.fake_device import FakeDevice


# ---------------------------------------------------------------------------
# Shared state / attack fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_state() -> DeviceState:
    return DeviceState(battery_level=80, ios_version="16.5", model="iPhone14,2", is_locked=True)


@pytest.fixture
def sample_attacks() -> list[Attack]:
    """
    Three attacks:
      - high_prob: compatible, two stages, combined prob 0.9*0.9=0.81
      - low_prob:  compatible, one stage,  prob 0.3
      - wrong_model: incompatible model
    """
    high_prob = Attack(
        id="high_prob",
        name="High Probability Attack",
        stages=[
            Stage(id="s0", name="Stage 0", success_probability=0.9),
            Stage(id="s1", name="Stage 1", success_probability=0.9),
        ],
        compatible_models=["iPhone14,2", "iPhone14,3"],
        min_ios=(16, 0),
        max_ios=(16, 9),
        min_battery=20,
    )
    low_prob = Attack(
        id="low_prob",
        name="Low Probability Attack",
        stages=[
            Stage(id="s0", name="Stage 0", success_probability=0.3),
        ],
        compatible_models=["iPhone14,2"],
        min_ios=(16, 0),
        max_ios=(16, 9),
        min_battery=20,
    )
    wrong_model = Attack(
        id="wrong_model",
        name="Wrong Model Attack",
        stages=[
            Stage(id="s0", name="Stage 0", success_probability=0.99),
        ],
        compatible_models=["iPhone13,1"],
        min_ios=(15, 0),
        max_ios=(15, 9),
        min_battery=10,
    )
    return [high_prob, low_prob, wrong_model]


@pytest.fixture
def fake_device(sample_state: DeviceState) -> FakeDevice:
    """FakeDevice where every stage of every attack succeeds."""
    return FakeDevice(
        state=sample_state,
        stage_results={
            ("high_prob", 0): True,
            ("high_prob", 1): True,
            ("low_prob", 0): True,
        },
        files={
            "/contacts.db": b"contacts data",
            "/media/photo1.jpg": b"jpg bytes",
            "/logs/system.log": b"log line\n",
        },
    )


# ---------------------------------------------------------------------------
# Integration fixtures (real C simulator subprocess)
# ---------------------------------------------------------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


SIMULATOR_BINARY = os.path.join(
    os.path.dirname(__file__), "..", "simulator", "simulator"
)


@pytest.fixture(scope="session")
def simulator_binary() -> str:
    """Compile the C simulator once per test session."""
    sim_dir = os.path.join(os.path.dirname(__file__), "..", "simulator")
    result = subprocess.run(["make", "-C", sim_dir], capture_output=True, text=True)
    assert result.returncode == 0, f"make failed:\n{result.stderr}"
    binary = os.path.join(sim_dir, "simulator")
    assert os.path.isfile(binary), "simulator binary not found after make"
    return binary


def _start_simulator(binary: str, extra_args: list[str]) -> tuple[subprocess.Popen, int]:
    port = _free_port()
    proc = subprocess.Popen(
        [binary, "--port", str(port)] + extra_args,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    # Wait until the port is accepting connections (up to 3 s)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            time.sleep(0.05)
    return proc, port


@pytest.fixture
def simulator_process(simulator_binary: str):
    """Default simulator with no scripted failures."""
    proc, port = _start_simulator(simulator_binary, [])
    yield "127.0.0.1", port
    proc.terminate()
    proc.wait(timeout=3)


@pytest.fixture
def simulator_fail_stage1(simulator_binary: str):
    """Simulator that forces stage index 1 to fail."""
    proc, port = _start_simulator(simulator_binary, ["--fail-stage", "1"])
    yield "127.0.0.1", port
    proc.terminate()
    proc.wait(timeout=3)


@pytest.fixture
def simulator_drop_after_stage0(simulator_binary: str):
    """Simulator that drops the connection after completing stage 0."""
    proc, port = _start_simulator(simulator_binary, ["--drop-after-stage", "0"])
    yield "127.0.0.1", port
    proc.terminate()
    proc.wait(timeout=3)
