"""OAuth refresh-token grant → Bearer access token (SkyLab / public REST).

Exchanges a per-user refresh token for a short-lived access token at
``https://{host}/ccx/oauth2/{tenant}/token``. Client credentials and refresh
tokens are never logged or returned in API responses.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

import httpx

DEFAULT_TOKEN_URL_TEMPLATE = "https://{host}/ccx/oauth2/{tenant}/token"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=15.0, pool=5.0)


class OAuthTokenError(Exception):
    """Refresh-token exchange failed."""


def token_url_from_resolved(resolved: Mapping[str, Any], host: str, tenant: str) -> str:
    auth = resolved.get("auth") or {}
    template = auth.get("tokenUrlTemplate") or DEFAULT_TOKEN_URL_TEMPLATE
    return str(template).format(host=host, tenant=tenant)


def exchange_refresh_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    verify: bool = True,
    timeout: Optional[httpx.Timeout] = None,
    client: Optional[httpx.Client] = None,
) -> Tuple[str, Optional[float]]:
    """Return ``(authorization_header, expires_in_seconds)``."""
    client_id = client_id.strip()
    client_secret = client_secret.strip()
    refresh_token = refresh_token.strip()
    if not client_id or not client_secret or not refresh_token:
        raise OAuthTokenError("Client ID, client secret, and refresh token are required.")

    owns_client = client is None
    http = client or httpx.Client(verify=verify, timeout=timeout or DEFAULT_TIMEOUT)
    try:
        try:
            resp = http.post(
                token_url,
                auth=(client_id, client_secret),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=timeout or DEFAULT_TIMEOUT,
            )
        except httpx.TimeoutException as exc:
            raise OAuthTokenError("Timed out contacting the OAuth token endpoint.") from exc
        except httpx.HTTPError as exc:
            raise OAuthTokenError(
                "Could not reach the OAuth token endpoint. Check host, tenant, and VPN."
            ) from exc

        if resp.status_code == 401:
            raise OAuthTokenError(
                "OAuth client rejected (HTTP 401). Check client ID and client secret."
            )
        if resp.status_code != 200:
            detail = _safe_error_detail(resp)
            raise OAuthTokenError(
                f"Token exchange failed (HTTP {resp.status_code}).{detail}"
            )

        try:
            body = resp.json()
        except ValueError as exc:
            raise OAuthTokenError("OAuth token endpoint returned a non-JSON response.") from exc

        access_token = body.get("access_token")
        if not access_token:
            raise OAuthTokenError("OAuth response did not include an access_token.")

        expires_in = body.get("expires_in")
        expires: Optional[float] = float(expires_in) if expires_in is not None else None
        return f"Bearer {access_token}", expires
    finally:
        if owns_client:
            http.close()


def _safe_error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return ""
    for key in ("error_description", "error", "message"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return f" {value.strip()}"
    return ""
