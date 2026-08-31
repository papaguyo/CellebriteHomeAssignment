from __future__ import annotations

from abc import ABC, abstractmethod

from .attack import Attack
from .device import DeviceState

__all__ = ["Selector"]


class Selector(ABC):
    """Strategy interface for choosing which attack to run."""

    @abstractmethod
    def select(self, attacks: list[Attack], state: DeviceState) -> Attack | None: ...
