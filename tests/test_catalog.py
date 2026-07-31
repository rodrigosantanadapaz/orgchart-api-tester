import json
import re

import pytest

from engine import catalog
from engine.catalog import CATEGORIES, ENDPOINTS, RESPONSE_TYPES, Endpoint

_PATH_PARAM_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")


def test_ids_are_unique():
    ids = [e.id for e in ENDPOINTS]
    assert len(ids) == len(set(ids))


def test_all_endpoints_are_read_only_get():
    assert all(e.method == "GET" for e in ENDPOINTS)


def test_categories_and_response_types_valid():
    for e in ENDPOINTS:
        assert e.category in CATEGORIES
        assert e.response_type in RESPONSE_TYPES


def test_no_request_body_in_v1():
    assert all(e.request_body is None for e in ENDPOINTS)


def test_path_placeholders_have_matching_required_param():
    for e in ENDPOINTS:
        placeholders = set(_PATH_PARAM_RE.findall(e.path))
        declared = {p.name for p in e.path_params()}
        assert placeholders == declared, e.id
        for p in e.path_params():
            assert p.required, f"{e.id}:{p.name} path params must be required"


def test_param_locations_valid():
    for e in ENDPOINTS:
        for p in e.params:
            assert p.location in ("path", "query")


def test_only_navigable_filter_is_repeatable():
    for e in ENDPOINTS:
        for p in e.params:
            if p.repeatable:
                assert p.name == "navigableFilter"


def test_by_id_roundtrip():
    for e in ENDPOINTS:
        assert catalog.by_id(e.id) is e
    assert catalog.by_id("does_not_exist") is None


def test_catalog_is_json_serializable():
    data = catalog.as_dicts()
    text = json.dumps(data)
    assert isinstance(json.loads(text), list)
    assert len(data) == len(ENDPOINTS)


def test_expected_endpoint_set_present():
    expected = {
        "list_navigables", "get_navigable", "get_children", "get_child",
        "get_parent", "get_parent_single", "prompt_organizations",
        "prompt_workers", "prompt_navigable_filters",
    }
    assert {e.id for e in ENDPOINTS} == expected


def test_endpoint_accessors():
    ep = catalog.by_id("get_children")
    assert isinstance(ep, Endpoint)
    assert [p.name for p in ep.path_params()] == ["ID"]
    assert "navigableFilter" in [p.name for p in ep.query_params()]
    assert ep.param("navigableFilter").repeatable is True
    assert ep.param("missing") is None
