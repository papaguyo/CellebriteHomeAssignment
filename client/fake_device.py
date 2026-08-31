from __future__ import annotations

import posixpath

from framework.device import Device, DeviceState, ConnectionLostError
from framework.stage import StageResult


class FakeDevice(Device):
    """
    In-memory device for unit tests. No subprocess or network required.

    stage_results: maps (attack_id, stage_index) -> bool (True=success)
    connection_drops: set of (attack_id, stage_index) that raise ConnectionLostError
    files: maps absolute path -> bytes content; directories are inferred from paths
    """

    def __init__(
        self,
        state: DeviceState,
        stage_results: dict[tuple[str, int], bool] | None = None,
        files: dict[str, bytes] | None = None,
        connection_drops: set[tuple[str, int]] | None = None,
    ) -> None:
        self._state = state
        self._stage_results: dict[tuple[str, int], bool] = stage_results or {}
        self._files: dict[str, bytes] = files or {}
        self._connection_drops: set[tuple[str, int]] = connection_drops or set()

    def get_state(self) -> DeviceState:
        return self._state

    def run_stage(self, attack_id: str, stage_index: int) -> StageResult:
        key = (attack_id, stage_index)
        if key in self._connection_drops:
            raise ConnectionLostError(f"simulated drop at {key}")
        success = self._stage_results.get(key, True)
        return StageResult(success=success, reason="" if success else "simulated failure")

    def list_files(self, path: str) -> list[str]:
        """Return immediate children of path (files AND inferred subdirectories)."""
        norm = path.rstrip("/") or "/"
        prefix = "/" if norm == "/" else norm + "/"
        children: set[str] = set()
        for fpath in self._files:
            if not fpath.startswith(prefix):
                continue
            rest = fpath[len(prefix):]
            first = rest.split("/")[0]
            if first:
                children.add(first)
        return sorted(children)

    def read_file(self, path: str) -> bytes:
        if path not in self._files:
            raise FileNotFoundError(f"no such file: {path}")
        return self._files[path]
