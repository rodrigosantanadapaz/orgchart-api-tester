import pytest

from harness.errors import ReferenceResolutionError
from harness.loader import (
    ReferenceResolver,
    SecretValue,
    collect_references,
    load_config,
    resolve_all_references,
)


def _env_for(*docs) -> dict:
    refs = set()
    for doc in docs:
        refs |= set(collect_references(doc))
    return {ref.split(":", 1)[1]: "value" for ref in refs}


def test_secretvalue_never_reveals_in_repr_or_str():
    secret = SecretValue("hunter2")
    assert "hunter2" not in repr(secret)
    assert "hunter2" not in str(secret)
    assert secret.reveal() == "hunter2"


def test_resolver_env_reference():
    resolver = ReferenceResolver(env={"OC_X": "the-value"})
    assert resolver.resolve("env:OC_X").reveal() == "the-value"


def test_resolver_missing_env_fails():
    with pytest.raises(ReferenceResolutionError):
        ReferenceResolver(env={}).resolve("env:MISSING")


def test_resolver_empty_env_fails():
    with pytest.raises(ReferenceResolutionError):
        ReferenceResolver(env={"E": ""}).resolve("env:E")


def test_resolver_bad_syntax_fails():
    with pytest.raises(ReferenceResolutionError):
        ReferenceResolver(env={}).resolve("literal-not-a-ref")


def test_resolver_secret_provider():
    resolver = ReferenceResolver(secret_provider=lambda name: "s3cr3t" if name == "K" else None)
    assert resolver.resolve("secret:K").reveal() == "s3cr3t"
    with pytest.raises(ReferenceResolutionError):
        resolver.resolve("secret:UNKNOWN")


def test_error_message_contains_ref_name_not_value():
    try:
        ReferenceResolver(env={"OC_X": ""}).resolve("env:OC_X")
    except ReferenceResolutionError as exc:
        assert any("env:OC_X" in m for m in exc.messages)


def test_collect_references_finds_all(source, td_suv, td_skylab, write_case):
    loaded = load_config(write_case(source, td_suv, td_skylab))
    refs = collect_references(loaded.resolved)
    assert "env:OC_OAUTH_CLIENT_ID" in refs
    assert "env:OC_OAUTH_CLIENT_SECRET" in refs


def test_resolve_all_aggregates_missing(source, td_suv, td_skylab, write_case):
    loaded = load_config(write_case(source, td_suv, td_skylab))
    with pytest.raises(ReferenceResolutionError) as excinfo:
        resolve_all_references(loaded.resolved, loaded.test_data, ReferenceResolver(env={}))
    assert len(excinfo.value.messages) >= 2


def test_resolve_all_success(source, td_suv, td_skylab, write_case):
    loaded = load_config(write_case(source, td_suv, td_skylab))
    env = _env_for(loaded.resolved, loaded.test_data)
    resolved = resolve_all_references(loaded.resolved, loaded.test_data, ReferenceResolver(env=env))
    expected = set(collect_references(loaded.resolved)) | set(collect_references(loaded.test_data))
    assert set(resolved) == expected
    assert all(isinstance(v, SecretValue) for v in resolved.values())
