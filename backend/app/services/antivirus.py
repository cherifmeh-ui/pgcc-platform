"""Fail-closed ClamAV scanner adapter using the clamd INSTREAM protocol."""
from __future__ import annotations

import asyncio
import struct

from app.core.config import settings


class AntivirusUnavailable(RuntimeError):
    """Raised when the configured antivirus service cannot be reached."""


class MalwareDetected(RuntimeError):
    """Raised when ClamAV reports a malware signature."""


async def scan_document_bytes(payload: bytes) -> None:
    """Scan a bounded in-memory upload. Never treats scanner failure as clean."""
    host = settings.CLAMAV_HOST.strip()
    if not host:
        raise AntivirusUnavailable("Service antivirus non configuré.")

    writer = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, settings.CLAMAV_PORT),
            timeout=settings.CLAMAV_TIMEOUT_SECONDS,
        )
        writer.write(b"zINSTREAM\\0")
        for offset in range(0, len(payload), 64 * 1024):
            chunk = payload[offset:offset + 64 * 1024]
            writer.write(struct.pack("!I", len(chunk)))
            writer.write(chunk)
        writer.write(struct.pack("!I", 0))
        await asyncio.wait_for(writer.drain(), timeout=settings.CLAMAV_TIMEOUT_SECONDS)
        response = await asyncio.wait_for(
            reader.readuntil(b"\\0"),
            timeout=settings.CLAMAV_TIMEOUT_SECONDS,
        )
        message = response.rstrip(b"\\0").decode("utf-8", errors="replace")
    except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
        raise AntivirusUnavailable("Service antivirus indisponible.") from exc
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    if message.endswith(" OK"):
        return
    if message.endswith(" FOUND"):
        raise MalwareDetected("Fichier malveillant détecté.")
    raise AntivirusUnavailable("Réponse antivirus invalide.")
