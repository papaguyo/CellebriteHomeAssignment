from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ConnectionLostError(Exception):
    """Raised when the transport to the device drops unexpectedly."""


class DeviceError(Exception):
    """Raised for logical device-level errors (e.g. no compatible attack)."""


@dataclass
class DeviceState:
    battery_level: int   # 0–100
    ios_version: str     # e.g. "16.5"
    model: str           # e.g. "iPhone14,2"
    is_locked: bool


class Device(ABC):
    """Abstract interface that both the real TCP client and FakeDevice implement."""

    @abstractmethod
    def get_state(self) -> DeviceState: ...

    @abstractmethod
    def run_stage(self, attack_id: str, stage_index: int) -> "StageResult": ...

    @abstractmethod
    def list_files(self, path: str) -> list[str]: ...

    @abstractmethod
    def read_file(self, path: str) -> bytes: ...
