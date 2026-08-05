"""Webapp environment detection for REST base URL selection."""

from __future__ import annotations

import httpx
import pytest

from webapp.service import ExecutionService, environment_key_for_host
from webapp.suv_id_token import SuvAuthError


def test_environment_key_for_skylab_host():
    assert environment_key_for_host("org.skylab.inday.io") == "skylab"


def test_environment_key_for_suv_host():
    assert environment_key_for_host("i-0abc.workdaysuv.com") == "suv"


def test_resolved_skylab_uses_internal_api_surface():
    service = ExecutionService()
    resolved = service._resolved_for("org.skylab.inday.io", "performance")
    assert resolved["restBaseTemplate"] == "https://{host}/ccx/internalapi/orgchart/v1/{tenant}"
    assert resolved["tenant"] == "performance"
    assert resolved["host"] == "org.skylab.inday.io"


def test_resolved_suv_uses_internal_api_surface():
    service = ExecutionService()
    resolved = service._resolved_for("i-0abc.workdaysuv.com", "super")
    assert "internalapi" in resolved["restBaseTemplate"]
    assert resolved["tenant"] == "super"


def test_skylab_live_connect_requires_bearer_token():
    service = ExecutionService(mode="live")
    with pytest.raises(SuvAuthError, match="Bearer"):
        service.connect(
            "org.skylab.inday.io",
            "performance",
            "wd-developer",
            "plain-login-password",
        )


def test_skylab_live_connect_ignores_username_with_bearer():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    service = ExecutionService(mode="live", http_client=client)
    session = service.connect(
        "org.skylab.inday.io",
        "performance",
        "not-a-real-user",
        "Bearer test-token",
    )
    assert session.username == "oauth"
    assert session.auth.authorization_header(None) == "Bearer test-token"


def test_skylab_live_connect_extracts_identity_from_jwt():
    import base64
    import json

    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(
        json.dumps({"sub": "wd-developer@performance"}).encode()
    ).decode().rstrip("=")
    jwt = f"{header}.{body}.signature"
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    service = ExecutionService(mode="live", http_client=client)
    session = service.connect(
        "org.skylab.inday.io",
        "performance",
        "oauth",
        jwt,
    )
    assert session.username == "oauth"
    assert session.identity == "wd-developer"


def test_skylab_live_connect_resolves_identity_from_users_me():
    import base64
    import json

    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(
        json.dumps({"sub": "eca89d2b3b1d1031988ee96a23920000"}).encode()
    ).decode().rstrip("=")
    jwt = f"{header}.{body}.signature"

    def handler(request: httpx.Request) -> httpx.Response:
        if "/users/eca89d2b3b1d1031988ee96a23920000" in request.url.path:
            return httpx.Response(200, json={"name": "Rodrigo SO"})
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = ExecutionService(mode="live", http_client=client)
    session = service.connect(
        "org.skylab.inday.io",
        "performance",
        "oauth",
        jwt,
    )
    assert session.identity == "Rodrigo SO"
    assert session.user_sub == "eca89d2b3b1d1031988ee96a23920000"
