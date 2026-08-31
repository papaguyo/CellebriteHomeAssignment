"""Unit tests for the ProbabilitySelector — no device, no subprocess."""
from __future__ import annotations

import pytest

from framework.attack import Attack
from framework.device import DeviceState
from framework.selector import ProbabilitySelector
from framework.stage import Stage


def make_attack(id: str, prob: float, n_stages: int, models: list[str], destructive: bool = False) -> Attack:
    stages = [Stage(id=f"s{i}", name=f"Stage {i}", success_probability=prob) for i in range(n_stages)]
    return Attack(
        id=id,
        name=id,
        stages=stages,
        compatible_models=models,
        min_ios=(16, 0),
        max_ios=(16, 9),
        min_battery=20,
        is_destructive=destructive,
    )


@pytest.fixture
def state() -> DeviceState:
    return DeviceState(battery_level=80, ios_version="16.5", model="iPhone14,2", is_locked=True)


@pytest.fixture
def selector() -> ProbabilitySelector:
    return ProbabilitySelector()


class TestProbabilitySelector:
    def test_picks_highest_probability(self, selector, state):
        low  = make_attack("low",  0.3, 1, ["iPhone14,2"])
        high = make_attack("high", 0.9, 1, ["iPhone14,2"])
        result = selector.select([low, high], state)
        assert result is not None
        assert result.id == "high"

    def test_tie_broken_by_fewer_stages(self, selector, state):
        # Both have the same estimated probability (0.81 each)
        two_stage = make_attack("two_stage", 0.9, 2, ["iPhone14,2"])  # 0.9^2 = 0.81
        three_stage = make_attack("three_stage", 0.9327, 3, ["iPhone14,2"])  # ~0.81 but more stages
        # Give them literally equal probability
        one_stage_81 = Attack(
            id="one_stage_81",
            name="one_stage_81",
            stages=[Stage("s0", "S0", 0.81)],
            compatible_models=["iPhone14,2"],
            min_ios=(16, 0), max_ios=(16, 9), min_battery=20,
        )
        two_stage_eq = Attack(
            id="two_stage_eq",
            name="two_stage_eq",
            stages=[Stage("s0", "S0", 0.9), Stage("s1", "S1", 0.9)],
            compatible_models=["iPhone14,2"],
            min_ios=(16, 0), max_ios=(16, 9), min_battery=20,
        )
        # one_stage_81 prob = 0.81, two_stage_eq prob = 0.81 → fewer stages wins
        result = selector.select([two_stage_eq, one_stage_81], state)
        assert result is not None
        assert result.id == "one_stage_81"

    def test_incompatible_model_excluded(self, selector, state):
        wrong_model = make_attack("wrong", 0.99, 1, ["iPhone13,1"])
        result = selector.select([wrong_model], state)
        assert result is None

    def test_all_incompatible_returns_none(self, selector, state):
        attacks = [
            make_attack("a", 0.9, 1, ["iPhone13,1"]),
            make_attack("b", 0.8, 1, ["iPhone13,2"]),
        ]
        assert selector.select(attacks, state) is None

    def test_single_compatible_returned(self, selector, state):
        a = make_attack("only", 0.5, 2, ["iPhone14,2"])
        result = selector.select([a], state)
        assert result is not None
        assert result.id == "only"

    def test_battery_too_low_excluded(self, selector):
        low_battery_state = DeviceState(battery_level=5, ios_version="16.5", model="iPhone14,2", is_locked=True)
        a = Attack(
            id="needs_battery",
            name="needs_battery",
            stages=[Stage("s0", "S0", 0.9)],
            compatible_models=["iPhone14,2"],
            min_ios=(16, 0), max_ios=(16, 9),
            min_battery=20,
        )
        assert selector.select([a], low_battery_state) is None

    def test_ios_version_out_of_range_excluded(self, selector):
        ios17_state = DeviceState(battery_level=80, ios_version="17.0", model="iPhone14,2", is_locked=True)
        a = make_attack("ios16_only", 0.9, 1, ["iPhone14,2"])  # max_ios=(16,9)
        assert selector.select([a], ios17_state) is None

    def test_destructive_loses_to_non_destructive_at_equal_probability(self, selector, state):
        safe       = make_attack("safe",       0.9, 1, ["iPhone14,2"], destructive=False)
        destructive = make_attack("destructive", 0.9, 1, ["iPhone14,2"], destructive=True)
        result = selector.select([destructive, safe], state)
        assert result is not None
        assert result.id == "safe"
