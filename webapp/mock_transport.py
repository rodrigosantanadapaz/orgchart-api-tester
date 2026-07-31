"""Mock transport for the web layer.

Implements the frozen ``engine.Transport`` protocol so the UI is fully
functional WITHOUT a real HTTP client or authentication. It never performs
network I/O; it echoes the built request back as a deterministic-shaped mock
response. Replaced later by a real httpx transport behind the same seam.
"""

from __future__ import annotations

import uuid
from typing import Optional

from engine.client import Response
from engine.request_builder import BuiltRequest


class MockTransport:
    """Returns a canned 200 response describing the request that would be sent."""

    def send(self, request: BuiltRequest, persona: Optional[str]) -> Response:
        body = {
            "_mock": True,
            "message": (
                "Mocked response — authentication and real HTTP transport are not "
                "implemented yet. This echoes the request the engine built."
            ),
            "endpoint": request.endpoint_id,
            "method": request.method,
            "requestUrl": request.url,
            "pathParams": request.path_params,
            "query": [list(pair) for pair in request.query],
            "persona": persona,
        }
        headers = {
            "content-type": "application/json",
            "x-mock": "true",
            "wd-stat-request-id": uuid.uuid4().hex,
        }
        return Response(status=200, headers=headers, body=body)
