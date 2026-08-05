"""Resolve the authenticated Skylab/CCX user from a Bearer OAuth access token.

Official flow (Skylab OAuth):
  1. Decode JWT payload → extract ``sub`` (user ID, e.g. ``74c95afec4d54603acfdb2d19ef65e7d``).
  2. ``GET /ccx/api/v1/{tenant}/users/{sub}`` with ``Authorization: Bearer <token>``.
  3. Read ``name`` (then ``fullName``, ``descriptor``, ``username``) for display.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx

_WID_DOLLAR = re.compile(r"^\d+\$\d+$")

_DISPLAY_NAME_KEYS = ("name", "fullName", "descriptor", "displayName", "userName", "username")
_LOGIN_KEYS = ("username", "userName", "user_name", "loginId", "login_id")


@dataclass(frozen=True)
class AuthenticatedUser:
    """Resolved OAuth bearer — safe to expose in the UI (no token/credentials)."""

    sub: Optional[str] = None
    display_name: Optional[str] = None
    login: Optional[str] = None

    @property
    def label(self) -> Optional[str]:
        if self.display_name:
            return self.display_name
        if self.login:
            return self.login
        return self.sub

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "sub": self.sub,
            "displayName": self.display_name,
            "login": self.login,
            "label": self.label,
        }


def bearer_token_from_authorization(header_or_token: str) -> Optional[str]:
    candidate = (header_or_token or "").strip()
    if candidate.lower().startswith("bearer "):
        candidate = candidate[7:].strip()
    return candidate or None


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """Decode a JWT payload without verifying the signature."""
    parts = token.strip().split(".")
    if len(parts) < 2:
        return None
    try:
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        body = json.loads(decoded)
        return body if isinstance(body, dict) else None
    except Exception:
        return None


def extract_sub_from_authorization(header_or_token: str) -> Optional[str]:
    """Return the JWT ``sub`` claim from a Bearer header or raw access token."""
    token = bearer_token_from_authorization(header_or_token)
    if not token:
        return None
    claims = decode_jwt_payload(token)
    if not claims:
        return None
    sub = claims.get("sub")
    if isinstance(sub, str) and sub.strip():
        return sub.strip()
    return None


def _first_string(body: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for key in keys:
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _profile_from_user_json(body: Any) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(body, dict):
        return None, None
    display_name = _first_string(body, _DISPLAY_NAME_KEYS)
    login = _first_string(body, _LOGIN_KEYS)
    for nested_key in ("user", "worker", "person"):
        nested = body.get(nested_key)
        if isinstance(nested, dict):
            n_login, n_display = _profile_from_user_json(nested)
            login = login or n_login
            display_name = display_name or n_display
    return login, display_name


def fetch_user_profile_by_sub(
    host: str,
    tenant: str,
    user_sub: str,
    authorization: str,
    *,
    client: httpx.Client,
    timeout: httpx.Timeout,
) -> Optional[Dict[str, Any]]:
    """``GET /ccx/api/v1/{tenant}/users/{sub}`` — primary Skylab profile lookup."""
    encoded_sub = quote(user_sub, safe="")
    url = f"https://{host}/ccx/api/v1/{tenant}/users/{encoded_sub}"
    headers = {"Accept": "application/json", "Authorization": authorization}
    try:
        resp = client.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    try:
        body = resp.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def resolve_authenticated_user(
    authorization: str,
    *,
    host: str,
    tenant: str,
    client: httpx.Client,
    timeout: Optional[httpx.Timeout] = None,
) -> AuthenticatedUser:
    """Decode ``sub``, fetch ``/users/{sub}``, return profile for session/UI."""
    timeout = timeout or httpx.Timeout(10.0)
    token_sub = extract_sub_from_authorization(authorization)
    if not token_sub:
        return AuthenticatedUser()

    profile_body = fetch_user_profile_by_sub(
        host,
        tenant,
        token_sub,
        authorization,
        client=client,
        timeout=timeout,
    )
    if profile_body:
        login, display_name = _profile_from_user_json(profile_body)
        return AuthenticatedUser(
            sub=token_sub,
            display_name=display_name,
            login=login,
        )

    claims = decode_jwt_payload(bearer_token_from_authorization(authorization) or "")
    login: Optional[str] = None
    if claims:
        login = _first_string(claims, _LOGIN_KEYS)
        if not login and isinstance(claims.get("sub"), str):
            raw_sub = claims["sub"].strip()
            if "@" in raw_sub and not raw_sub.lower().startswith("http"):
                login = raw_sub.split("@", 1)[0].strip() or None
            elif not _WID_DOLLAR.match(raw_sub) and len(raw_sub) < 32:
                login = raw_sub

    return AuthenticatedUser(sub=token_sub, display_name=None, login=login)
