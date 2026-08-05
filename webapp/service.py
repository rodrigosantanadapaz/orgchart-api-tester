"""Adapter that wires the frozen loader + engine + transports to the web layer.

Supports two execution modes selected by a configuration flag:

  * ``mock`` — uses ``MockTransport`` (no network, no auth).
  * ``live`` — uses ``HttpxTransport`` to issue real read-only GET requests,
    with a temporary static ``Authorization`` header held only in memory in the
    connection session.

The mode comes from the ``mode`` argument or the ``OC_EXECUTION_MODE`` env var
(default ``mock``). No credential is ever written to disk; ``disconnect()``
destroys the in-memory header and closes any live client.

This module holds no endpoint knowledge and builds no URLs — everything flows
through the frozen engine.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Mapping, Optional, Tuple

import httpx

from engine.client import ReadOnlyApiClient, Response
from engine.request_builder import BuiltRequest
from harness.loader import deep_merge, load_config
from transport import HttpxTransport

from .oauth_user import AuthenticatedUser, resolve_authenticated_user
from .mock_transport import MockTransport
from .oauth_token import OAuthTokenError, exchange_refresh_token, token_url_from_resolved
from .session_auth import StaticSessionAuthProvider
from .suv_id_token import SuvAuthError, SuvIdTokenProvider

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "environment.json"
VALID_MODES = ("mock", "live")
# Placeholder WID for optional internal navigable probe (override via OC_PROBE_NAVIGABLE_WID).
DEFAULT_PROBE_NAVIGABLE_WID = os.getenv(
    "OC_PROBE_NAVIGABLE_WID", "00000000000000000000000000000001"
)


def environment_key_for_host(host: str) -> Optional[str]:
    """Pick harness environment overrides from the connected host."""
    h = host.lower()
    if "skylab" in h or h.endswith(".inday.io"):
        return "skylab"
    if "workdaysuv.com" in h:
        return "suv"
    return None


class NotConnected(Exception):
    """Raised when an execution is attempted before connecting."""


class AlreadyConnected(Exception):
    """Raised when the execution mode cannot change while a session is active."""


class InvalidMode(Exception):
    """Raised when an unknown execution mode is requested."""

    def __init__(self, message: str) -> None:
        self.messages = [message]
        super().__init__(message)


def _is_prebuilt_auth_header(password: str) -> bool:
    lowered = password.strip().lower()
    return lowered.startswith(("bearer ", "basic ", "id "))


def _normalize_live_password(password: str) -> str:
    """Accept raw JWT access tokens (paste from curl) as well as full headers."""
    candidate = password.strip()
    if not candidate:
        return candidate
    lowered = candidate.lower()
    if lowered.startswith(("bearer ", "basic ", "id ")):
        return candidate
    if lowered.startswith("bearer"):
        token = candidate[6:].lstrip()
        if token:
            return f"Bearer {token}"
    if candidate.startswith("eyJ"):
        return f"Bearer {candidate}"
    return candidate


def _build_authorization_header(username: str, password: str) -> str:
    """Build a static Authorization header for pre-supplied token values only."""
    candidate = password.strip()
    lowered = candidate.lower()
    if lowered.startswith(("bearer ", "basic ", "id ")):
        return candidate
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


@dataclass
class Session:
    host: str
    tenant: str
    username: str
    auth: StaticSessionAuthProvider | SuvIdTokenProvider
    identity: Optional[str] = None
    user_sub: Optional[str] = None
    user_login: Optional[str] = None
    display_name: Optional[str] = None
    transport: Optional[HttpxTransport] = None

    def apply_user(self, user: AuthenticatedUser) -> None:
        self.user_sub = user.sub
        self.user_login = user.login
        self.display_name = user.display_name
        self.identity = user.label

    def user_profile(self) -> AuthenticatedUser:
        return AuthenticatedUser(
            sub=self.user_sub,
            display_name=self.display_name,
            login=self.user_login,
        )

    def destroy(self) -> None:
        self.auth.clear()
        if self.transport is not None:
            self.transport.close()
            self.transport = None


class ExecutionService:
    def __init__(
        self,
        config_path: Path | str = DEFAULT_CONFIG,
        *,
        mode: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._loaded = load_config(config_path)
        self._defaults: Dict[str, Any] = dict(self._loaded.resolved)
        self._mode = (mode or os.getenv("OC_EXECUTION_MODE", "mock")).lower()
        if self._mode not in VALID_MODES:
            raise ValueError(f"invalid execution mode '{self._mode}'; expected one of {VALID_MODES}")
        self._mock = MockTransport()
        self._http_client = http_client  # optional injected client for live-mode tests
        self._session: Optional[Session] = None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def connection(self) -> Optional[Session]:
        return self._session

    def is_connected(self) -> bool:
        return self._session is not None

    def refresh_oauth_identity(self) -> AuthenticatedUser:
        """Re-resolve token bearer profile from JWT sub + CCX REST."""
        session = self._session
        empty = AuthenticatedUser()
        if session is None or session.username != "oauth":
            return session.user_profile() if session else empty
        if self._mode != "live" or session.transport is None:
            return session.user_profile()
        auth_value = session.auth.authorization_header(None)
        if not auth_value:
            return session.user_profile()
        user = resolve_authenticated_user(
            auth_value,
            host=session.host,
            tenant=session.tenant,
            client=session.transport._get_client(),  # noqa: SLF001
            timeout=session.transport.timeout,
        )
        session.apply_user(user)
        return user

    def set_mode(self, mode: str) -> None:
        """Switch execution mode (mock vs live). Requires an idle session."""
        if self._session is not None:
            raise AlreadyConnected("disconnect before changing execution mode")
        normalized = mode.lower()
        if normalized not in VALID_MODES:
            raise InvalidMode(
                f"invalid execution mode '{mode}'; expected one of {VALID_MODES}"
            )
        self._mode = normalized

    # -- connection ----------------------------------------------------- #
    def connect(self, host: str, tenant: str, username: str, password: str) -> Session:
        host = host.strip().rstrip("/")
        for scheme in ("https://", "http://"):
            if host.startswith(scheme):
                host = host[len(scheme):]
        host = host.split("/")[0]
        if self._mode == "live":
            password = _normalize_live_password(password)

        transport: Optional[HttpxTransport] = None
        oauth_user: Optional[AuthenticatedUser] = None
        env_key = environment_key_for_host(host)
        auth_header: Optional[str] = None
        if self._mode == "live" and _is_prebuilt_auth_header(password):
            if env_key == "skylab":
                username = "oauth"
            auth_header = _build_authorization_header(username, password)
            auth: StaticSessionAuthProvider | SuvIdTokenProvider = StaticSessionAuthProvider(
                auth_header
            )
        elif self._mode == "live" and env_key == "skylab":
            raise SuvAuthError(
                "SkyLab needs an OAuth Bearer access token in Password — paste "
                "'Bearer eyJ...' or just the access_token from the curl response."
            )
        elif self._mode == "live":
            resolved = self._resolved_for(host, tenant)
            tls = resolved.get("tls", {})
            timeouts = resolved.get("timeouts", {})
            timeout = httpx.Timeout(
                connect=float(timeouts.get("connectMs", 5000)) / 1000.0,
                read=float(timeouts.get("readMs", 30000)) / 1000.0,
                write=float(timeouts.get("readMs", 30000)) / 1000.0,
                pool=float(timeouts.get("connectMs", 5000)) / 1000.0,
            )
            auth = SuvIdTokenProvider(
                host,
                tenant,
                username,
                password,
                verify=bool(tls.get("verify", True)),
                timeout=timeout,
                client=self._http_client,
            )
            auth.validate()
        else:
            auth = StaticSessionAuthProvider(
                _build_authorization_header(username, password)
            )

        if self._mode == "live":
            resolved = self._resolved_for(host, tenant)
            transport = HttpxTransport.from_resolved(
                resolved, auth_provider=auth, client=self._http_client
            )
        if (
            self._mode == "live"
            and env_key == "skylab"
            and username == "oauth"
            and auth_header
        ):
            oauth_user = resolve_authenticated_user(
                auth_header,
                host=host,
                tenant=tenant,
                client=transport._get_client() if transport is not None else self._http_client,
                timeout=transport.timeout if transport is not None else None,
            )
        self._session = Session(
            host=host,
            tenant=tenant,
            username=username,
            auth=auth,
            transport=transport,
        )
        if oauth_user is not None:
            self._session.apply_user(oauth_user)
        return self._session

    def disconnect(self) -> None:
        if self._session is not None:
            self._session.destroy()  # zero credential + close client
        self._session = None

    def exchange_oauth_token(
        self,
        host: str,
        tenant: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> Tuple[str, Optional[float]]:
        """Refresh-token grant; returns ``(Bearer header, expires_in)``."""
        host = host.strip().rstrip("/")
        for scheme in ("https://", "http://"):
            if host.startswith(scheme):
                host = host[len(scheme):]
        host = host.split("/")[0]
        tenant = tenant.strip()
        resolved = self._resolved_for(host, tenant)
        tls = resolved.get("tls", {})
        timeouts = resolved.get("timeouts", {})
        timeout = httpx.Timeout(
            connect=float(timeouts.get("connectMs", 5000)) / 1000.0,
            read=float(timeouts.get("tokenMs", 15000)) / 1000.0,
            write=float(timeouts.get("tokenMs", 15000)) / 1000.0,
            pool=float(timeouts.get("connectMs", 5000)) / 1000.0,
        )
        token_url = token_url_from_resolved(resolved, host, tenant)
        return exchange_refresh_token(
            token_url,
            client_id,
            client_secret,
            refresh_token,
            verify=bool(tls.get("verify", True)),
            timeout=timeout,
            client=self._http_client,
        )

    def probe_upstream(self) -> List[Dict[str, Any]]:
        """Control GETs using the active session auth (staffing vs orgchart)."""
        session = self._session
        if session is None:
            raise NotConnected("connect to a host before probing upstream APIs")
        if self._mode != "live" or session.transport is None:
            raise InvalidMode("upstream probe requires live mode with an active connection")

        resolved = self._resolved_for(session.host, session.tenant)
        host = session.host
        tenant = session.tenant
        orgchart_base = str(resolved["restBaseTemplate"]).format(host=host, tenant=tenant).rstrip("/")
        targets = [
            (
                "staffing",
                f"https://{host}/ccx/api/staffing/v6/{tenant}/workers?limit=1",
            ),
            (
                "orgchart_public",
                f"https://{host}/ccx/api/orgchart/v1/{tenant}/values/orgChartPrompts/organizations/?limit=1",
            ),
            (
                "orgchart_routed",
                f"{orgchart_base}/values/orgChartPrompts/organizations/?limit=1",
            ),
            (
                "orgchart_internal_prompt",
                f"https://{host}/ccx/internalapi/orgchart/v1/{tenant}/values/orgChartPrompts/organizations/?limit=1",
            ),
            (
                "orgchart_internal_navigable",
                f"https://{host}/ccx/internalapi/orgchart/v1/{tenant}/navigables/{DEFAULT_PROBE_NAVIGABLE_WID}",
            ),
        ]
        headers = dict(resolved.get("defaultHeaders", {}))
        auth_value = session.auth.authorization_header(None)
        if auth_value:
            headers["Authorization"] = auth_value

        client = session.transport._get_client()  # noqa: SLF001 — reuse live session client
        results: List[Dict[str, Any]] = []
        for name, url in targets:
            resp = client.get(url, headers=headers, timeout=session.transport.timeout)
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            results.append(
                {
                    "name": name,
                    "url": url,
                    "status": resp.status_code,
                    "hasWdRequestId": "wd-stat-request-id" in hdrs,
                    "errorHint": _probe_error_hint(resp),
                }
            )
        return results

    def probe_openapi_catalog(self, host: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch Skylab OpenAPI catalog documents using the active session auth."""
        session = self._session
        if session is None:
            raise NotConnected("connect to a host before probing OpenAPI catalogs")
        if self._mode != "live" or session.transport is None:
            raise InvalidMode("OpenAPI catalog probe requires live mode with an active connection")

        resolved = self._resolved_for(session.host, session.tenant)
        target_host = (host or session.host).strip()
        tenant = session.tenant
        targets = [
            (
                "tenant_hub",
                f"/ccx/api/v1/{tenant}/openapi.json",
            ),
            (
                "orgchart_public",
                f"/ccx/api/orgchart/v1/{tenant}/openapi.json",
            ),
            (
                "orgchart_internal",
                f"/ccx/internalapi/orgchart/v1/{tenant}/openapi.json",
            ),
        ]
        headers = dict(resolved.get("defaultHeaders", {}))
        headers["Accept"] = "application/json"
        auth_value = session.auth.authorization_header(None)
        if auth_value:
            headers["Authorization"] = auth_value

        client = session.transport._get_client()  # noqa: SLF001 — reuse live session client
        results: List[Dict[str, Any]] = []
        for name, path in targets:
            url = f"https://{target_host}{path}"
            resp = client.get(url, headers=headers, timeout=session.transport.timeout)
            parsed = _parse_openapi_catalog_response(resp)
            item: Dict[str, Any] = {
                "name": name,
                "path": path,
                "url": url,
                "status": resp.status_code,
                "contentType": parsed["content_type"],
                "isOpenApiDocument": parsed["is_openapi_document"],
                "serviceTitle": parsed["service_title"],
                "serviceVersion": parsed["service_version"],
            }
            if not parsed["is_openapi_document"]:
                item["curlCommand"] = _redacted_curl_get(url)
            results.append(item)
        return results

    # -- execution ------------------------------------------------------ #
    def _resolved_for(self, host: str, tenant: str) -> Mapping[str, Any]:
        env_key = environment_key_for_host(host)
        if env_key:
            base = dict(self._loaded.source.get("defaults", {}))
            env_block = dict(self._loaded.source["environments"].get(env_key, {}))
            resolved = dict(deep_merge(base, env_block))
            resolved["activeEnvironment"] = env_key
        else:
            resolved = dict(self._defaults)
        resolved["host"] = host
        resolved["tenant"] = tenant
        resolved.pop("roles", None)  # persona here is the username, not an A-D role
        return resolved

    def execute(
        self,
        endpoint_id: str,
        parameters: Optional[Mapping[str, Any]] = None,
        persona: Optional[str] = None,
    ) -> Tuple[BuiltRequest, Response, float]:
        session = self._session
        if session is None:
            raise NotConnected("connect to a host before sending requests")

        resolved = self._resolved_for(session.host, session.tenant)
        transport = self._mock if self._mode == "mock" else session.transport
        client = ReadOnlyApiClient(resolved, transport=transport)
        built = client.build(endpoint_id, parameters)  # URL + safe headers for display
        start = perf_counter()
        response = client.execute(endpoint_id, parameters, persona=persona)
        duration_ms = (perf_counter() - start) * 1000.0
        return built, response, duration_ms


def _probe_error_hint(resp: httpx.Response) -> Optional[str]:
    try:
        body = resp.json()
    except ValueError:
        text = (resp.text or "").strip()
        return text[:120] if text else None
    if isinstance(body, dict):
        for key in ("error", "error_description", "message"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:160]
    return None


def _parse_openapi_catalog_response(resp: httpx.Response) -> Dict[str, Optional[Any]]:
    content_type = resp.headers.get("content-type")
    is_openapi = False
    service_title: Optional[str] = None
    service_version: Optional[str] = None
    if resp.status_code == 200:
        try:
            body = resp.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get("openapi"), str):
            is_openapi = True
            info = body.get("info")
            if isinstance(info, dict):
                title = info.get("title")
                version = info.get("version")
                service_title = title if isinstance(title, str) else None
                service_version = version if isinstance(version, str) else None
    return {
        "content_type": content_type,
        "is_openapi_document": is_openapi,
        "service_title": service_title,
        "service_version": service_version,
    }


def _redacted_curl_get(url: str) -> str:
    return (
        "curl -sS -D - -o /tmp/openapi.json "
        '-H "Authorization: Bearer $TOKEN" '
        '-H "Accept: application/json" '
        f'"{url}"'
    )
