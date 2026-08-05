"""Pydantic request/response models for the web layer.

These describe only the JSON contract between the SPA and the FastAPI backend.
They contain no business logic and never carry credentials back to the client.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

# A parameter value is either a scalar or a list (for repeatable query params).
ParamValue = Union[str, int, float, bool, List[Union[str, int, float, bool]]]


class ConnectRequest(BaseModel):
    host: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    tenant: str = Field(..., min_length=1)


class ConnectResponse(BaseModel):
    status: str
    host: str
    tenant: str
    username: str
    mode: str
    message: str
    identity: Optional[str] = None
    userSub: Optional[str] = None
    userLogin: Optional[str] = None
    oauthOnly: bool = False


class DisconnectResponse(BaseModel):
    status: str


class ExecuteRequest(BaseModel):
    endpoint_id: str = Field(..., min_length=1)
    parameters: Dict[str, ParamValue] = Field(default_factory=dict)
    persona: Optional[str] = None


class ExecuteResponse(BaseModel):
    timestamp: str
    endpointId: str
    persona: Optional[str]
    status: int  # upstream (Skylab) HTTP status — kept for backward compatibility
    upstreamStatus: int
    proxyHttpStatus: int = 200
    upstreamOk: bool
    durationMs: float
    method: str
    url: str
    requestHeaders: Dict[str, str]
    responseHeaders: Dict[str, str]
    query: List[Tuple[str, str]]
    body: Any


class CatalogResponse(BaseModel):
    categories: List[str]
    endpoints: List[dict]


class ConfigResponse(BaseModel):
    mode: str
    modes: List[str]
    connected: bool = False
    host: Optional[str] = None
    tenant: Optional[str] = None
    username: Optional[str] = None
    identity: Optional[str] = None
    userSub: Optional[str] = None
    userLogin: Optional[str] = None
    oauthOnly: bool = False


class MeResponse(BaseModel):
    connected: bool
    sub: Optional[str] = None
    displayName: Optional[str] = None
    login: Optional[str] = None
    label: Optional[str] = None


class SetModeRequest(BaseModel):
    mode: str = Field(..., min_length=1)


class TokenRequest(BaseModel):
    host: str = Field(..., min_length=1)
    tenant: str = Field(..., min_length=1)
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    authorization: str
    expiresIn: Optional[float] = None
    message: str


class ProbeResult(BaseModel):
    name: str
    url: str
    status: int
    hasWdRequestId: bool
    errorHint: Optional[str] = None


class ProbeResponse(BaseModel):
    host: str
    tenant: str
    probes: List[ProbeResult]
    summary: str


class OpenApiCatalogRequest(BaseModel):
    host: Optional[str] = None


class OpenApiCatalogResult(BaseModel):
    name: str
    path: str
    url: str
    status: int
    contentType: Optional[str] = None
    isOpenApiDocument: bool
    serviceTitle: Optional[str] = None
    serviceVersion: Optional[str] = None
    curlCommand: Optional[str] = None


class OpenApiCatalogResponse(BaseModel):
    host: str
    tenant: str
    results: List[OpenApiCatalogResult]


class ErrorResponse(BaseModel):
    error: str
    detail: List[str] = Field(default_factory=list)
