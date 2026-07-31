"""Temporary, in-memory Authorization provider for a connection session.

This is NOT OAuth. It holds a single static ``Authorization`` header value in
memory for the life of a connection and hands it to the transport's auth seam
(``AuthProvider``). ``clear()`` zeroes the value on disconnect so no credential
outlives the session. Nothing here is ever serialized or written to disk, and
the value is redacted from ``repr``.
"""

from __future__ import annotations

from typing import Optional


class StaticSessionAuthProvider:
    """Implements the transport ``AuthProvider`` protocol with a fixed header."""

    __slots__ = ("_value",)

    def __init__(self, header_value: str) -> None:
        self._value: Optional[str] = header_value

    def authorization_header(self, persona: Optional[str]) -> Optional[str]:
        # Static: the persona does not change the header in this temporary model.
        return self._value

    def clear(self) -> None:
        self._value = None

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "<StaticSessionAuthProvider redacted>"
