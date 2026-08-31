"""Unit tests for Orchestrator — uses FakeDevice, no subprocess."""
from __future__ import annotations

import pytest

from client.fake_device import FakeDevice
from framework.attack import Attack
from framework.device import DeviceState, ConnectionLostError, DeviceError
from framework.orchestrator import Orchestrator
from framework.stage import Stage


@pytest.fixture
def state() -> DeviceState:
    return DeviceState(battery_level=80, ios_version="16.5", model="iPhone14,2", is_locked=True)


def _attack(id: str, n_stages: int = 2) -> Attack:
    return Attack(
        id=id,
        name=id,
        stages=[Stage(id=f"s{i}", name=f"Stage {i}", success_probability=0.9) for i in range(n_stages)],
        compatible_models=["iPhone14,2"],
        min_ios=(16, 0),
        max_ios=(16, 9),
        min_battery=20,
    )


class TestOrchestratorSuccess:
    def test_full_success(self, state):
        attack = _attack("atk", 3)
        device = FakeDevice(state, stage_results={("atk", 0): True, ("atk", 1): True, ("atk", 2): True})
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is True
        assert outcome.attack is attack
        assert outcome.failed_stage is None
        assert outcome.error is None

    def test_success_with_single_stage(self, state):
        attack = _attack("atk", 1)
        device = FakeDevice(state, stage_results={("atk", 0): True})
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is True


class TestOrchestratorFailure:
    def test_stage_0_fails(self, state):
        attack = _attack("atk", 3)
        device = FakeDevice(state, stage_results={("atk", 0): False, ("atk", 1): True, ("atk", 2): True})
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is False
        assert outcome.failed_stage == 0
        assert outcome.error is None

    def test_middle_stage_fails(self, state):
        attack = _attack("atk", 3)
        device = FakeDevice(state, stage_results={("atk", 0): True, ("atk", 1): False, ("atk", 2): True})
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is False
        assert outcome.failed_stage == 1

    def test_last_stage_fails(self, state):
        attack = _attack("atk", 3)
        device = FakeDevice(state, stage_results={("atk", 0): True, ("atk", 1): True, ("atk", 2): False})
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is False
        assert outcome.failed_stage == 2

    def test_no_stages_run_after_first_failure(self, state):
        """Verify abort-on-first-failure: later stages must not be called."""
        call_log: list[tuple[str, int]] = []

        class TrackingDevice(FakeDevice):
            def run_stage(self, attack_id, stage_index):
                call_log.append((attack_id, stage_index))
                return super().run_stage(attack_id, stage_index)

        attack = _attack("atk", 3)
        device = TrackingDevice(state, stage_results={("atk", 0): False})
        Orchestrator(device, [attack]).run()
        assert call_log == [("atk", 0)]


class TestOrchestratorConnectionLost:
    def test_connection_lost_mid_chain(self, state):
        attack = _attack("atk", 3)
        device = FakeDevice(
            state,
            stage_results={("atk", 0): True},
            connection_drops={("atk", 1)},
        )
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is False
        assert outcome.failed_stage == 1
        assert isinstance(outcome.error, ConnectionLostError)

    def test_connection_lost_at_stage_0(self, state):
        attack = _attack("atk", 2)
        device = FakeDevice(state, connection_drops={("atk", 0)})
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is False
        assert outcome.failed_stage == 0
        assert isinstance(outcome.error, ConnectionLostError)


class TestOrchestratorNoCompatibleAttack:
    def test_no_compatible_attack_returns_error_outcome(self, state):
        attack = Attack(
            id="ios15_only",
            name="iOS15 only",
            stages=[Stage("s0", "S0", 0.9)],
            compatible_models=["iPhone13,1"],
            min_ios=(15, 0), max_ios=(15, 9), min_battery=10,
        )
        device = FakeDevice(state)
        outcome = Orchestrator(device, [attack]).run()
        assert outcome.success is False
        assert outcome.attack is None
        assert isinstance(outcome.error, DeviceError)

    def test_empty_attack_list_returns_error_outcome(self, state):
        device = FakeDevice(state)
        outcome = Orchestrator(device, []).run()
        assert outcome.success is False
        assert isinstance(outcome.error, DeviceError)
