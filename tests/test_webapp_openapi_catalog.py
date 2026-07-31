"""OpenAPI catalog probe for Skylab publication validation."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from webapp.app import create_app
from webapp.service import ExecutionService

TENANT_HUB = "/ccx/api/v1/performance/openapi.json"
ORGCHART_PUBLIC = "/ccx/api/orgchart/v1/performance/openapi.json"
ORGCHART_INTERNAL = "/ccx/internalapi/orgchart/v1/performance/openapi.json"


def _openapi_body(title: str, version: str) -> dict:
    return {
        "openapi": "3.0.1",
        "info": {"title": title, "version": version},
        "paths": {},
    }


def test_openapi_catalog_probe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return httpx.Response(401, json={"error": "Unauthorized"})
        if path == TENANT_HUB:
            return httpx.Response(
                200,
                json=_openapi_body("Tenant REST Hub", "v1"),
                headers={"content-type": "application/json"},
            )
        if path == ORGCHART_PUBLIC:
            return httpx.Response(404, json={"error": "not found"})
        if path == ORGCHART_INTERNAL:
            return httpx.Response(
                200,
                json=_openapi_body("orgchart", "v1"),
                headers={"content-type": "application/json"},
            )
        return httpx.Response(404, json={"error": "missing"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    service = ExecutionService(mode="live", http_client=http)
    client = TestClient(create_app(service))
    client.post(
        "/api/connect",
        json={
            "host": "org.skylab.inday.io",
            "username": "api-client",
            "password": "Bearer test-token",
            "tenant": "performance",
        },
    )
    resp = client.post("/api/openapi-catalog", json={"host": "org.skylab.inday.io"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["host"] == "org.skylab.inday.io"
    assert body["tenant"] == "performance"
    by_name = {item["name"]: item for item in body["results"]}
    assert by_name["tenant_hub"]["isOpenApiDocument"] is True
    assert by_name["tenant_hub"]["serviceTitle"] == "Tenant REST Hub"
    assert by_name["orgchart_public"]["isOpenApiDocument"] is False
    assert by_name["orgchart_public"]["status"] == 404
    assert by_name["orgchart_internal"]["isOpenApiDocument"] is True
    assert by_name["orgchart_internal"]["serviceTitle"] == "orgchart"
    assert "curlCommand" in by_name["orgchart_public"]
