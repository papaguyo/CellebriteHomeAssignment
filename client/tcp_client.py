from __future__ import annotations

import json
import socket

from framework.device import Device, DeviceState, ConnectionLostError
from framework.stage import StageResult

_ENCODING = "utf-8"
_RECV_SIZE = 4096


class SimulatedDeviceClient(Device):
    """
    TCP client that speaks the text-JSON protocol to the C simulator.

    Each public method sends one command and reads the response.
    Any socket error is translated to ConnectionLostError so the
    orchestrator can distinguish transport failures from stage failures.
    """

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self._timeout)
        sock.connect((self._host, self._port))
        self._sock = sock
        self._buf = b""

    def close(self) -> None:
        if self._sock:
            try:
                self._send("QUIT")
            except Exception:
                pass
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "SimulatedDeviceClient":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Device ABC
    # ------------------------------------------------------------------

    def get_state(self) -> DeviceState:
        raw = self._cmd("GET_STATE")
        d = json.loads(raw)
        return DeviceState(
            battery_level=d["battery"],
            ios_version=d["ios_version"],
            model=d["model"],
            is_locked=d["is_locked"],
        )

    def run_stage(self, attack_id: str, stage_index: int) -> StageResult:
        raw = self._cmd(f"RUN_STAGE {attack_id} {stage_index}")
        d = json.loads(raw)
        return StageResult(success=d["status"] == "SUCCESS", reason=d.get("reason", ""))

    def list_files(self, path: str) -> list[str]:
        raw = self._cmd(f"LIST {path}")
        d = json.loads(raw)
        return d["files"]

    def read_file(self, path: str) -> bytes:
        # Protocol: server sends size header line, then exactly size bytes.
        self._send(f"READ {path}")
        header = self._readline()
        d = json.loads(header)
        size = d["size"]
        return self._read_exactly(size)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cmd(self, command: str) -> str:
        self._send(command)
        return self._readline()

    def _send(self, text: str) -> None:
        try:
            assert self._sock is not None, "not connected"
            self._sock.sendall((text + "\n").encode(_ENCODING))
        except (OSError, AssertionError) as exc:
            raise ConnectionLostError(str(exc)) from exc

    def _readline(self) -> str:
        while b"\n" not in self._buf:
            try:
                chunk = self._sock.recv(_RECV_SIZE)  # type: ignore[union-attr]
            except OSError as exc:
                raise ConnectionLostError(str(exc)) from exc
            if not chunk:
                raise ConnectionLostError("server closed connection")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode(_ENCODING)

    def _read_exactly(self, n: int) -> bytes:
        data = self._buf[:n]
        self._buf = self._buf[n:]
        while len(data) < n:
            try:
                chunk = self._sock.recv(_RECV_SIZE)  # type: ignore[union-attr]
            except OSError as exc:
                raise ConnectionLostError(str(exc)) from exc
            if not chunk:
                raise ConnectionLostError("server closed connection mid-read")
            needed = n - len(data)
            data += chunk[:needed]
            self._buf = chunk[needed:] + self._buf
        return data
