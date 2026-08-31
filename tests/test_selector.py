"""Unit tests for all selector implementations — no device, no subprocess."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from framework.attack import Attack
from framework.device import DeviceState
from framework.selectors import ProbabilitySelector, PrioritySelector, WeightedRandomSelector
from framework.stage import Stage


def make_attack(
    id: str,
    prob: float,
    n_stages: int,
    models: list[str],
    destructive: bool = False,
    priority: int = 0,
) -> Attack:
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
        priority=priority,
    )


@pytest.fixture
def state() -> DeviceState:
    return DeviceState(battery_level=80, ios_version="16.5", model="iPhone14,2", is_locked=True)


# ---------------------------------------------------------------------------
# ProbabilitySelector
# ---------------------------------------------------------------------------

class TestProbabilitySelector:
    @pytest.fixture
    def selector(self) -> ProbabilitySelector:
        return ProbabilitySelector()

    def test_picks_highest_probability(self, selector, state):
        low  = make_attack("low",  0.3, 1, ["iPhone14,2"])
        high = make_attack("high", 0.9, 1, ["iPhone14,2"])
        result = selector.select([low, high], state)
        assert result is not None
        assert result.id == "high"

    def test_tie_broken_by_fewer_stages(self, selector, state):
        one_stage_81 = Attack(
            id="one_stage_81", name="one_stage_81",
            stages=[Stage("s0", "S0", 0.81)],
            compatible_models=["iPhone14,2"],
            min_ios=(16, 0), max_ios=(16, 9), min_battery=20,
        )
        two_stage_eq = Attack(
            id="two_stage_eq", name="two_stage_eq",
            stages=[Stage("s0", "S0", 0.9), Stage("s1", "S1", 0.9)],
            compatible_models=["iPhone14,2"],
            min_ios=(16, 0), max_ios=(16, 9), min_battery=20,
        )
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
            id="needs_battery", name="needs_battery",
            stages=[Stage("s0", "S0", 0.9)],
            compatible_models=["iPhone14,2"],
            min_ios=(16, 0), max_ios=(16, 9), min_battery=20,
        )
        assert selector.select([a], low_battery_state) is None

    def test_ios_version_out_of_range_excluded(self, selector):
        ios17_state = DeviceState(battery_level=80, ios_version="17.0", model="iPhone14,2", is_locked=True)
        a = make_attack("ios16_only", 0.9, 1, ["iPhone14,2"])
        assert selector.select([a], ios17_state) is None

    def test_destructive_loses_to_non_destructive_at_equal_probability(self, selector, state):
        safe        = make_attack("safe",        0.9, 1, ["iPhone14,2"], destructive=False)
        destructive = make_attack("destructive", 0.9, 1, ["iPhone14,2"], destructive=True)
        result = selector.select([destructive, safe], state)
        assert result is not None
        assert result.id == "safe"


# ---------------------------------------------------------------------------
# PrioritySelector
# ---------------------------------------------------------------------------

class TestPrioritySelector:
    @pytest.fixture
    def selector(self) -> PrioritySelector:
        return PrioritySelector()

    def test_lower_priority_number_wins_over_higher_probability(self, selector, state):
        # priority=1 with low prob beats priority=2 with high prob
        high_prob_low_prio = make_attack("high_p", 0.95, 1, ["iPhone14,2"], priority=2)
        low_prob_high_prio = make_attack("low_p",  0.50, 1, ["iPhone14,2"], priority=1)
        result = selector.select([high_prob_low_prio, low_prob_high_prio], state)
        assert result is not None
        assert result.id == "low_p"

    def test_tie_in_priority_broken_by_higher_probability(self, selector, state):
        a = make_attack("a", 0.6, 1, ["iPhone14,2"], priority=1)
        b = make_attack("b", 0.9, 1, ["iPhone14,2"], priority=1)
        result = selector.select([a, b], state)
        assert result is not None
        assert result.id == "b"

    def test_priority_zero_treated_as_unranked_goes_last(self, selector, state):
        unranked = make_attack("unranked", 0.99, 1, ["iPhone14,2"], priority=0)
        ranked   = make_attack("ranked",   0.10, 1, ["iPhone14,2"], priority=1)
        result = selector.select([unranked, ranked], state)
        assert result is not None
        assert result.id == "ranked"

    def test_all_incompatible_returns_none(self, selector, state):
        a = make_attack("a", 0.9, 1, ["iPhone13,1"], priority=1)
        assert selector.select([a], state) is None

    def test_empty_models_compatible_with_any_device(self, selector, state):
        universal = make_attack("universal", 0.7, 1, [], priority=1)
        result = selector.select([universal], state)
        assert result is not None
        assert result.id == "universal"


# ---------------------------------------------------------------------------
# WeightedRandomSelector
# ---------------------------------------------------------------------------

class TestWeightedRandomSelector:
    @pytest.fixture
    def selector(self) -> WeightedRandomSelector:
        return WeightedRandomSelector()

    def test_returns_attack_chosen_by_random_choices(self, selector, state):
        a = make_attack("a", 0.9, 1, ["iPhone14,2"])
        b = make_attack("b", 0.5, 1, ["iPhone14,2"])
        with patch("framework.selectors.weighted_random_selector.random.choices", return_value=[b]):
            result = selector.select([a, b], state)
        assert result is not None
        assert result.id == "b"

    def test_only_compatible_attacks_are_candidates(self, selector, state):
        compatible   = make_attack("ok",  0.8, 1, ["iPhone14,2"])
        incompatible = make_attack("bad", 0.9, 1, ["iPhone13,1"])
        captured: list = []

        def fake_choices(population, weights, k):
            captured.extend(population)
            return [population[0]]

        with patch("framework.selectors.weighted_random_selector.random.choices", side_effect=fake_choices):
            selector.select([compatible, incompatible], state)

        assert all(a.id == "ok" for a in captured)

    def test_all_incompatible_returns_none(self, selector, state):
        a = make_attack("a", 0.9, 1, ["iPhone13,1"])
        assert selector.select([a], state) is None
