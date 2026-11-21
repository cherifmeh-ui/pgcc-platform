import pytest
from types import SimpleNamespace

from app.services.security_logger import get_client_ip, get_user_agent


def test_client_ip_is_none_when_peer_missing():
    request = SimpleNamespace(headers={"x-forwarded-for": "198.51.100.8"}, client=None)
    assert get_client_ip(request) is None


def test_client_ip_ignores_forwarded_header():
    request = SimpleNamespace(
        headers={"x-forwarded-for": "198.51.100.8"},
        client=SimpleNamespace(host="192.0.2.10"),
    )
    assert get_client_ip(request) == "192.0.2.10"


def test_user_agent_is_bounded():
    request = SimpleNamespace(headers={"user-agent": "a" * 500}, client=None)
    assert get_user_agent(request) == "a" * 255


def test_missing_request_returns_none():
    assert get_client_ip(None) is None
    assert get_user_agent(None) is None
