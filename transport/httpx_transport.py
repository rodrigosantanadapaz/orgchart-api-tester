"""Production read-only HTTP transport built on httpx.

Implements the frozen ``engine.Transport`` protocol so it can be swapped in for
``MockTransport`` without touching the UI, RequestBuilder, or engine. It:

  * sends only GET requests (raises ``ReadOnlyViolation`` otherwise);
  * uses URLs/headers exactly as produced by the RequestBuilder;
  * respects TLS ``verify`` and timeouts from the resolved environment;
  * injects ``Authorization`` only via an optional ``AuthProvider``;
  * never logs credentials or tokens;
  * fails closed: network/timeout/decoding problems raise ``TransportError``.

HTTP error statuses (4xx/5xx) are NOT raised — they are returned as a
``Response`` so the tester can display them.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

import httpx

from engine.client import Response
from engine.errors import ReadOnlyViolation
from engine.request_builder import BuiltRequest

from .auth import AuthProvider, NullAuthProvider
from .errors import TransportError, TransportTimeout

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)


def _ms_to_s(value: Any, default_ms: float) -> float:
    return (float(value) if value is not None else float(default_ms)) / 1000.0


class HttpxTransport:
    def __init__(
        self,
        *,
        verify: bool = True,
        timeout: Optional[httpx.Timeout] = None,
        auth_provider: Optional[AuthProvider] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._verify = bool(verify)
        self._timeout = timeout or _DEFAULT_TIMEOUT
        self._auth = auth_provider or NullAuthProvider()
        self._client = client
        self._owns_client = client is None

    # -- introspection (for config-respect assertions) ------------------ #
    @property
    def verify(self) -> bool:
        return self._verify

    @property
    def timeout(self) -> httpx.Timeout:
        return self._timeout

    # -- construction from resolved config ------------------------------ #
    @classmethod
    def from_resolved(
        cls,
        resolved: Mapping[str, Any],
        *,
        auth_provider: Optional[AuthProvider] = None,
        client: Optional[httpx.Client] = None,
    ) -> "HttpxTransport":
        verify = bool(resolved.get("tls", {}).get("verify", True))
        timeouts = resolved.get("timeouts", {})
        timeout = httpx.Timeout(
            connect=_ms_to_s(timeouts.get("connectMs"), 5000),
            read=_ms_to_s(timeouts.get("readMs"), 30000),
            write=_ms_to_s(timeouts.get("readMs"), 30000),
            pool=_ms_to_s(timeouts.get("connectMs"), 5000),
        )
        return cls(verify=verify, timeout=timeout, auth_provider=auth_provider, client=client)

    # -- transport ------------------------------------------------------ #
    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(verify=self._verify, timeout=self._timeout)
        return self._client

    def send(self, request: BuiltRequest, persona: Optional[str]) -> Response:
        if request.method.upper() != "GET":
            raise ReadOnlyViolation(
                f"HttpxTransport is read-only (GET only); got {request.method}"
            )

        headers = dict(request.headers)  # safe headers from the builder
        auth_value = self._auth.authorization_header(persona)
        if auth_value:
            headers["Authorization"] = auth_value  # never logged

        client = self._get_client()
        try:
            resp = client.get(request.url, headers=headers, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise TransportTimeout("request timed out") from exc
        except httpx.HTTPError as exc:
            # httpx errors do not carry auth headers; message is kept generic.
            raise TransportError("network error while contacting the API") from exc

        return self._to_response(resp)

    def _to_response(self, resp: httpx.Response) -> Response:
        headers = dict(resp.headers)
        content_type = resp.headers.get("content-type", "").lower()
        if "json" in content_type:
            try:
                body: Any = resp.json()
            except json.JSONDecodeError as exc:
                raise TransportError(
                    f"malformed JSON in response (HTTP {resp.status_code})"
                ) from exc
        else:
            # Unexpected content type: return the raw text unparsed.
            body = resp.text
        return Response(status=resp.status_code, headers=headers, body=body)

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "HttpxTransport":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
