"""Authentication seam for the transport layer.

This milestone does NOT implement authentication. It only defines the minimal
abstraction the transport needs so a future ``AuthProvider`` can supply an
``Authorization`` header per persona. The transport works without auth (using
``NullAuthProvider``) so unit tests need no credentials.

Implementations MUST NOT log the returned value; the transport treats it as a
secret and only ever places it in the outbound ``Authorization`` header.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class AuthProvider(Protocol):
    def authorization_header(self, persona: Optional[str]) -> Optional[str]:
        """Return a full ``Authorization`` header value (e.g. ``"Bearer <token>"``)
        for the given persona, or ``None`` for an unauthenticated request."""
        ...


class NullAuthProvider:
    """Default provider used until real authentication exists: adds no header."""

    def authorization_header(self, persona: Optional[str]) -> Optional[str]:
        return None
