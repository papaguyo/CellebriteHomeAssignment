from __future__ import annotations

import logging
import posixpath

from .device import Device

logger = logging.getLogger(__name__)


class Extractor:
    """
    Reads files from a device after a successful attack.

    list_files() is used for directory traversal; read_file() fetches content.
    The device distinguishes files from directories by whether list_files()
    returns children: an empty list means it IS a file (or empty dir).
    The simulator protocol makes directories explicit by returning their children.
    """

    def __init__(self, device: Device) -> None:
        self.device = device

    def read(self, path: str) -> bytes:
        return self.device.read_file(path)

    def extract_all(self, root: str = "/") -> dict[str, bytes]:
        result: dict[str, bytes] = {}
        self._walk(root, result)
        total_bytes = sum(len(v) for v in result.values())
        logger.info("extract_all: %d file%s, %d bytes total",
                    len(result), "s" if len(result) != 1 else "", total_bytes)
        return result

    def _walk(self, path: str, result: dict[str, bytes]) -> None:
        children = self.device.list_files(path)
        if not children:
            # Leaf node — read as a file. Silently skip if the path turns out
            # to be an empty directory (e.g. the root of a device with no files).
            try:
                data = self.device.read_file(path)
                logger.debug("  extracted %s (%d B)", path, len(data))
                result[path] = data
            except FileNotFoundError:
                pass
        else:
            for name in children:
                child_path = posixpath.join(path, name) if path != "/" else "/" + name
                self._walk(child_path, result)
