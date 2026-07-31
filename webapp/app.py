"""FastAPI application for the Org Chart API Tester UI.

Thin web layer: serves the SPA and exposes the minimum endpoints the UI needs
(``/api/catalog``, ``/api/connect``, ``/api/disconnect``, ``/api/execute``).
All endpoint knowledge and request building lives in the frozen ``engine``;
all configuration lives in the frozen ``harness`` loader. This module only
translates HTTP <-> service calls and maps errors to friendly responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from engine import catalog
from engine.catalog import CATEGORIES
from engine.errors import (
    EndpointNotFound,
    ReadOnlyViolation,
    RequestValidationError,
    UnknownPersona,
)

from transport.errors import TransportError, TransportTimeout

from .models import (
    CatalogResponse,
    ConfigResponse,
    ConnectRequest,
    ConnectResponse,
    DisconnectResponse,
    ExecuteRequest,
    ExecuteResponse,
    SetModeRequest,
    TokenRequest,
    TokenResponse,
    ProbeResponse,
    ProbeResult,
    OpenApiCatalogRequest,
    OpenApiCatalogResponse,
    OpenApiCatalogResult,
)
from .service import (
    VALID_MODES,
    AlreadyConnected,
    ExecutionService,
    InvalidMode,
    NotConnected,
    environment_key_for_host,
)
from .suv_id_token import SuvAuthError
from .oauth_token import OAuthTokenError

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(service: Optional[ExecutionService] = None) -> FastAPI:
    service = service or ExecutionService()
    app = FastAPI(title="Org Chart API Tester", version="1.0.0")

    # ------------------------- error handling ------------------------- #
    def _error(code: int, message: str, detail=None) -> JSONResponse:
        return JSONResponse(
            status_code=code,
            content={"error": message, "detail": detail or []},
        )

    @app.exception_handler(NotConnected)
    async def _not_connected(_req, exc: NotConnected):  # noqa: ANN001
        return _error(status.HTTP_409_CONFLICT, "Not connected", [str(exc)])

    @app.exception_handler(AlreadyConnected)
    async def _already_connected(_req, exc: AlreadyConnected):  # noqa: ANN001
        return _error(status.HTTP_409_CONFLICT, "Already connected", [str(exc)])

    @app.exception_handler(InvalidMode)
    async def _invalid_mode(_req, exc: InvalidMode):  # noqa: ANN001
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid mode", exc.messages)

    @app.exception_handler(SuvAuthError)
    async def _suv_auth_error(_req, exc: SuvAuthError):  # noqa: ANN001
        return _error(status.HTTP_400_BAD_REQUEST, str(exc), [])

    @app.exception_handler(OAuthTokenError)
    async def _oauth_token_error(_req, exc: OAuthTokenError):  # noqa: ANN001
        return _error(status.HTTP_400_BAD_REQUEST, str(exc), [])

    @app.exception_handler(EndpointNotFound)
    async def _endpoint_not_found(_req, exc: EndpointNotFound):  # noqa: ANN001
        return _error(status.HTTP_404_NOT_FOUND, "Unknown endpoint", exc.messages)

    @app.exception_handler(RequestValidationError)
    async def _bad_request(_req, exc: RequestValidationError):  # noqa: ANN001
        return _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid parameters", exc.messages)

    @app.exception_handler(ReadOnlyViolation)
    async def _read_only(_req, exc: ReadOnlyViolation):  # noqa: ANN001
        return _error(status.HTTP_400_BAD_REQUEST, "Read-only violation", exc.messages)

    @app.exception_handler(UnknownPersona)
    async def _unknown_persona(_req, exc: UnknownPersona):  # noqa: ANN001
        return _error(status.HTTP_400_BAD_REQUEST, "Unknown persona", exc.messages)

    @app.exception_handler(TransportTimeout)
    async def _timeout(_req, exc: TransportTimeout):  # noqa: ANN001
        return _error(status.HTTP_504_GATEWAY_TIMEOUT, "Upstream timeout", exc.messages)

    @app.exception_handler(TransportError)
    async def _transport_error(_req, exc: TransportError):  # noqa: ANN001
        return _error(status.HTTP_502_BAD_GATEWAY, "Upstream request failed", exc.messages)

    # ------------------------------ API ------------------------------- #
    @app.get("/api/catalog", response_model=CatalogResponse)
    async def get_catalog() -> CatalogResponse:
        return CatalogResponse(categories=list(CATEGORIES), endpoints=catalog.as_dicts())

    @app.get("/api/config", response_model=ConfigResponse)
    async def get_config() -> ConfigResponse:
        session = service.connection
        if session is None:
            return ConfigResponse(mode=service.mode, modes=list(VALID_MODES), connected=False)
        return ConfigResponse(
            mode=service.mode,
            modes=list(VALID_MODES),
            connected=True,
            host=session.host,
            tenant=session.tenant,
            username=session.username,
        )

    @app.post("/api/mode", response_model=ConfigResponse)
    async def set_mode(req: SetModeRequest) -> ConfigResponse:
        service.set_mode(req.mode)
        return ConfigResponse(mode=service.mode, modes=list(VALID_MODES))

    @app.post("/api/connect", response_model=ConnectResponse)
    async def connect(req: ConnectRequest) -> ConnectResponse:
        # Mock auth: no real credential check; password is never stored or echoed.
        conn = service.connect(
            host=req.host, tenant=req.tenant, username=req.username, password=req.password
        )
        env_key = environment_key_for_host(conn.host)
        if env_key == "skylab" and service.mode == "live" and conn.username == "oauth":
            message = (
                f"Connected to {conn.host} (tenant {conn.tenant}) via OAuth Bearer "
                f"[{service.mode} mode]. Username is not used on SkyLab."
            )
        else:
            message = (
                f"Connected to {conn.host} (tenant {conn.tenant}) as {conn.username} "
                f"[{service.mode} mode]."
            )
        return ConnectResponse(
            status="connected",
            host=conn.host,
            tenant=conn.tenant,
            username=conn.username,
            mode=service.mode,
            message=message,
        )

    @app.post("/api/disconnect", response_model=DisconnectResponse)
    async def disconnect() -> DisconnectResponse:
        service.disconnect()
        return DisconnectResponse(status="disconnected")

    @app.post("/api/token", response_model=TokenResponse)
    async def get_token(req: TokenRequest) -> TokenResponse:
        authorization, expires_in = service.exchange_oauth_token(
            host=req.host,
            tenant=req.tenant,
            client_id=req.client_id,
            client_secret=req.client_secret,
            refresh_token=req.refresh_token,
        )
        expiry_note = (
            f" Token expires in about {int(expires_in)} seconds."
            if expires_in is not None
            else ""
        )
        return TokenResponse(
            authorization=authorization,
            expiresIn=expires_in,
            message=f"Access token obtained.{expiry_note} Paste into Password and Connect.",
        )

    @app.post("/api/probe", response_model=ProbeResponse)
    async def probe_upstream() -> ProbeResponse:
        session = service.connection
        if session is None:
            raise NotConnected("connect to a host before probing upstream APIs")
        raw = service.probe_upstream()
        probes = [ProbeResult(**item) for item in raw]
        staffing = next((p for p in probes if p.name == "staffing"), None)
        org_public = next((p for p in probes if p.name == "orgchart_public"), None)
        org_routed = next((p for p in probes if p.name == "orgchart_routed"), None)
        org_internal = next((p for p in probes if p.name == "orgchart_internal_prompt"), None)
        env_key = environment_key_for_host(session.host)
        if org_routed and org_routed.status == 200:
            if org_public and org_public.status != 200 and env_key == "skylab":
                summary = (
                    "Orgchart works on /ccx/internalapi/... for this SkyLab tenant. "
                    "Public /ccx/api/orgchart/... is not published here (HTTP "
                    f"{org_public.status}). The tester routes Skylab to internalapi."
                )
            else:
                summary = "Orgchart works on the API surface the tester routes to for this host."
        elif org_internal and org_internal.status == 200 and org_public and org_public.status != 200:
            summary = (
                "Orgchart is reachable on /ccx/internalapi/... but not on public "
                f"/ccx/api/... (HTTP {org_public.status}). Reconnect so the tester "
                "picks up the internalapi route for Skylab."
            )
        elif staffing and staffing.status == 200 and org_public and org_public.status != 200:
            if env_key == "suv":
                summary = (
                    "OAuth works (staffing 200) but public orgchart (/ccx/api/...) is blocked on "
                    "this SUV. Reconnect with username+password — the tester uses /internalapi/ on SUVs."
                )
            else:
                summary = (
                    "OAuth works (staffing 200) but orgchart public API is rejected — "
                    "likely orgchart publish/toggle on this SkyLab tenant."
                )
        elif staffing and staffing.status == 200:
            summary = "OAuth token is valid for REST on this host/tenant."
        elif staffing and staffing.status == 401:
            summary = (
                "Bearer token invalid or expired — use Get token again and reconnect."
            )
        elif staffing and staffing.status == 403:
            if org_routed and org_routed.status == 200:
                summary = (
                    "Orgchart works on the routed API surface. Staffing returned 403 — "
                    "that control API may not be in your client's scopes (not necessarily a blocker)."
                )
            elif org_public and org_public.status in (401, 403):
                summary = (
                    "Bearer rejected for orgchart (HTTP "
                    f"{org_public.status}). Regenerate the refresh token on this Skylab "
                    "tenant and confirm scope Organizations and Roles + domain "
                    "Reports: Navigate Organization for the token user."
                )
            else:
                summary = (
                    "Token reaches Skylab but REST calls are denied or rejected. "
                    "Confirm API client scope Organizations and Roles on this tenant, "
                    "regenerate refresh token after saving scopes, and try Super User."
                )
        else:
            summary = "See per-probe status codes below."
        return ProbeResponse(
            host=session.host,
            tenant=session.tenant,
            probes=probes,
            summary=summary,
        )

    @app.post("/api/openapi-catalog", response_model=OpenApiCatalogResponse)
    async def probe_openapi_catalog(req: OpenApiCatalogRequest) -> OpenApiCatalogResponse:
        session = service.connection
        if session is None:
            raise NotConnected("connect to a host before probing OpenAPI catalogs")
        target_host = (req.host or session.host).strip()
        raw = service.probe_openapi_catalog(host=target_host)
        results = [OpenApiCatalogResult(**item) for item in raw]
        return OpenApiCatalogResponse(host=target_host, tenant=session.tenant, results=results)

    @app.post("/api/execute", response_model=ExecuteResponse)
    async def execute(req: ExecuteRequest) -> ExecuteResponse:
        persona = req.persona or (service.connection.username if service.connection else None)
        built, response, duration_ms = service.execute(
            req.endpoint_id, req.parameters, persona=persona
        )
        upstream_status = response.status
        upstream_ok = 200 <= upstream_status < 300
        return ExecuteResponse(
            timestamp=datetime.now(timezone.utc).isoformat(),
            endpointId=req.endpoint_id,
            persona=persona,
            status=upstream_status,
            upstreamStatus=upstream_status,
            proxyHttpStatus=200,
            upstreamOk=upstream_ok,
            durationMs=round(duration_ms, 3),
            method=built.method,
            url=built.url,
            requestHeaders=built.headers,  # already secret-free (engine guarantee)
            responseHeaders=response.headers,
            query=[tuple(pair) for pair in built.query],
            body=response.body,
        )

    # --------------------------- frontend ----------------------------- #
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(str(_STATIC_DIR / "index.html"))

    return app


app = create_app()
