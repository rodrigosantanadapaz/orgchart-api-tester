"""SUV username/password → ID token exchange for live REST calls.

Workday SUVs do **not** accept HTTP Basic on ``/ccx/api/...`` or
``/ccx/internalapi/...``. The flow is:

1. ``GET https://{host}/ors/{tenant}/services/security/v1/authIdToken``
   with ``Authorization: Basic <tenanted user:password>``
2. Use the returned ``encodedToken`` on REST calls as
   ``Authorization: ID <token>`` (scheme is ``ID``, not ``Bearer``).

Credentials and tokens live only in memory for the connection session.
Nothing is logged, persisted, or echoed to API responses.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Optional

import httpx

AUTH_TOKEN_URL_TEMPLATE = (
    "https://{host}/ors/{tenant}/services/security/v1/authIdToken"
)
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)


class SuvAuthError(Exception):
    """Credential exchange failed (bad username/password, or auth service missing)."""


class SuvIdTokenProvider:
    """Implements the transport ``AuthProvider`` protocol with a cached ID token."""

    __slots__ = (
        "_host",
        "_tenant",
        "_username",
        "_password",
        "_verify",
        "_timeout",
        "_client",
        "_owns_client",
        "_token",
        "_expires_at",
    )

    def __init__(
        self,
        host: str,
        tenant: str,
        username: str,
        password: str,
        *,
        verify: bool = True,
        timeout: Optional[httpx.Timeout] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._host = host.strip()
        self._tenant = tenant.strip()
        self._username = username.strip()
        self._password = password
        self._verify = bool(verify)
        self._timeout = timeout or DEFAULT_TIMEOUT
        self._owns_client = client is None
        self._client = client or httpx.Client(verify=self._verify, timeout=self._timeout)
        self._token: Optional[str] = None
        self._expires_at = 0.0

    def validate(self) -> None:
        """Fetch an ID token now so bad credentials fail at connect time."""
        self._token = None
        self._expires_at = 0.0
        self._fetch_token()

    def authorization_header(self, persona: Optional[str]) -> Optional[str]:
        if self._password is None:
            return None
        token = self._get_token()
        return f"ID {token}"

    def clear(self) -> None:
        self._password = None
        self._token = None
        self._expires_at = 0.0
        if self._owns_client:
            self._client.close()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "<SuvIdTokenProvider redacted>"

    def _auth_url(self) -> str:
        return AUTH_TOKEN_URL_TEMPLATE.format(host=self._host, tenant=self._tenant)

    def _get_token(self) -> str:
        now = time.time()
        if self._token and self._expires_at - 30 > now:
            return self._token
        return self._fetch_token()

    def _fetch_token(self) -> str:
        if not self._username or self._password is None:
            raise SuvAuthError("A tenanted username and password are required.")

        url = self._auth_url()
        basic = base64.b64encode(
            f"{self._username}:{self._password}".encode("utf-8")
        ).decode("ascii")
        try:
            resp = self._client.get(
                url,
                headers={"Authorization": f"Basic {basic}"},
                timeout=self._timeout,
            )
        except httpx.TimeoutException as exc:
            raise SuvAuthError("Timed out contacting the SUV auth service.") from exc
        except httpx.HTTPError as exc:
            raise SuvAuthError(
                "Could not reach the SUV auth service. Check the hostname and VPN."
            ) from exc

        if resp.status_code == 401:
            raise SuvAuthError(
                "Login failed: the username or password was not accepted by the SUV."
            )
        if resp.status_code == 404:
            raise SuvAuthError(
                "Auth service not found. Check the SUV hostname and tenant."
            )
        if resp.status_code != 200:
            raise SuvAuthError(
                f"Login failed (HTTP {resp.status_code}) at the SUV auth service."
            )

        try:
            body = resp.json()
        except ValueError as exc:
            raise SuvAuthError("Auth service returned a non-JSON response.") from exc

        token = body.get("encodedToken")
        if not token:
            raise SuvAuthError("Auth service response did not include a token.")

        self._token = token
        self._expires_at = time.time() + _token_ttl(token)
        return token


def _token_ttl(token: str, default_s: float = 840.0) -> float:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        exp = float(claims["exp"])
        return max(exp - time.time(), 0.0)
    except Exception:
        return default_s
