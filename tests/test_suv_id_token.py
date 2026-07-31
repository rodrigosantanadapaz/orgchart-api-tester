"""Tests for SUV ID token authentication (web layer only)."""

from __future__ import annotations

import base64
import httpx
import pytest

from webapp.suv_id_token import SuvAuthError, SuvIdTokenProvider

FAKE_TOKEN = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0ZXN0In0.sig"


def _basic(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def _handler(request: httpx.Request) -> httpx.Response:
    if request.headers.get("authorization") != _basic("superuser", "pw"):
        return httpx.Response(401, json={"error": "denied"})
    return httpx.Response(200, json={"encodedToken": FAKE_TOKEN})


def test_validate_fetches_id_token():
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    auth = SuvIdTokenProvider(
        "suv.example.com", "super", "superuser", "pw", client=client
    )
    auth.validate()
    assert auth.authorization_header(None) == f"ID {FAKE_TOKEN}"


def test_validate_rejects_bad_password():
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    auth = SuvIdTokenProvider(
        "suv.example.com", "super", "superuser", "wrong", client=client
    )
    with pytest.raises(SuvAuthError, match="not accepted"):
        auth.validate()


def test_clear_zeros_credentials():
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    auth = SuvIdTokenProvider(
        "suv.example.com", "super", "superuser", "pw", client=client
    )
    auth.validate()
    auth.clear()
    assert auth.authorization_header(None) is None
