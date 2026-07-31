"""Live execution mode wiring for the web layer (no real network)."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from webapp.app import create_app
from webapp.service import ExecutionService

SECRET_PW = "s3cr3t-pw"
FAKE_ID_TOKEN = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0ZXN0In0.sig"


def _live_handler(request: httpx.Request) -> httpx.Response:
    if "authIdToken" in str(request.url):
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Basic "):
            return httpx.Response(401, json={"error": "denied"})
        return httpx.Response(200, json={"encodedToken": FAKE_ID_TOKEN})
    auth = request.headers.get("authorization", "")
    if not auth.startswith("ID "):
        return httpx.Response(401, json={"error": "Unauthorized"})
    return httpx.Response(200, json={"live": True, "path": request.url.path})


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def live_client():
    client = httpx.Client(transport=httpx.MockTransport(_live_handler))
    service = ExecutionService(mode="live", http_client=client)
    with TestClient(create_app(service=service)) as tc:
        yield tc


def _connect(client: TestClient, **overrides):
    payload = {
        "host": "suv.example.com",
        "tenant": "super",
        "username": "oreynolds",
        "password": SECRET_PW,
    }
    payload.update(overrides)
    return client.post("/api/connect", json=payload)


# ------------------------------ config / mode ------------------------------ #
def test_config_reports_mode(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "mock"
    assert data["modes"] == ["mock", "live"]


def test_set_mode_when_idle(client):
    resp = client.post("/api/mode", json={"mode": "live"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "live"


def test_set_mode_rejects_unknown(client):
    resp = client.post("/api/mode", json={"mode": "oauth"})
    assert resp.status_code == 422
    assert resp.json()["error"] == "Invalid mode"


def test_set_mode_blocked_while_connected(client):
    _connect(client)
    resp = client.post("/api/mode", json={"mode": "live"})
    assert resp.status_code == 409
    assert resp.json()["error"] == "Already connected"


def test_config_reports_active_connection(client):
    _connect(client, username="alice", host="org.skylab.inday.io", tenant="performance")
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["host"] == "org.skylab.inday.io"
    assert data["tenant"] == "performance"
    assert data["username"] == "alice"


# ------------------------------ live connect / execute --------------------- #
def test_live_connect_reports_mode(live_client):
    resp = _connect(live_client)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "live"
    assert SECRET_PW not in resp.text
    assert "password" not in data


def test_live_execute_uses_httpx_transport(live_client):
    _connect(live_client)
    resp = live_client.post(
        "/api/execute",
        json={"endpoint_id": "list_navigables", "parameters": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["body"]["live"] is True
    assert "_mock" not in data["body"]
    assert data["status"] == 200
    assert "/navigables" in data["url"]


def test_live_execute_hides_authorization_in_display_headers(live_client):
    _connect(live_client)
    resp = live_client.post(
        "/api/execute",
        json={"endpoint_id": "list_navigables", "parameters": {}},
    )
    headers = {k.lower() for k in resp.json()["requestHeaders"]}
    assert "authorization" not in headers
    assert SECRET_PW not in resp.text


def test_live_disconnect_clears_session(live_client):
    _connect(live_client)
    assert live_client.post("/api/disconnect").status_code == 200
    resp = live_client.post(
        "/api/execute",
        json={"endpoint_id": "list_navigables", "parameters": {}},
    )
    assert resp.status_code == 409


def test_mock_mode_still_available_after_live_service_fixture(live_client):
    """Mock responses remain available when the service is constructed in mock mode."""
    service = ExecutionService(mode="mock")
    with TestClient(create_app(service=service)) as client:
        _connect(client)
        resp = client.post(
            "/api/execute",
            json={"endpoint_id": "list_navigables", "parameters": {}},
        )
        assert resp.status_code == 200
        assert resp.json()["body"]["_mock"] is True
