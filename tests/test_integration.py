"""
Integration tests — spin up the real C simulator binary and run full scenarios
over a real TCP connection.

These tests require `make -C simulator` to succeed (the conftest session fixture
handles compilation automatically).
"""
from __future__ import annotations

import pytest

from client.tcp_client import SimulatedDeviceClient
from framework.attack import Attack
from framework.device import ConnectionLostError, DeviceError
from framework.extractor import Extractor
from framework.orchestrator import Orchestrator
from framework.stage import Stage


# helpers

def _make_attack(id: str, n_stages: int = 2) -> Attack:
    """Compatible with iPhone14,2 / iOS 16.5 — matches simulator defaults."""
    return Attack(
        id=id,
        name=id,
        stages=[Stage(id=f"s{i}", name=f"Stage {i}", success_probability=0.9) for i in range(n_stages)],
        compatible_models=["iPhone14,2"],
        min_ios=(16, 0),
        max_ios=(16, 9),
        min_battery=20,
    )


# GET_STATE

class TestGetState:
    def test_returns_configured_defaults(self, simulator_process):
        host, port = simulator_process
        with SimulatedDeviceClient(host, port) as client:
            state = client.get_state()
        assert state.model == "iPhone14,2"
        assert state.ios_version == "16.5"
        assert state.battery_level == 80
        assert state.is_locked is True


# full success path

class TestFullSuccess:
    def test_two_stage_attack_succeeds(self, simulator_process):
        host, port = simulator_process
        attack = _make_attack("atk", n_stages=2)
        with SimulatedDeviceClient(host, port) as client:
            orchestrator = Orchestrator(client, [attack])
            outcome = orchestrator.run()
        assert outcome.success is True
        assert outcome.attack is attack
        assert outcome.failed_stage is None
        assert outcome.error is None

    def test_single_stage_attack_succeeds(self, simulator_process):
        host, port = simulator_process
        attack = _make_attack("atk", n_stages=1)
        with SimulatedDeviceClient(host, port) as client:
            outcome = Orchestrator(client, [attack]).run()
        assert outcome.success is True


# scripted stage failure

class TestStageFailure:
    def test_stage_1_forced_fail(self, simulator_fail_stage1):
        host, port = simulator_fail_stage1
        attack = _make_attack("atk", n_stages=3)
        with SimulatedDeviceClient(host, port) as client:
            outcome = Orchestrator(client, [attack]).run()
        assert outcome.success is False
        assert outcome.failed_stage == 1
        assert outcome.error is None

    def test_stage_0_ok_then_stage_1_fails(self, simulator_fail_stage1):
        """Stage 0 runs and succeeds; stage 1 is forced to fail."""
        host, port = simulator_fail_stage1
        attack = _make_attack("atk", n_stages=2)
        with SimulatedDeviceClient(host, port) as client:
            outcome = Orchestrator(client, [attack]).run()
        assert outcome.success is False
        assert outcome.failed_stage == 1


# connection drop mid-chain

class TestConnectionDrop:
    def test_connection_lost_after_stage_0(self, simulator_drop_after_stage0):
        host, port = simulator_drop_after_stage0
        attack = _make_attack("atk", n_stages=3)
        with SimulatedDeviceClient(host, port) as client:
            outcome = Orchestrator(client, [attack]).run()
        assert outcome.success is False
        assert isinstance(outcome.error, ConnectionLostError)
        assert outcome.failed_stage == 1  # drop happens before stage 1 can respond


# extract_all over TCP

class TestExtractAll:
    def test_extract_all_returns_known_files(self, simulator_process):
        host, port = simulator_process
        attack = _make_attack("atk", n_stages=1)
        with SimulatedDeviceClient(host, port) as client:
            outcome = Orchestrator(client, [attack]).run()
            assert outcome.success is True
            ex = Extractor(client)
            files = ex.extract_all("/")
        assert "/contacts.db" in files
        assert "/media/photo1.jpg" in files
        assert "/media/photo2.jpg" in files
        assert "/logs/system.log" in files

    def test_read_single_file_over_tcp(self, simulator_process):
        host, port = simulator_process
        with SimulatedDeviceClient(host, port) as client:
            content = client.read_file("/contacts.db")
        assert b"contacts" in content


# no compatible attack

class TestNoCompatibleAttack:
    def test_incompatible_device_model(self, simulator_process):
        host, port = simulator_process
        attack = Attack(
            id="ios15_only",
            name="iOS 15 only",
            stages=[Stage("s0", "S0", 0.9)],
            compatible_models=["iPhone13,1"],
            min_ios=(15, 0), max_ios=(15, 9), min_battery=10,
        )
        with SimulatedDeviceClient(host, port) as client:
            outcome = Orchestrator(client, [attack]).run()
        assert outcome.success is False
        assert outcome.attack is None
        assert isinstance(outcome.error, DeviceError)
