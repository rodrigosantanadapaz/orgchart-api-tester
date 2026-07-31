"""Upstream control probe (staffing vs orgchart) using session auth."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from webapp.app import create_app
from webapp.service import ExecutionService


def test_probe_requires_connection():
    client = TestClient(create_app())
    resp = client.post("/api/probe")
    assert resp.status_code == 409


def test_probe_reports_staffing_and_orgchart_status():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if "/staffing/" in request.url.path:
            return httpx.Response(
                200,
                json={"total": 1, "data": []},
                headers={"wd-stat-request-id": "abc"},
            )
        if "/internalapi/" in request.url.path:
            return httpx.Response(200, json={"total": 1, "data": []})
        return httpx.Response(400, json={"error": "Invalid request"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    service = ExecutionService(mode="live", http_client=http)
    app_client = TestClient(create_app(service))
    app_client.post(
        "/api/connect",
        json={
            "host": "i-0abc.workdaysuv.com",
            "tenant": "super",
            "username": "superuser",
            "password": "Bearer test-token",
        },
    )
    resp = app_client.post("/api/probe")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["probes"]) == 5
    by_name = {p["name"]: p for p in data["probes"]}
    assert by_name["staffing"]["status"] == 200
    assert by_name["orgchart_public"]["status"] == 400
    assert by_name["orgchart_routed"]["status"] == 200
    assert by_name["orgchart_internal_prompt"]["status"] == 200
    assert by_name["orgchart_internal_navigable"]["status"] == 200
    assert "orgchart works" in data["summary"].lower()
