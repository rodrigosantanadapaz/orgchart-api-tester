"""OAuth refresh-token exchange for SkyLab / public REST."""

from __future__ import annotations

import httpx
import pytest

from webapp.oauth_token import OAuthTokenError, exchange_refresh_token, token_url_from_resolved
from webapp.service import ExecutionService


def test_token_url_from_resolved_uses_config_template():
    resolved = {
        "auth": {"tokenUrlTemplate": "https://{host}/ccx/oauth2/{tenant}/token"},
    }
    assert (
        token_url_from_resolved(resolved, "org.skylab.inday.io", "performance")
        == "https://org.skylab.inday.io/ccx/oauth2/performance/token"
    )


def test_exchange_refresh_token_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/ccx/oauth2/performance/token")
        assert request.headers.get("authorization", "").startswith("Basic ")
        body = request.content.decode()
        assert "grant_type=refresh_token" in body
        assert "refresh_token=rt-abc" in body
        return httpx.Response(
            200,
            json={"access_token": "access-xyz", "token_type": "Bearer", "expires_in": 3600},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    authorization, expires = exchange_refresh_token(
        "https://org.skylab.inday.io/ccx/oauth2/performance/token",
        "client-id",
        "client-secret",
        "rt-abc",
        client=client,
    )
    assert authorization == "Bearer access-xyz"
    assert expires == 3600.0


def test_exchange_refresh_token_invalid_client():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "invalid_client"}))
    )
    with pytest.raises(OAuthTokenError, match="401"):
        exchange_refresh_token(
            "https://example.com/token",
            "bad",
            "bad",
            "rt",
            client=client,
        )


def test_service_exchange_oauth_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "tok", "expires_in": 900})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = ExecutionService(mode="live", http_client=client)
    authorization, expires = service.exchange_oauth_token(
        "org.skylab.inday.io",
        "performance",
        "cid",
        "csecret",
        "refresh",
    )
    assert authorization == "Bearer tok"
    assert expires == 900.0
