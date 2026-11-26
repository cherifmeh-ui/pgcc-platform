"""Fail-closed client for the isolated document parser service."""
import json
import httpx

from app.core.config import settings


class ParserUnavailable(Exception):
    """The parser service could not be reached or did not respond safely."""


class ParserRejected(Exception):
    """The parser rejected the document or its extraction."""


MAX_RESULT_BYTES = 8 * 1024 * 1024


async def extract_document_text(data: bytes, filename: str) -> tuple[str, str]:
    base_url = settings.PARSER_BASE_URL.strip().rstrip("/")
    token = settings.PARSER_SHARED_TOKEN.strip()
    if not base_url or len(token) < 32:
        raise ParserUnavailable("Le service d'extraction isolé n'est pas configuré.")
    timeout = httpx.Timeout(connect=2.0, read=25.0, write=10.0, pool=2.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            async with client.stream(
                "POST",
                f"{base_url}/v1/extract",
                headers={"X-Parser-Token": token},
                files={"file": (filename, data, "application/octet-stream")},
            ) as response:
                if response.status_code != 200:
                    body = (await response.aread())[:2048].decode("utf-8", "replace")
                    if response.status_code in {400, 413, 415, 408}:
                        raise ParserRejected(f"Extraction refusée ({response.status_code}).")
                    raise ParserUnavailable(f"Service d'extraction indisponible ({response.status_code}).")
                chunks = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_RESULT_BYTES:
                        raise ParserUnavailable("Réponse du parseur trop volumineuse.")
                    chunks.append(chunk)
        payload = json.loads(b"".join(chunks))
        text = payload.get("text")
        detected_format = payload.get("detected_format")
        if not isinstance(text, str) or not text or detected_format not in {"PDF", "DOCX"}:
            raise ParserUnavailable("Réponse invalide du service d'extraction.")
        return text, detected_format
    except (ParserRejected, ParserUnavailable):
        raise
    except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ParserUnavailable("Échec de communication avec le service d'extraction.") from exc
