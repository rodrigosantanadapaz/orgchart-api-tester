"""Read-only HTTP transport layer (ORG-21922).

Provides a production ``HttpxTransport`` that implements the frozen
``engine.Transport`` protocol, plus the ``AuthProvider`` seam it will use once
authentication is implemented. Swappable for ``MockTransport`` with no changes
to the UI, RequestBuilder, or engine.
"""

from __future__ import annotations

from .auth import AuthProvider, NullAuthProvider
from .errors import TransportError, TransportTimeout
from .httpx_transport import HttpxTransport

__all__ = [
    "HttpxTransport",
    "AuthProvider",
    "NullAuthProvider",
    "TransportError",
    "TransportTimeout",
]
