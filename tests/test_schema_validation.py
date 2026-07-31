import pytest

from harness.errors import SchemaValidationError
from harness.loader import load_config


# --------------------------- valid documents --------------------------- #
def test_valid_suv_loads(source, td_suv, td_skylab, write_case):
    loaded = load_config(write_case(source, td_suv, td_skylab))
    assert loaded.resolved["activeEnvironment"] == "suv"
    assert loaded.test_data["environment"] == "suv"


def test_valid_skylab_loads(source, td_suv, td_skylab, write_case):
    source["activeEnvironment"] = "skylab"
    loaded = load_config(write_case(source, td_suv, td_skylab))
    assert loaded.resolved["evidence"]["collect"] is True
    assert loaded.resolved["evidence"]["dir"]


# --------------------------- environment.schema --------------------------- #
def test_skylab_tls_verify_false_rejected(source, td_suv, td_skylab, write_case):
    source["environments"]["skylab"]["tls"] = {"verify": False}
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_suv_tls_false_without_reason_rejected(source, td_suv, td_skylab, write_case):
    source["environments"]["suv"]["tls"] = {"verify": False}
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_suv_tls_false_with_reason_ok(source, td_suv, td_skylab, write_case):
    source["environments"]["suv"]["tls"] = {"verify": False, "reason": "self-signed dev cert"}
    loaded = load_config(write_case(source, td_suv, td_skylab))
    assert loaded.resolved["tls"] == {"verify": False, "reason": "self-signed dev cert"}


def test_default_headers_reject_authorization(source, td_suv, td_skylab, write_case):
    source["defaults"]["defaultHeaders"]["Authorization"] = "Bearer x"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_secret_literal_key_rejected(source, td_suv, td_skylab, write_case):
    source["defaults"]["auth"]["clientSecret"] = "supersecret"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_bad_credential_ref_rejected(source, td_suv, td_skylab, write_case):
    source["defaults"]["auth"]["clientIdRef"] = "literal-not-a-ref"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_timeouts_minimum_one(source, td_suv, td_skylab, write_case):
    source["defaults"]["timeouts"]["connectMs"] = 0
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_pagination_minimum_one(source, td_suv, td_skylab, write_case):
    source["defaults"]["pagination"]["defaultLimit"] = 0
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_extra_environment_key_rejected(source, td_suv, td_skylab, write_case):
    source["environments"]["preview"] = {
        "host": "x",
        "tls": {"verify": True},
        "evidence": {"collect": False},
        "testDataRef": "./x.json",
    }
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_suv_evidence_collect_true_rejected(source, td_suv, td_skylab, write_case):
    source["environments"]["suv"]["evidence"] = {"collect": True}
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_unknown_toggle_state_rejected(source, td_suv, td_skylab, write_case):
    source["defaults"]["toggle"]["expectedState"] = "maybe"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


# --------------------------- test-data.schema --------------------------- #
def test_wid_bad_format_rejected(source, td_suv, td_skylab, write_case):
    td_suv["wids"]["ORG_VIS"] = "NOTHEX"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_wid_valid_hex_ok(source, td_suv, td_skylab, write_case):
    td_suv["wids"]["ORG_VIS"] = "0" * 31 + "a"
    loaded = load_config(write_case(source, td_suv, td_skylab))
    assert loaded.test_data["wids"]["ORG_VIS"] == "0" * 31 + "a"


def test_persona_identity_must_be_reference(source, td_suv, td_skylab, write_case):
    td_suv["personas"]["A"]["identityRef"] = "oreynolds"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_persona_literal_secret_field_rejected(source, td_suv, td_skylab, write_case):
    td_suv["personas"]["A"]["token"] = "abc123"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_skylab_requires_all_four_personas(source, td_suv, td_skylab, write_case):
    source["activeEnvironment"] = "skylab"
    del td_skylab["personas"]["D"]
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_missing_required_wid_label_rejected(source, td_suv, td_skylab, write_case):
    del td_suv["wids"]["ORG_VIS"]
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))


def test_extra_wid_label_rejected(source, td_suv, td_skylab, write_case):
    td_suv["wids"]["SURPRISE"] = "TBD"
    with pytest.raises(SchemaValidationError):
        load_config(write_case(source, td_suv, td_skylab))
