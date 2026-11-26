import json

import httpx
import pytest

from app.core.config import settings
from app.services import isolated_parser_client as parser


def _client_with_response(monkeypatch, response):
    async def handler(_request):
        return response

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(parser.httpx, "AsyncClient", factory)
    monkeypatch.setattr(settings, "PARSER_BASE_URL", "http://parser:8090")
    monkeypatch.setattr(settings, "PARSER_SHARED_TOKEN", "t" * 48)


@pytest.mark.asyncio
async def test_isolated_parser_client_returns_validated_extraction(monkeypatch):
    response = httpx.Response(
        200,
        json={"text": "Politique de sécurité", "detected_format": "DOCX"},
    )
    _client_with_response(monkeypatch, response)
    result = await parser.extract_document_text(b"PK-test", "policy.docx")
    assert result == ("Politique de sécurité", "DOCX")


@pytest.mark.asyncio
async def test_isolated_parser_client_fails_closed_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "PARSER_BASE_URL", "")
    monkeypatch.setattr(settings, "PARSER_SHARED_TOKEN", "")
    with pytest.raises(parser.ParserUnavailable):
        await parser.extract_document_text(b"%PDF-test", "policy.pdf")


@pytest.mark.asyncio
async def test_isolated_parser_client_fails_closed_on_service_error(monkeypatch):
    _client_with_response(monkeypatch, httpx.Response(503, text="unavailable"))
    with pytest.raises(parser.ParserUnavailable):
        await parser.extract_document_text(b"%PDF-test", "policy.pdf")


@pytest.mark.asyncio
async def test_isolated_parser_client_rejects_invalid_response(monkeypatch):
    response = httpx.Response(200, json={"text": "", "detected_format": "EXE"})
    _client_with_response(monkeypatch, response)
    with pytest.raises(parser.ParserUnavailable):
        await parser.extract_document_text(b"%PDF-test", "policy.pdf")
