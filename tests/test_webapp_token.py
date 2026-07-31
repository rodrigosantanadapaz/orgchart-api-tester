"""Web API token exchange endpoint."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from webapp.app import create_app
from webapp.service import ExecutionService


def test_token_endpoint_returns_bearer_header():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "abc123", "expires_in": 1200})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = ExecutionService(mode="live", http_client=client)
    app_client = TestClient(create_app(service))

    resp = app_client.post(
        "/api/token",
        json={
            "host": "org.skylab.inday.io",
            "tenant": "performance",
            "client_id": "cid",
            "client_secret": "secret",
            "refresh_token": "refresh",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["authorization"] == "Bearer abc123"
    assert data["expiresIn"] == 1200
    assert "secret" not in resp.text
    assert "refresh" not in resp.text


def test_token_endpoint_requires_fields():
    app_client = TestClient(create_app())
    resp = app_client.post(
        "/api/token",
        json={"host": "h", "tenant": "t", "client_id": "c"},
    )
    assert resp.status_code == 422
