"""Builds a concrete HTTP request description from an endpoint + parameters.

The builder is transport-agnostic and stateless per call. It:
  * validates required path params and rejects unknown params;
  * substitutes ``{ID}``/``{subresourceID}`` and percent-encodes values;
  * assembles the query string (supporting repeatable params);
  * copies the environment's ``defaultHeaders`` allowlist.

It NEVER adds credentials. Auth headers are the responsibility of a future auth
layer that decorates the request at send time; ``BuiltRequest`` therefore cannot
carry a secret produced by this builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import quote, urlencode

from .catalog import Endpoint
from .errors import RequestValidationError

# Header names that must never be present in a built request's headers. Auth is
# applied later by the transport/auth layer, not baked into the request here.
_FORBIDDEN_HEADERS = {"authorization", "cookie", "set-cookie"}


@dataclass(frozen=True)
class BuiltRequest:
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    query: List[Tuple[str, str]] = field(default_factory=list)
    path_params: Dict[str, str] = field(default_factory=dict)
    endpoint_id: str = ""


class RequestBuilder:
    """Turns ``(endpoint, parameters)`` into a :class:`BuiltRequest`.

    Requires only the small subset of the resolved configuration needed to
    address the API: ``restBaseTemplate``, ``host``, ``tenant``, and
    ``defaultHeaders``.
    """

    def __init__(self, resolved: Mapping[str, Any]) -> None:
        for key in ("restBaseTemplate", "host", "tenant"):
            if key not in resolved:
                raise RequestValidationError([f"resolved config missing required key '{key}'"])
        self._template = resolved["restBaseTemplate"]
        self._host = resolved["host"]
        self._tenant = resolved["tenant"]
        self._default_headers = dict(resolved.get("defaultHeaders", {}))

    # ------------------------------------------------------------------ #
    def build(
        self,
        endpoint: Endpoint,
        parameters: Optional[Mapping[str, Any]] = None,
    ) -> BuiltRequest:
        parameters = dict(parameters or {})
        problems: List[str] = []

        known = {p.name: p for p in endpoint.params}
        for name in parameters:
            if name not in known:
                problems.append(f"unknown parameter '{name}' for endpoint '{endpoint.id}'")

        # Required path params must be present and non-empty.
        for param in endpoint.path_params():
            if param.required and not _is_nonempty(parameters.get(param.name)):
                problems.append(f"missing required path parameter '{param.name}'")

        # Required query params (none in v1, but supported for completeness).
        for param in endpoint.query_params():
            if param.required and param.name not in parameters:
                problems.append(f"missing required query parameter '{param.name}'")

        # Repeatable-only lists.
        for name, value in parameters.items():
            param = known.get(name)
            if param is None:
                continue
            if isinstance(value, (list, tuple)) and not param.repeatable:
                problems.append(f"parameter '{name}' does not accept multiple values")
            if param.location == "path" and isinstance(value, (list, tuple)):
                problems.append(f"path parameter '{name}' cannot be a list")

        if problems:
            raise RequestValidationError(problems)

        path_values: Dict[str, str] = {}
        for param in endpoint.path_params():
            if param.name in parameters:
                path_values[param.name] = _to_str(parameters[param.name])

        url = self._build_url(endpoint.path, path_values)
        query = self._build_query(endpoint, parameters)
        full_url = url + ("?" + urlencode(query) if query else "")

        return BuiltRequest(
            method=endpoint.method,
            url=full_url,
            headers=self._safe_headers(),
            query=query,
            path_params=path_values,
            endpoint_id=endpoint.id,
        )

    # ------------------------------------------------------------------ #
    def _base(self) -> str:
        return self._template.format(host=self._host, tenant=self._tenant)

    def _build_url(self, path: str, path_values: Mapping[str, str]) -> str:
        rendered = path
        for name, value in path_values.items():
            rendered = rendered.replace("{" + name + "}", quote(value, safe=""))
        return self._base() + rendered

    def _build_query(
        self, endpoint: Endpoint, parameters: Mapping[str, Any]
    ) -> List[Tuple[str, str]]:
        pairs: List[Tuple[str, str]] = []
        # Preserve endpoint-declared order for deterministic URLs.
        for param in endpoint.query_params():
            if param.name not in parameters:
                continue
            value = parameters[param.name]
            if isinstance(value, (list, tuple)):
                for item in value:
                    pairs.append((param.name, _to_str(item)))
            else:
                pairs.append((param.name, _to_str(value)))
        return pairs

    def _safe_headers(self) -> Dict[str, str]:
        headers = {
            k: v for k, v in self._default_headers.items()
            if k.lower() not in _FORBIDDEN_HEADERS
        }
        return headers


def _is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _to_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
