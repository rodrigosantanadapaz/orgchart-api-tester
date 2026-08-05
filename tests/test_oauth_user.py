"""OAuth user resolution (JWT sub + CCX /users/{sub})."""

from __future__ import annotations

import base64
import json

import httpx

from webapp.oauth_user import (
    AuthenticatedUser,
    decode_jwt_payload,
    extract_sub_from_authorization,
    fetch_user_profile_by_sub,
    resolve_authenticated_user,
)


def _jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header}.{body}.signature"


def test_decode_jwt_payload_and_extract_sub():
    sub = "74c95afec4d54603acfdb2d19ef65e7d"
    token = _jwt({"sub": sub, "org": "ORG"})
    claims = decode_jwt_payload(token)
    assert claims is not None
    assert claims["sub"] == sub
    assert extract_sub_from_authorization(f"Bearer {token}") == sub


def test_fetch_user_profile_by_sub_uses_users_endpoint():
    sub = "74c95afec4d54603acfdb2d19ef65e7d"
    token = _jwt({"sub": sub})
    seen_url = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_url.append(str(request.url))
        if f"/users/{sub}" in request.url.path:
            return httpx.Response(
                200,
                json={"id": sub, "name": "Rodrigo SO Role Assignees", "username": "wd-developer"},
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    body = fetch_user_profile_by_sub(
        "org.skylab.inday.io",
        "performance",
        sub,
        f"Bearer {token}",
        client=client,
        timeout=httpx.Timeout(5.0),
    )
    assert body is not None
    assert body["name"] == "Rodrigo SO Role Assignees"
    assert any("/ccx/api/v1/performance/users/" in url for url in seen_url)


def test_resolve_authenticated_user_returns_sub_and_name():
    sub = "74c95afec4d54603acfdb2d19ef65e7d"
    token = _jwt({"sub": sub})

    def handler(request: httpx.Request) -> httpx.Response:
        if f"/users/{sub}" in request.url.path:
            return httpx.Response(200, json={"name": "Rodrigo SO", "username": "persona_a"})
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    user = resolve_authenticated_user(
        f"Bearer {token}",
        host="org.skylab.inday.io",
        tenant="performance",
        client=client,
    )
    assert user.sub == sub
    assert user.display_name == "Rodrigo SO"
    assert user.login == "persona_a"
    assert user.label == "Rodrigo SO"


def test_resolve_returns_sub_when_profile_fetch_fails():
    sub = "74c95afec4d54603acfdb2d19ef65e7d"
    token = _jwt({"sub": sub})
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    user = resolve_authenticated_user(
        f"Bearer {token}",
        host="org.skylab.inday.io",
        tenant="performance",
        client=client,
    )
    assert user.sub == sub
    assert user.display_name is None
    assert user.label == sub


def test_authenticated_user_label_priority():
    user = AuthenticatedUser(sub="wid", display_name="Full Name", login="login")
    assert user.label == "Full Name"
