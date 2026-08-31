"""Unit tests for Extractor — uses FakeDevice, no subprocess."""
from __future__ import annotations

import pytest

from client.fake_device import FakeDevice
from framework.device import DeviceState
from framework.extractor import Extractor


@pytest.fixture
def state() -> DeviceState:
    return DeviceState(battery_level=80, ios_version="16.5", model="iPhone14,2", is_locked=True)


@pytest.fixture
def device_with_files(state: DeviceState) -> FakeDevice:
    return FakeDevice(
        state=state,
        files={
            "/contacts.db": b"contacts",
            "/media/photo1.jpg": b"jpg1",
            "/media/photo2.jpg": b"jpg2",
            "/logs/system.log": b"logdata",
        },
    )


class TestExtractorRead:
    def test_read_existing_file(self, device_with_files: FakeDevice):
        ex = Extractor(device_with_files)
        assert ex.read("/contacts.db") == b"contacts"

    def test_read_nested_file(self, device_with_files: FakeDevice):
        ex = Extractor(device_with_files)
        assert ex.read("/media/photo1.jpg") == b"jpg1"

    def test_read_missing_file_raises(self, device_with_files: FakeDevice):
        ex = Extractor(device_with_files)
        with pytest.raises(FileNotFoundError):
            ex.read("/nonexistent.txt")


class TestExtractAll:
    def test_extract_all_returns_all_files(self, device_with_files: FakeDevice):
        ex = Extractor(device_with_files)
        result = ex.extract_all("/")
        assert set(result.keys()) == {
            "/contacts.db",
            "/media/photo1.jpg",
            "/media/photo2.jpg",
            "/logs/system.log",
        }

    def test_extract_all_file_contents_correct(self, device_with_files: FakeDevice):
        ex = Extractor(device_with_files)
        result = ex.extract_all("/")
        assert result["/contacts.db"] == b"contacts"
        assert result["/media/photo1.jpg"] == b"jpg1"
        assert result["/logs/system.log"] == b"logdata"

    def test_extract_subtree(self, device_with_files: FakeDevice):
        ex = Extractor(device_with_files)
        result = ex.extract_all("/media")
        assert set(result.keys()) == {"/media/photo1.jpg", "/media/photo2.jpg"}

    def test_extract_single_file_path(self, state: DeviceState):
        device = FakeDevice(state=state, files={"/only.txt": b"hello"})
        ex = Extractor(device)
        result = ex.extract_all("/")
        assert result == {"/only.txt": b"hello"}

    def test_extract_empty_device(self, state: DeviceState):
        device = FakeDevice(state=state, files={})
        ex = Extractor(device)
        result = ex.extract_all("/")
        # Root has no children and is not a file → empty dict
        assert result == {}
