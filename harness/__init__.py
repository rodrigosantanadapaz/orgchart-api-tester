"""Org Chart REST API security-test configuration harness (ORG-21922).

Scope: configuration loading, deep-merge, JSON-Schema validation, semantic
validation, reference resolution, and the runtime-readiness (TBD) gate.
This package deliberately does NOT contain an API client, HTTP calls,
evidence collection, or any UI.
"""

from __future__ import annotations

from .errors import (
    ConfigError,
    ReferenceResolutionError,
    RuntimeNotReadyError,
    SchemaValidationError,
    SemanticValidationError,
)
from .loader import (
    LoadedConfig,
    ReferenceResolver,
    SecretValue,
    assert_runtime_ready,
    collect_references,
    deep_merge,
    find_tbd,
    load_config,
    prepare_for_execution,
    resolve_all_references,
    resolve_environment,
    semantic_validate,
)

__all__ = [
    "ConfigError",
    "SchemaValidationError",
    "SemanticValidationError",
    "ReferenceResolutionError",
    "RuntimeNotReadyError",
    "LoadedConfig",
    "ReferenceResolver",
    "SecretValue",
    "assert_runtime_ready",
    "collect_references",
    "deep_merge",
    "find_tbd",
    "load_config",
    "prepare_for_execution",
    "resolve_all_references",
    "resolve_environment",
    "semantic_validate",
]
