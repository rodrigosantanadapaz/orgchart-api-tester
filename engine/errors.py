"""Exceptions for the read-only Org Chart execution engine."""

from __future__ import annotations

from typing import List, Sequence


class EngineError(Exception):
    """Base class for engine failures."""

    def __init__(self, message: str, messages: Sequence[str] | None = None) -> None:
        super().__init__(message)
        self.messages: List[str] = list(messages) if messages is not None else [message]


class EndpointNotFound(EngineError):
    """Requested endpoint id/definition does not exist in the catalog."""


class RequestValidationError(EngineError):
    """Provided parameters do not satisfy the endpoint definition."""

    def __init__(self, messages: Sequence[str]) -> None:
        text = "request validation failed:\n  - " + "\n  - ".join(messages)
        super().__init__(text, messages)


class ReadOnlyViolation(EngineError):
    """Attempted to execute a non-GET (mutating) endpoint through the read-only client."""


class UnknownPersona(EngineError):
    """Persona is not one of the declared roles for the active environment."""


class TransportNotConfigured(EngineError):
    """No HTTP transport was injected; the engine cannot send requests yet."""
