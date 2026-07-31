"""Exception hierarchy for the Org Chart security-test configuration harness.

All errors carry a structured ``messages`` list so callers can present or assert
on individual problems without parsing prose. No exception ever includes a
resolved secret value in its message.
"""

from __future__ import annotations

from typing import List, Optional, Sequence


class ConfigError(Exception):
    """Base class for every configuration/loader failure."""

    def __init__(self, message: str, messages: Optional[Sequence[str]] = None) -> None:
        super().__init__(message)
        self.messages: List[str] = list(messages) if messages is not None else [message]


class SchemaValidationError(ConfigError):
    """A document failed JSON Schema (draft-07) validation."""

    def __init__(self, label: str, messages: Sequence[str]) -> None:
        self.label = label
        text = f"{label}: schema validation failed:\n  - " + "\n  - ".join(messages)
        super().__init__(text, messages)


class SemanticValidationError(ConfigError):
    """A cross-field / cross-document rule that JSON Schema cannot express failed."""

    def __init__(self, messages: Sequence[str]) -> None:
        text = "semantic validation failed:\n  - " + "\n  - ".join(messages)
        super().__init__(text, messages)


class ReferenceResolutionError(ConfigError):
    """An ``env:``/``secret:`` reference was malformed, missing, or empty."""

    def __init__(self, messages: Sequence[str]) -> None:
        text = "reference resolution failed:\n  - " + "\n  - ".join(messages)
        super().__init__(text, messages)


class RuntimeNotReadyError(ConfigError):
    """Execution was requested while required values are still ``TBD`` (fail closed)."""

    def __init__(self, tbd_items: Sequence[str]) -> None:
        self.tbd_items = list(tbd_items)
        text = (
            "runtime not ready; unresolved TBD values must be confirmed before "
            "any request is sent:\n  - " + "\n  - ".join(tbd_items)
        )
        super().__init__(text, tbd_items)
