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


def test_skylab_live_connect_accepts_raw_jwt_access_token():
    jwt = "eyJhbGci.test.signature"
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    service = ExecutionService(mode="live", http_client=client)
    session = service.connect(
        "org.skylab.inday.io",
        "performance",
        "wd-developer",
        jwt,
    )
    assert session.auth.authorization_header(None) == f"Bearer {jwt}"
