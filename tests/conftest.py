"""Shared fixtures for the harness tests.

Each test starts from the real, committed configuration/test-data documents,
deep-copies them, optionally mutates the copy, writes it to a temporary
directory, and runs it through the public loader API. This exercises the whole
pipeline (schema + semantic + resolution) end-to-end.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR / "config"


def _load(name: str) -> dict:
    return json.loads((CONFIG_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def source() -> dict:
    return _load("environment.json")


@pytest.fixture
def td_suv() -> dict:
    return _load("test-data.suv.json")


@pytest.fixture
def td_skylab() -> dict:
    return _load("test-data.skylab.json")


@pytest.fixture
def write_case(tmp_path):
    """Write a source doc + test-data files to a temp dir; return the config path."""

    def _write(source_doc: dict, suv: dict | None = None, skylab: dict | None = None) -> Path:
        config_path = tmp_path / "environment.json"
        config_path.write_text(json.dumps(source_doc), encoding="utf-8")
        if suv is not None:
            (tmp_path / "test-data.suv.json").write_text(json.dumps(suv), encoding="utf-8")
        if skylab is not None:
            (tmp_path / "test-data.skylab.json").write_text(json.dumps(skylab), encoding="utf-8")
        return config_path

    return _write


@pytest.fixture
def resolved_env() -> dict:
    """A minimal, runtime-shaped resolved config for engine tests (host filled)."""
    return {
        "activeEnvironment": "suv",
        "tenant": "super",
        "restBaseTemplate": "https://{host}/ccx/internalapi/orgchart/v1/{tenant}",
        "host": "suv.example.com",
        "defaultHeaders": {"Accept": "application/json", "Accept-Language": "en-US"},
        "roles": ["A", "B", "C", "D"],
    }


def make_ready(source_doc: dict, test_data: dict) -> tuple[dict, dict]:
    """Return copies with every runtime-required TBD filled in (for the active env)."""
    source_doc = copy.deepcopy(source_doc)
    test_data = copy.deepcopy(test_data)
    active = source_doc["activeEnvironment"]
    env = source_doc["environments"][active]
    env["host"] = "host.example.com"
    env["auth"] = {"model": "oauth2_refresh_token_per_user"}
    env["toggle"] = {"name": "ORG-CONFIRMED", "expectedState": "on"}
    for key in test_data["wids"]:
        test_data["wids"][key] = "0" * 32
    test_data["filters"] = {"FLT_OK": "type=Organization", "FLT_BAD": "not-a-real-filter"}
    return source_doc, test_data
