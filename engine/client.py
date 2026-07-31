"""Read-only Org Chart API client abstraction.

Deliberately does NOT implement authentication or perform real HTTP calls. It
orchestrates: resolve endpoint -> enforce read-only -> validate persona ->
build request -> delegate to an injectable ``Transport``.

A real transport (requests/httpx) and an auth layer are added later; the
``Transport`` protocol is the seam for that. Until a transport is injected, the
client fails closed with ``TransportNotConfigured`` and never touches the
network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Protocol, Union, runtime_checkable

from . import catalog
from .catalog import Endpoint
from .errors import (
    EndpointNotFound,
    ReadOnlyViolation,
    TransportNotConfigured,
    UnknownPersona,
)
from .request_builder import BuiltRequest, RequestBuilder


@dataclass(frozen=True)
class Response:
    """Transport-agnostic response container (populated by a real transport later)."""

    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None


@runtime_checkable
class Transport(Protocol):
    """Injectable HTTP seam.

    Implementations receive the fully built request and the persona label so a
    future auth layer can attach the correct credentials at send time. The
    persona is passed as an opaque label; the transport/auth layer — not this
    client — resolves it to a token.
    """

    def send(self, request: BuiltRequest, persona: Optional[str]) -> Response:
        ...


class UnconfiguredTransport:
    """Default transport: refuses to send, guaranteeing no accidental network I/O."""

    def send(self, request: BuiltRequest, persona: Optional[str]) -> Response:  # noqa: D401
        raise TransportNotConfigured(
            "no HTTP transport injected; the read-only client cannot send requests yet"
        )


class ReadOnlyApiClient:
    def __init__(
        self,
        resolved: Mapping[str, Any],
        *,
        transport: Optional[Transport] = None,
        request_builder: Optional[RequestBuilder] = None,
    ) -> None:
        self._resolved = resolved
        self._builder = request_builder or RequestBuilder(resolved)
        self._transport: Transport = transport or UnconfiguredTransport()
        self._roles = set(resolved.get("roles", []))

    # ------------------------------------------------------------------ #
    def build(
        self,
        endpoint: Union[str, Endpoint],
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> BuiltRequest:
        """Resolve + validate + build a request WITHOUT sending it."""
        ep = self._resolve_endpoint(endpoint)
        self._enforce_read_only(ep)
        return self._builder.build(ep, parameters)

    def execute(
        self,
        endpoint: Union[str, Endpoint],
        parameters: Optional[Mapping[str, Any]] = None,
        persona: Optional[str] = None,
    ) -> Response:
        """Build the request and delegate to the injected transport.

        Auth is NOT applied here. The persona is validated (if roles are known)
        and forwarded to the transport, which is responsible for credentials.
        """
        ep = self._resolve_endpoint(endpoint)
        self._enforce_read_only(ep)
        self._validate_persona(persona)
        request = self._builder.build(ep, parameters)
        return self._transport.send(request, persona)

    # ------------------------------------------------------------------ #
    def _resolve_endpoint(self, endpoint: Union[str, Endpoint]) -> Endpoint:
        if isinstance(endpoint, Endpoint):
            return endpoint
        found = catalog.by_id(endpoint)
        if found is None:
            raise EndpointNotFound(f"unknown endpoint id '{endpoint}'")
        return found

    def _enforce_read_only(self, endpoint: Endpoint) -> None:
        if endpoint.method.upper() != "GET":
            raise ReadOnlyViolation(
                f"endpoint '{endpoint.id}' uses {endpoint.method}; only GET is allowed"
            )

    def _validate_persona(self, persona: Optional[str]) -> None:
        if persona is None:
            return
        if self._roles and persona not in self._roles:
            raise UnknownPersona(
                f"persona '{persona}' is not a declared role {sorted(self._roles)}"
            )
