"""Configuration loader for the Org Chart REST API security-test harness (ORG-21922).

Responsibilities (design-approved scope only — NO HTTP, NO evidence, NO UI):

1. Load and JSON-Schema-validate the source ``environment.json``.
2. Deep-merge ``defaults`` with the active environment.
3. JSON-Schema-validate the resolved (post-merge) configuration.
4. Load and validate the referenced ``test-data.<env>.json`` file.
5. Apply semantic validations that draft-07 cannot express.
6. Resolve ``env:``/``secret:`` references WITHOUT logging their values.
7. Fail closed (``RuntimeNotReadyError``) before any request when required values are TBD.

Merge semantics: objects are recursively deep-merged (environment overrides
defaults); arrays and scalars are replaced wholesale. ``test-data`` is validated
independently and is never merged into the configuration.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

from jsonschema import Draft7Validator

from .errors import (
    ConfigError,
    ReferenceResolutionError,
    RuntimeNotReadyError,
    SchemaValidationError,
    SemanticValidationError,
)

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

#: ``env:NAME`` or ``secret:NAME`` — names limited to ``[A-Za-z0-9_]``.
REF_PATTERN = re.compile(r"^(env|secret):([A-Za-z0-9_]+)$")

_TBD_STRINGS = {"TBD", "tbd"}


# --------------------------------------------------------------------------- #
# JSON loading + schema validation
# --------------------------------------------------------------------------- #
def _load_json(path: Path | str) -> Any:
    p = Path(path)
    try:
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"file not found: {p}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {p}: {exc}") from exc


_schema_cache: Dict[str, dict] = {}


def _schema(name: str) -> dict:
    if name not in _schema_cache:
        _schema_cache[name] = _load_json(_SCHEMA_DIR / name)
    return _schema_cache[name]


def _validate(instance: Any, schema_name: str, label: str) -> None:
    validator = Draft7Validator(_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        messages = []
        for err in errors:
            location = "/".join(str(p) for p in err.path) or "<root>"
            messages.append(f"{location}: {err.message}")
        raise SchemaValidationError(label, messages)


# --------------------------------------------------------------------------- #
# Deep merge
# --------------------------------------------------------------------------- #
def _clone(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _clone(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clone(v) for v in value]
    return value


def deep_merge(base: Any, override: Any) -> Any:
    """Recursively merge ``override`` onto ``base``.

    Objects merge key-by-key; arrays and scalar values replace wholesale.
    """
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        merged: Dict[str, Any] = {k: _clone(v) for k, v in base.items()}
        for key, value in override.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = _clone(value)
        return merged
    # Arrays and scalars: replace.
    return _clone(override)


def resolve_environment(source: Mapping[str, Any]) -> Dict[str, Any]:
    """Produce the flattened, single-environment configuration.

    Raises ``SemanticValidationError`` if ``activeEnvironment`` is absent from
    ``environments`` (the "active environment must exist" rule).
    """
    active = source["activeEnvironment"]
    environments = source["environments"]
    if active not in environments:
        raise SemanticValidationError(
            [f"activeEnvironment '{active}' does not exist under environments"]
        )
    resolved = deep_merge(source["defaults"], environments[active])
    resolved["activeEnvironment"] = active
    return resolved


# --------------------------------------------------------------------------- #
# Semantic validations (not expressible in draft-07)
# --------------------------------------------------------------------------- #
def semantic_validate(resolved: Mapping[str, Any], test_data: Mapping[str, Any]) -> None:
    problems: List[str] = []

    pagination = resolved["pagination"]
    if pagination["defaultLimit"] > pagination["maxLimit"]:
        problems.append(
            f"pagination.defaultLimit ({pagination['defaultLimit']}) must not exceed "
            f"maxLimit ({pagination['maxLimit']})"
        )

    if test_data["environment"] != resolved["activeEnvironment"]:
        problems.append(
            f"test-data.environment '{test_data['environment']}' does not match "
            f"activeEnvironment '{resolved['activeEnvironment']}'"
        )

    declared_roles = set(resolved["roles"])
    personas = set(test_data["personas"].keys())
    missing = declared_roles - personas
    extra = personas - declared_roles
    if missing:
        problems.append(f"declared roles have no matching persona: {sorted(missing)}")
    if extra:
        problems.append(f"personas not declared in roles: {sorted(extra)}")

    if problems:
        raise SemanticValidationError(problems)


# --------------------------------------------------------------------------- #
# Reference resolution (env:/secret:) — values never logged
# --------------------------------------------------------------------------- #
class SecretValue:
    """Wrapper that keeps a resolved secret out of logs and reprs."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Return the underlying value. Only call at the moment of use."""
        return self._value

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "<redacted-secret>"

    __str__ = __repr__


@dataclass
class ReferenceResolver:
    """Resolves ``env:``/``secret:`` references.

    ``env`` defaults to ``os.environ``. ``secret_provider`` is an optional
    callable mapping a secret name to its value (or ``None`` if unknown).
    """

    env: Optional[Mapping[str, str]] = None
    secret_provider: Optional[Callable[[str], Optional[str]]] = None

    def resolve(self, ref: str) -> SecretValue:
        match = REF_PATTERN.match(ref)
        if not match:
            raise ReferenceResolutionError([f"invalid reference syntax: {ref!r}"])
        scheme, name = match.group(1), match.group(2)
        if scheme == "env":
            source = self.env if self.env is not None else os.environ
            value = source.get(name)
        else:  # secret
            if self.secret_provider is None:
                raise ReferenceResolutionError(
                    [f"no secret provider configured to resolve {ref!r}"]
                )
            value = self.secret_provider(name)
        if value is None or value == "":
            # Note: only the reference name is reported, never a value.
            raise ReferenceResolutionError([f"reference {ref!r} resolved to a missing/empty value"])
        return SecretValue(value)


def collect_references(obj: Any) -> List[str]:
    """Return the sorted, de-duplicated set of ref strings anywhere in ``obj``."""
    found: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)
        elif isinstance(node, str) and REF_PATTERN.match(node):
            found.add(node)

    _walk(obj)
    return sorted(found)


def resolve_all_references(
    resolved: Mapping[str, Any],
    test_data: Mapping[str, Any],
    resolver: Optional[ReferenceResolver] = None,
) -> Dict[str, SecretValue]:
    """Resolve every reference in the resolved config and test-data.

    Fails closed with a single aggregated ``ReferenceResolutionError`` if any
    reference is malformed, missing, or empty. Resolved values are wrapped in
    ``SecretValue`` and never logged.
    """
    resolver = resolver or ReferenceResolver()
    refs = sorted(set(collect_references(resolved)) | set(collect_references(test_data)))
    resolved_values: Dict[str, SecretValue] = {}
    errors: List[str] = []
    for ref in refs:
        try:
            resolved_values[ref] = resolver.resolve(ref)
        except ReferenceResolutionError as exc:
            errors.extend(exc.messages)
    if errors:
        raise ReferenceResolutionError(errors)
    return resolved_values


# --------------------------------------------------------------------------- #
# TBD gate (fail closed before request execution)
# --------------------------------------------------------------------------- #
def _is_tbd(value: Any) -> bool:
    return isinstance(value, str) and value.strip() in _TBD_STRINGS


def find_tbd(
    resolved: Mapping[str, Any],
    test_data: Mapping[str, Any],
    *,
    required_wids: Optional[Iterable[str]] = None,
    required_filters: Optional[Iterable[str]] = None,
) -> List[str]:
    """Return the list of dotted paths whose values remain TBD.

    ``required_wids`` / ``required_filters`` restrict the check to the test
    values a given test actually needs; when ``None`` every declared value is
    checked.
    """
    tbd: List[str] = []

    if _is_tbd(resolved.get("host")):
        tbd.append("host")

    auth = resolved.get("auth", {})
    if _is_tbd(auth.get("model")):
        tbd.append("auth.model")
    if auth.get("model") == "oauth2_client_credentials_acting_as":
        mechanism = auth.get("actingAs", {}).get("mechanism")
        if mechanism is None or _is_tbd(mechanism):
            tbd.append("auth.actingAs.mechanism")

    toggle = resolved.get("toggle", {})
    if _is_tbd(toggle.get("name")):
        tbd.append("toggle.name")
    if _is_tbd(toggle.get("expectedState")):
        tbd.append("toggle.expectedState")

    wids = test_data.get("wids", {})
    wid_keys = list(required_wids) if required_wids is not None else list(wids.keys())
    for key in wid_keys:
        if _is_tbd(wids.get(key)):
            tbd.append(f"wids.{key}")

    filters = test_data.get("filters", {})
    filter_keys = list(required_filters) if required_filters is not None else list(filters.keys())
    for key in filter_keys:
        if _is_tbd(filters.get(key)):
            tbd.append(f"filters.{key}")

    return tbd


def assert_runtime_ready(
    resolved: Mapping[str, Any],
    test_data: Mapping[str, Any],
    *,
    required_wids: Optional[Iterable[str]] = None,
    required_filters: Optional[Iterable[str]] = None,
) -> None:
    tbd = find_tbd(
        resolved,
        test_data,
        required_wids=required_wids,
        required_filters=required_filters,
    )
    if tbd:
        raise RuntimeNotReadyError(tbd)


# --------------------------------------------------------------------------- #
# Top-level entry points
# --------------------------------------------------------------------------- #
@dataclass
class LoadedConfig:
    source: Dict[str, Any]
    resolved: Dict[str, Any]
    test_data: Dict[str, Any]
    config_path: Path
    test_data_path: Path


def load_config(config_path: Path | str) -> LoadedConfig:
    """Load + validate config and its test-data (steps 1-5). Does NOT gate on TBD.

    TBD values are allowed here so that loading/validation never blocks; only
    ``assert_runtime_ready`` / ``prepare_for_execution`` fail closed on TBD.
    """
    config_path = Path(config_path).resolve()
    source = _load_json(config_path)
    _validate(source, "environment.schema.json", "environment.json")

    resolved = resolve_environment(source)
    _validate(resolved, "resolved-environment.schema.json", "resolved environment")

    test_data_path = (config_path.parent / resolved["testDataRef"]).resolve()
    test_data = _load_json(test_data_path)
    _validate(test_data, "test-data.schema.json", f"test-data ({test_data_path.name})")

    semantic_validate(resolved, test_data)

    return LoadedConfig(
        source=source,
        resolved=resolved,
        test_data=test_data,
        config_path=config_path,
        test_data_path=test_data_path,
    )


def prepare_for_execution(
    config_path: Path | str,
    *,
    resolver: Optional[ReferenceResolver] = None,
    required_wids: Optional[Iterable[str]] = None,
    required_filters: Optional[Iterable[str]] = None,
) -> tuple[LoadedConfig, Dict[str, SecretValue]]:
    """Full pre-request pipeline: load + validate, fail closed on TBD, resolve refs.

    Returns the loaded config and the resolved secrets map. The TBD gate runs
    BEFORE reference resolution so execution is blocked while required runtime
    values remain unconfirmed.
    """
    loaded = load_config(config_path)
    assert_runtime_ready(
        loaded.resolved,
        loaded.test_data,
        required_wids=required_wids,
        required_filters=required_filters,
    )
    secrets = resolve_all_references(loaded.resolved, loaded.test_data, resolver)
    return loaded, secrets


def _main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover - CLI glue
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate the Org Chart security-test configuration (no requests are sent)."
    )
    parser.add_argument("config", help="path to environment.json")
    args = parser.parse_args(argv)

    try:
        loaded = load_config(args.config)
    except ConfigError as exc:
        print(f"INVALID: {exc}")
        return 1

    print(f"OK: '{loaded.config_path.name}' + '{loaded.test_data_path.name}' validated.")
    tbd = find_tbd(loaded.resolved, loaded.test_data)
    if tbd:
        print("Loaded, but NOT runtime-ready. Unresolved TBD values:")
        for item in tbd:
            print(f"  - {item}")
    else:
        print("Runtime-ready: no TBD values remain.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
