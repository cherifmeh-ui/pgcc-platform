import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services import antivirus


@pytest.mark.asyncio
async def test_scanner_requires_configuration(monkeypatch):
    monkeypatch.setattr(antivirus.settings, "CLAMAV_HOST", "")
    with pytest.raises(antivirus.AntivirusUnavailable):
        await antivirus.scan_document_bytes(b"file")


@pytest.mark.asyncio
async def test_scanner_accepts_clean_verdict(monkeypatch):
    class Reader:
        async def readuntil(self, separator):
            assert separator == b"\\0"
            return b"stream: OK\\0"

    class Writer:
        def __init__(self):
            self.data = bytearray()
            self.closed = False
        def write(self, data):
            self.data.extend(data)
        async def drain(self):
            return None
        def close(self):
            self.closed = True
        async def wait_closed(self):
            return None

    writer = Writer()
    monkeypatch.setattr(antivirus.settings, "CLAMAV_HOST", "clamav")
    monkeypatch.setattr(antivirus.settings, "CLAMAV_PORT", 3310)
    monkeypatch.setattr(
        antivirus.asyncio, "open_connection",
        AsyncMock(return_value=(Reader(), writer)),
    )
    await antivirus.scan_document_bytes(b"clean payload")
    assert b"zINSTREAM\\0" in writer.data
    assert writer.closed


@pytest.mark.asyncio
async def test_scanner_rejects_malware_verdict(monkeypatch):
    class Reader:
        async def readuntil(self, separator):
            return b"stream: Eicar-Test-Signature FOUND\\0"

    class Writer:
        def write(self, data): pass
        async def drain(self): pass
        def close(self): pass
        async def wait_closed(self): pass

    monkeypatch.setattr(antivirus.settings, "CLAMAV_HOST", "clamav")
    monkeypatch.setattr(
        antivirus.asyncio, "open_connection",
        AsyncMock(return_value=(Reader(), Writer())),
    )
    with pytest.raises(antivirus.MalwareDetected):
        await antivirus.scan_document_bytes(b"infected")


@pytest.mark.asyncio
async def test_scanner_fails_closed_on_connection_error(monkeypatch):
    monkeypatch.setattr(antivirus.settings, "CLAMAV_HOST", "clamav")
    monkeypatch.setattr(
        antivirus.asyncio, "open_connection",
        AsyncMock(side_effect=OSError("offline")),
    )
    with pytest.raises(antivirus.AntivirusUnavailable):
        await antivirus.scan_document_bytes(b"payload")
