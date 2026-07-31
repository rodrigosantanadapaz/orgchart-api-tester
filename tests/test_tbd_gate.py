import pytest

from harness.errors import RuntimeNotReadyError
from harness.loader import (
    ReferenceResolver,
    SecretValue,
    assert_runtime_ready,
    collect_references,
    find_tbd,
    load_config,
    prepare_for_execution,
)
from tests.conftest import make_ready


def _env_for(*docs) -> dict:
    refs = set()
    for doc in docs:
        refs |= set(collect_references(doc))
    return {ref.split(":", 1)[1]: "value" for ref in refs}


def test_find_tbd_reports_default_unknowns(source, td_suv, td_skylab, write_case):
    loaded = load_config(write_case(source, td_suv, td_skylab))
    tbd = find_tbd(loaded.resolved, loaded.test_data)
    assert "host" in tbd
    assert "auth.model" in tbd
    assert "toggle.name" in tbd
    assert "toggle.expectedState" in tbd
    assert any(item.startswith("wids.") for item in tbd)
    assert any(item.startswith("filters.") for item in tbd)


def test_assert_runtime_ready_raises_when_tbd(source, td_suv, td_skylab, write_case):
    loaded = load_config(write_case(source, td_suv, td_skylab))
    with pytest.raises(RuntimeNotReadyError):
        assert_runtime_ready(loaded.resolved, loaded.test_data)


def test_prepare_fails_closed_on_tbd_before_resolving_refs(source, td_suv, td_skylab, write_case):
    config_path = write_case(source, td_suv, td_skylab)
    # No env vars set: if refs were resolved first we'd see ReferenceResolutionError.
    # The TBD gate must trip FIRST, proving execution is blocked before any request.
    with pytest.raises(RuntimeNotReadyError):
        prepare_for_execution(config_path, resolver=ReferenceResolver(env={}))


def test_runtime_ready_when_all_filled(source, td_suv, td_skylab, write_case):
    ready_source, ready_td = make_ready(source, td_suv)
    loaded = load_config(write_case(ready_source, ready_td, td_skylab))
    assert_runtime_ready(loaded.resolved, loaded.test_data)  # must not raise
    assert find_tbd(loaded.resolved, loaded.test_data) == []


def test_prepare_succeeds_when_ready(source, td_suv, td_skylab, write_case):
    ready_source, ready_td = make_ready(source, td_suv)
    config_path = write_case(ready_source, ready_td, td_skylab)
    loaded = load_config(config_path)
    env = _env_for(loaded.resolved, loaded.test_data)
    loaded2, secrets = prepare_for_execution(config_path, resolver=ReferenceResolver(env=env))
    assert loaded2.resolved["host"] == "host.example.com"
    assert secrets
    assert all(isinstance(v, SecretValue) for v in secrets.values())


def test_acting_as_mechanism_tbd_when_client_credentials(source, td_suv, td_skylab, write_case):
    ready_source, ready_td = make_ready(source, td_suv)
    ready_source["environments"]["suv"]["auth"] = {"model": "oauth2_client_credentials_acting_as"}
    loaded = load_config(write_case(ready_source, ready_td, td_skylab))
    tbd = find_tbd(loaded.resolved, loaded.test_data)
    assert "auth.actingAs.mechanism" in tbd


def test_required_subset_gating(source, td_suv, td_skylab, write_case):
    ready_source, ready_td = make_ready(source, td_suv)
    ready_td["wids"]["ORG_VIS"] = "TBD"  # single remaining unknown
    loaded = load_config(write_case(ready_source, ready_td, td_skylab))
    # A test that does not need ORG_VIS is ready:
    assert_runtime_ready(
        loaded.resolved,
        loaded.test_data,
        required_wids=["WKR_VIS"],
        required_filters=["FLT_OK"],
    )
    # A test that needs ORG_VIS is blocked:
    with pytest.raises(RuntimeNotReadyError):
        assert_runtime_ready(loaded.resolved, loaded.test_data, required_wids=["ORG_VIS"])
