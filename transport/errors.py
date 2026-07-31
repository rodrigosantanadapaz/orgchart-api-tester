"""Transport-level exceptions (fail-closed).

Messages are intentionally generic and NEVER include headers, tokens, or
credentials. The originating exception is chained for debugging but httpx
exceptions do not carry auth headers.
"""

from __future__ import annotations

from typing import List, Sequence


class TransportError(Exception):
    """A request could not be completed (network, decoding, protocol, etc.)."""

    def __init__(self, message: str, messages: Sequence[str] | None = None) -> None:
        super().__init__(message)
        self.messages: List[str] = list(messages) if messages is not None else [message]


class TransportTimeout(TransportError):
    """The request exceeded the configured timeout."""
