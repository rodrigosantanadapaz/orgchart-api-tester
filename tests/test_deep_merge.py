import pytest

from harness.errors import SemanticValidationError
from harness.loader import deep_merge, resolve_environment


def test_objects_merge_recursively():
    base = {"a": {"x": 1, "y": 2}, "k": 1}
    over = {"a": {"y": 20, "z": 3}}
    assert deep_merge(base, over) == {"a": {"x": 1, "y": 20, "z": 3}, "k": 1}


def test_arrays_replace_not_concatenated():
    assert deep_merge({"a": [1, 2, 3]}, {"a": [9]}) == {"a": [9]}


def test_scalars_replace():
    assert deep_merge({"a": 1, "b": "x"}, {"a": 2}) == {"a": 2, "b": "x"}


def test_new_keys_are_added():
    assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1}, "list": [1]}
    over = {"a": {"y": 2}, "list": [2]}
    deep_merge(base, over)
    assert base == {"a": {"x": 1}, "list": [1]}
    assert over == {"a": {"y": 2}, "list": [2]}


def test_resolve_environment_injects_active_and_merges(source):
    resolved = resolve_environment(source)
    assert resolved["activeEnvironment"] == "suv"
    # environment override wins
    assert "internalapi" in resolved["restBaseTemplate"]
    assert resolved["evidence"]["collect"] is False
    # defaults are preserved through the merge
    assert resolved["tenant"] == "super"
    assert resolved["evidence"]["redactHeaders"] == ["authorization", "cookie", "set-cookie"]
    assert resolved["roles"] == ["A", "B", "C", "D"]


def test_resolve_environment_skylab_gets_evidence_dir(source):
    source["activeEnvironment"] = "skylab"
    resolved = resolve_environment(source)
    assert resolved["evidence"]["collect"] is True
    assert resolved["evidence"]["dir"] == "evidence/skylab/{testId}"


def test_resolve_environment_missing_active_raises(source):
    source["activeEnvironment"] = "skylab"
    del source["environments"]["skylab"]
    with pytest.raises(SemanticValidationError):
        resolve_environment(source)
