"""Read-only Org Chart REST API execution engine (ORG-21922).

Scope: endpoint catalog, request building, and a read-only client with an
injectable transport. NO authentication, NO real HTTP, NO evidence, NO UI.
"""

from __future__ import annotations

from . import catalog
from .catalog import (
    CATEGORIES,
    ENDPOINTS,
    PARAM_LOCATIONS,
    RESPONSE_TYPES,
    Endpoint,
    Param,
    as_dicts,
    by_id,
)
from .client import (
    ReadOnlyApiClient,
    Response,
    Transport,
    UnconfiguredTransport,
)
from .errors import (
    EndpointNotFound,
    EngineError,
    ReadOnlyViolation,
    RequestValidationError,
    TransportNotConfigured,
    UnknownPersona,
)
from .request_builder import BuiltRequest, RequestBuilder

__all__ = [
    "CATEGORIES",
    "RESPONSE_TYPES",
    "PARAM_LOCATIONS",
    "ENDPOINTS",
    "Endpoint",
    "Param",
    "by_id",
    "as_dicts",
    "catalog",
    "RequestBuilder",
    "BuiltRequest",
    "ReadOnlyApiClient",
    "Response",
    "Transport",
    "UnconfiguredTransport",
    "EngineError",
    "EndpointNotFound",
    "RequestValidationError",
    "ReadOnlyViolation",
    "UnknownPersona",
    "TransportNotConfigured",
]
