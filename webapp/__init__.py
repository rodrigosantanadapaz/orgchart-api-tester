"""Web application layer for the Org Chart API Tester (ORG-21922).

A thin FastAPI app + static SPA on top of the frozen engine/loader. Auth and
HTTP transport are mocked; this milestone delivers a fully functional UI ready
to plug into the future authentication layer.
"""

from __future__ import annotations

from .app import create_app
from .service import ExecutionService

__all__ = ["create_app", "ExecutionService"]
