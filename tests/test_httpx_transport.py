import httpx
import pytest

from engine import catalog
from engine.client import ReadOnlyApiClient
from engine.errors import ReadOnlyViolation
from engine.request_builder import BuiltRequest, RequestBuilder
from transport import HttpxTransport, NullAuthProvider, TransportError, TransportTimeout


@pytest.fixture
def builder(resolved_env):
    return RequestBuilder(resolved_env)


def make_transport(handler, **kwargs):
    """Build an HttpxTransport backed by an in-memory MockTransport (no network)."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return HttpxTransport(client=client, **kwargs)


class StaticAuth:
    def __init__(self, value):
        self._value = value

    def authorization_header(self, persona):
        return self._value


# ------------------------------ success ------------------------------ #
def test_successful_request(builder):
    def handler(request):
        return httpx.Response(200, json={"ok": True, "path": request.url.path})

    transport = make_transport(handler)
    req = builder.build(catalog.by_id("list_navigables"))
    resp = transport.send(req, None)
    assert resp.status == 200
    assert resp.body["ok"] is True
    assert resp.body["path"].endswith("/navigables")


def test_safe_headers_are_forwarded(builder):
    seen = {}

    def handler(request):
        seen["accept"] = request.headers.get("accept")
        return httpx.Response(200, json={})

    transport = make_transport(handler)
    transport.send(builder.build(catalog.by_id("list_navigables")), None)
    assert seen["accept"] == "application/json"


# ------------------------------ HTTP errors -------------------------- #
def test_http_error_status_returned_not_raised(builder):
    def handler(request):
        return httpx.Response(404, json={"error": "not found"})

    transport = make_transport(handler)
    resp = transport.send(builder.build(catalog.by_id("list_navigables")), None)
    assert resp.status == 404
    assert resp.body["error"] == "not found"


# ------------------------------ timeouts ----------------------------- #
def test_timeout_raises(builder):
    def handler(request):
        raise httpx.ReadTimeout("timed out", request=request)

    transport = make_transport(handler)
    with pytest.raises(TransportTimeout):
        transport.send(builder.build(catalog.by_id("list_navigables")), None)


# ------------------------------ network failure ---------------------- #
def test_network_failure_raises(builder):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    transport = make_transport(handler)
    with pytest.raises(TransportError):
        transport.send(builder.build(catalog.by_id("list_navigables")), None)


# ------------------------------ malformed JSON ----------------------- #
def test_malformed_json_raises(builder):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/json"}, content=b"{ not json")

    transport = make_transport(handler)
    with pytest.raises(TransportError):
        transport.send(builder.build(catalog.by_id("list_navigables")), None)


# ------------------------------ content types ------------------------ #
def test_unexpected_content_type_returned_as_text(builder):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html>ok</html>")

    transport = make_transport(handler)
    resp = transport.send(builder.build(catalog.by_id("list_navigables")), None)
    assert resp.status == 200
    assert resp.body == "<html>ok</html>"


# ------------------------------ GET-only ----------------------------- #
def test_get_only_enforced():
    transport = make_transport(lambda request: httpx.Response(200, json={}))
    bad = BuiltRequest(method="POST", url="https://example.com/x", headers={}, query=[], path_params={})
    with pytest.raises(ReadOnlyViolation):
        transport.send(bad, None)


# ------------------------------ auth seam ---------------------------- #
def test_authorization_header_injected(builder):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    transport = make_transport(handler, auth_provider=StaticAuth("Bearer tok123"))
    transport.send(builder.build(catalog.by_id("list_navigables")), persona="A")
    assert seen["auth"] == "Bearer tok123"


def test_no_authorization_header_without_provider(builder):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    transport = make_transport(handler, auth_provider=NullAuthProvider())
    transport.send(builder.build(catalog.by_id("list_navigables")), persona="A")
    assert seen["auth"] is None


def test_token_never_appears_in_exception(builder):
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    transport = make_transport(handler, auth_provider=StaticAuth("Bearer supersecret"))
    with pytest.raises(TransportError) as exc:
        transport.send(builder.build(catalog.by_id("list_navigables")), persona="A")
    assert "supersecret" not in str(exc.value)
    assert "supersecret" not in repr(exc.value)


# ------------------------------ config respect ----------------------- #
def test_from_resolved_respects_tls_and_timeouts():
    resolved = {"tls": {"verify": False}, "timeouts": {"connectMs": 1000, "readMs": 2000, "tokenMs": 15000}}
    transport = HttpxTransport.from_resolved(resolved)
    assert transport.verify is False
    assert transport.timeout.connect == 1.0
    assert transport.timeout.read == 2.0


def test_from_resolved_defaults_verify_true():
    transport = HttpxTransport.from_resolved({})
    assert transport.verify is True


def test_verify_false_client_can_be_created():
    transport = HttpxTransport(verify=False)
    client = transport._get_client()
    assert isinstance(client, httpx.Client)
    transport.close()


# ------------------------------ swap-in ------------------------------ #
def test_swaps_into_readonly_client_end_to_end(resolved_env):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"resolved": True})

    transport = make_transport(handler)
    client = ReadOnlyApiClient(resolved_env, transport=transport)
    resp = client.execute("get_navigable", {"ID": "w1"}, persona="A")
    assert resp.status == 200
    assert resp.body == {"resolved": True}
    assert seen["url"].endswith("/navigables/w1")
