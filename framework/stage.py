from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StageResult:
    success: bool
    reason: str = ""


@dataclass
class Stage:
    id: str
    name: str
    success_probability: float  # 0.0–1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.success_probability <= 1.0:
            raise ValueError(f"success_probability must be in [0, 1], got {self.success_probability}")
