from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce
from operator import mul

from .device import DeviceState
from .stage import Stage


def parse_ios(version: str) -> tuple[int, int]:
    """Parse "16.5" → (16, 5). Handles "16" → (16, 0)."""
    parts = version.split(".")
    major = int(parts[0])
    minor = int(parts[1]) if len(parts) > 1 else 0
    return (major, minor)


@dataclass
class Attack:
    id: str
    name: str
    stages: list[Stage]
    compatible_models: list[str]  # e.g. ["iPhone14,2", "iPhone14,3"]
    min_ios: tuple[int, int]      # inclusive, e.g. (16, 0)
    max_ios: tuple[int, int]      # inclusive, e.g. (16, 5)
    min_battery: int              # minimum battery % required
    is_destructive: bool = False
    priority: int = 0  # lower = higher priority; 0 = unranked

    @property
    def estimated_success_probability(self) -> float:
        if not self.stages:
            return 0.0
        return reduce(mul, (s.success_probability for s in self.stages), 1.0)

    def is_compatible(self, state: DeviceState) -> bool:
        if self.compatible_models and state.model not in self.compatible_models:
            return False
        if state.battery_level < self.min_battery:
            return False
        ios = parse_ios(state.ios_version)
        if ios < self.min_ios or ios > self.max_ios:
            return False
        return True
