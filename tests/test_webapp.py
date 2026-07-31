import pytest
from fastapi.testclient import TestClient

from engine.catalog import ENDPOINTS
from webapp.app import create_app


@pytest.fixture
def client():
    # Fresh app (and fresh in-memory connection state) per test.
    return TestClient(create_app())


def _connect(client, **overrides):
    payload = {"host": "suv.example.com", "tenant": "super", "username": "oreynolds", "password": "pw"}
    payload.update(overrides)
    return client.post("/api/connect", json=payload)


# ------------------------------ catalog ------------------------------ #
def test_catalog_matches_engine(client):
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["categories"] == ["navigables", "hierarchy", "prompts"]
    assert len(data["endpoints"]) == len(ENDPOINTS)
    sample = data["endpoints"][0]
    for key in ("id", "method", "path", "category", "summary", "params", "response_type"):
        assert key in sample


def test_catalog_endpoint_ids_match(client):
    ids = {e["id"] for e in client.get("/api/catalog").json()["endpoints"]}
    assert ids == {e.id for e in ENDPOINTS}


# ------------------------------ connect ------------------------------ #
def test_connect_succeeds_and_hides_password(client):
    resp = _connect(client)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "connected"
    assert data["username"] == "oreynolds"
    assert "pw" not in resp.text  # password never echoed
    assert "password" not in data


def test_connect_requires_fields(client):
    resp = client.post("/api/connect", json={"host": "h", "tenant": "t", "username": "u"})
    assert resp.status_code == 422  # pydantic validation (missing password)


# ------------------------------ execute ------------------------------ #
def test_execute_requires_connection(client):
    resp = client.post("/api/execute", json={"endpoint_id": "list_navigables", "parameters": {}})
    assert resp.status_code == 409
    assert resp.json()["error"] == "Not connected"


def test_execute_builds_url_via_engine(client):
    _connect(client)
    resp = client.post("/api/execute", json={"endpoint_id": "get_navigable", "parameters": {"ID": "w1"}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == 200
    assert data["url"].endswith("/orgchart/v1/super/navigables/w1")
    assert data["method"] == "GET"
    assert data["persona"] == "oreynolds"
    assert data["body"]["_mock"] is True
    assert data["durationMs"] >= 0


def test_execute_request_headers_have_no_secrets(client):
    _connect(client)
    resp = client.post("/api/execute", json={"endpoint_id": "list_navigables", "parameters": {}})
    headers = {k.lower() for k in resp.json()["requestHeaders"]}
    assert "authorization" not in headers
    assert "cookie" not in headers
    assert "accept" in headers


def test_execute_repeatable_query(client):
    _connect(client)
    resp = client.post("/api/execute", json={
        "endpoint_id": "get_children",
        "parameters": {"ID": "p1", "navigableFilter": ["w1", "w2"]},
    })
    assert resp.status_code == 200
    url = resp.json()["url"]
    assert url.count("navigableFilter=") == 2
    assert "/navigables/p1/children" in url


def test_execute_missing_required_param(client):
    _connect(client)
    resp = client.post("/api/execute", json={"endpoint_id": "get_navigable", "parameters": {}})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"] == "Invalid parameters"
    assert any("ID" in d for d in body["detail"])


def test_execute_unknown_endpoint(client):
    _connect(client)
    resp = client.post("/api/execute", json={"endpoint_id": "nope", "parameters": {}})
    assert resp.status_code == 404
    assert resp.json()["error"] == "Unknown endpoint"


def test_disconnect_then_execute_blocked(client):
    _connect(client)
    assert client.post("/api/disconnect").json()["status"] == "disconnected"
    resp = client.post("/api/execute", json={"endpoint_id": "list_navigables", "parameters": {}})
    assert resp.status_code == 409


# ------------------------------ frontend ------------------------------ #
def test_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Org Chart API Tester" in resp.text


def test_static_js_served(client):
    resp = client.get("/static/js/main.js")
    assert resp.status_code == 200
    assert "class App" in resp.text
