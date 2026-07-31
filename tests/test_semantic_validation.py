import pytest

from harness.errors import SemanticValidationError
from harness.loader import load_config


def test_default_limit_exceeds_max_rejected(source, td_suv, td_skylab, write_case):
    source["defaults"]["pagination"]["defaultLimit"] = 200  # > maxLimit (100)
    with pytest.raises(SemanticValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_test_data_environment_mismatch_rejected(source, td_suv, td_skylab, write_case):
    # active env is suv, but the suv test-data claims skylab
    td_suv["environment"] = "skylab"
    with pytest.raises(SemanticValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_roles_without_persona_rejected(source, td_suv, td_skylab, write_case):
    # roles A-D declared, but persona D removed from the (active) suv test-data
    del td_suv["personas"]["D"]
    with pytest.raises(SemanticValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_persona_without_role_rejected(source, td_suv, td_skylab, write_case):
    source["defaults"]["roles"] = ["A", "B", "C"]  # D persona present but not declared
    with pytest.raises(SemanticValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_matching_role_subset_ok(source, td_suv, td_skylab, write_case):
    source["defaults"]["roles"] = ["A", "B"]
    td_suv["personas"] = {k: v for k, v in td_suv["personas"].items() if k in ("A", "B")}
    loaded = load_config(write_case(source, td_suv, td_skylab))
    assert set(loaded.resolved["roles"]) == {"A", "B"}
    assert set(loaded.test_data["personas"]) == {"A", "B"}
