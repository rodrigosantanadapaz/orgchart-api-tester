import pytest

from engine import catalog
from engine.errors import RequestValidationError
from engine.request_builder import RequestBuilder

BASE = "https://suv.example.com/ccx/internalapi/orgchart/v1/super"


@pytest.fixture
def builder(resolved_env):
    return RequestBuilder(resolved_env)


def test_list_navigables_url(builder):
    req = builder.build(catalog.by_id("list_navigables"))
    assert req.method == "GET"
    assert req.url == f"{BASE}/navigables"


def test_list_navigables_with_pagination(builder):
    req = builder.build(catalog.by_id("list_navigables"), {"limit": 20, "offset": 40})
    assert req.url == f"{BASE}/navigables?limit=20&offset=40"
    assert req.query == [("limit", "20"), ("offset", "40")]


def test_path_param_substitution_and_encoding(builder):
    req = builder.build(catalog.by_id("get_navigable"), {"ID": "abc/def 1"})
    assert req.url == f"{BASE}/navigables/abc%2Fdef%201"
    assert req.path_params == {"ID": "abc/def 1"}


def test_two_path_params(builder):
    req = builder.build(
        catalog.by_id("get_child"),
        {"ID": "parent1", "subresourceID": "child1"},
    )
    assert req.url == f"{BASE}/navigables/parent1/children/child1"


def test_repeatable_navigable_filter(builder):
    req = builder.build(
        catalog.by_id("get_children"),
        {"ID": "p1", "navigableFilter": ["w1", "w2"], "limit": 10},
    )
    assert req.query == [("navigableFilter", "w1"), ("navigableFilter", "w2"), ("limit", "10")]
    assert "navigableFilter=w1&navigableFilter=w2&limit=10" in req.url


def test_query_order_follows_endpoint_definition(builder):
    # offset provided before limit in the input, but declared order is limit, offset
    req = builder.build(catalog.by_id("list_navigables"), {"offset": 5, "limit": 2})
    assert req.query == [("limit", "2"), ("offset", "5")]


def test_prompt_trailing_slash_preserved(builder):
    req = builder.build(catalog.by_id("prompt_workers"), {"search": "Logan"})
    assert req.url == f"{BASE}/values/orgChartPrompts/workers/?search=Logan"


def test_missing_required_path_param_raises(builder):
    with pytest.raises(RequestValidationError) as exc:
        builder.build(catalog.by_id("get_navigable"), {})
    assert any("ID" in m for m in exc.value.messages)


def test_empty_required_path_param_raises(builder):
    with pytest.raises(RequestValidationError):
        builder.build(catalog.by_id("get_navigable"), {"ID": "   "})


def test_unknown_parameter_raises(builder):
    with pytest.raises(RequestValidationError) as exc:
        builder.build(catalog.by_id("list_navigables"), {"bogus": "x"})
    assert any("bogus" in m for m in exc.value.messages)


def test_multiple_values_on_non_repeatable_raises(builder):
    with pytest.raises(RequestValidationError):
        builder.build(catalog.by_id("list_navigables"), {"limit": [1, 2]})


def test_headers_come_from_defaults_and_have_no_secrets(builder):
    req = builder.build(catalog.by_id("list_navigables"))
    assert req.headers == {"Accept": "application/json", "Accept-Language": "en-US"}
    lowered = {k.lower() for k in req.headers}
    assert "authorization" not in lowered
    assert "cookie" not in lowered


def test_forbidden_default_header_is_stripped():
    resolved = {
        "restBaseTemplate": "https://{host}/x/{tenant}",
        "host": "h",
        "tenant": "t",
        "defaultHeaders": {"Accept": "application/json", "Authorization": "Bearer leaked"},
    }
    req = RequestBuilder(resolved).build(catalog.by_id("list_navigables"))
    assert "Authorization" not in req.headers
    assert "Bearer leaked" not in str(req.headers)


def test_builder_requires_addressing_keys():
    with pytest.raises(RequestValidationError):
        RequestBuilder({"host": "h", "tenant": "t"})  # missing restBaseTemplate
