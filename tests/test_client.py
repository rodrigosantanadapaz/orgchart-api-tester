import pytest

from engine import catalog
from engine.catalog import Endpoint, Param
from engine.client import ReadOnlyApiClient, Response, Transport, UnconfiguredTransport
from engine.errors import (
    EndpointNotFound,
    ReadOnlyViolation,
    TransportNotConfigured,
    UnknownPersona,
)
from engine.request_builder import BuiltRequest


class RecordingTransport:
    """Fake transport that records what it was asked to send."""

    def __init__(self, response: Response | None = None):
        self.calls: list[tuple[BuiltRequest, str | None]] = []
        self._response = response or Response(status=200, headers={}, body={"ok": True})

    def send(self, request: BuiltRequest, persona):
        self.calls.append((request, persona))
        return self._response


def test_recording_transport_satisfies_protocol():
    assert isinstance(RecordingTransport(), Transport)


def test_execute_delegates_to_transport(resolved_env):
    transport = RecordingTransport()
    client = ReadOnlyApiClient(resolved_env, transport=transport)
    resp = client.execute("get_navigable", {"ID": "w1"}, persona="A")
    assert resp.status == 200
    assert len(transport.calls) == 1
    built, persona = transport.calls[0]
    assert persona == "A"
    assert built.endpoint_id == "get_navigable"
    assert built.url.endswith("/navigables/w1")


def test_default_transport_fails_closed(resolved_env):
    client = ReadOnlyApiClient(resolved_env)
    assert isinstance(client._transport, UnconfiguredTransport)
    with pytest.raises(TransportNotConfigured):
        client.execute("list_navigables")


def test_build_does_not_require_transport(resolved_env):
    client = ReadOnlyApiClient(resolved_env)
    built = client.build("list_navigables", {"limit": 5})
    assert built.url.endswith("/navigables?limit=5")


def test_unknown_endpoint_raises(resolved_env):
    client = ReadOnlyApiClient(resolved_env, transport=RecordingTransport())
    with pytest.raises(EndpointNotFound):
        client.execute("nope")


def test_non_get_endpoint_rejected(resolved_env):
    mutating = Endpoint(
        id="delete_navigable",
        method="DELETE",
        path="/navigables/{ID}",
        category="navigables",
        summary="(hypothetical) delete",
        params=[Param("ID", "path", required=True)],
    )
    client = ReadOnlyApiClient(resolved_env, transport=RecordingTransport())
    with pytest.raises(ReadOnlyViolation):
        client.execute(mutating, {"ID": "x"})


def test_unknown_persona_rejected(resolved_env):
    client = ReadOnlyApiClient(resolved_env, transport=RecordingTransport())
    with pytest.raises(UnknownPersona):
        client.execute("list_navigables", persona="Z")


def test_persona_optional(resolved_env):
    transport = RecordingTransport()
    client = ReadOnlyApiClient(resolved_env, transport=transport)
    client.execute("list_navigables")
    assert transport.calls[0][1] is None


def test_built_request_carries_no_credentials(resolved_env):
    transport = RecordingTransport()
    client = ReadOnlyApiClient(resolved_env, transport=transport)
    client.execute("list_navigables", persona="B")
    built = transport.calls[0][0]
    header_keys = {k.lower() for k in built.headers}
    assert "authorization" not in header_keys
    assert "cookie" not in header_keys
