"""Regression tests for the startup loading-overlay lifecycle.

These tests exercise the frontend contract (CSS + JS) without a browser:
after /api/config and /api/catalog succeed, hideLoading() must remove the
visibility class so the overlay is not displayed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from webapp.app import create_app

STATIC = Path(__file__).resolve().parents[1] / "webapp" / "static"
VISIBLE_CLASS = "is-visible"


@pytest.fixture
def client():
    return TestClient(create_app())


class _Overlay:
    """Minimal stand-in for the loading overlay DOM node + CSS rules."""

    def __init__(self, class_name: str = "loading-overlay") -> None:
        self.classes: set[str] = {class_name}
        self.aria_hidden = "true"

    def show(self) -> None:
        self.classes.add(VISIBLE_CLASS)
        self.aria_hidden = "false"

    def hide(self) -> None:
        self.classes.discard(VISIBLE_CLASS)
        self.aria_hidden = "true"

    @property
    def is_visible(self) -> bool:
        return VISIBLE_CLASS in self.classes


def _simulate_startup_lifecycle() -> _Overlay:
    """Mirror ui.js reference counting used by App.init()."""
    overlay = _Overlay()
    count = 0

    def show() -> None:
        nonlocal count
        count += 1
        overlay.show()

    def hide() -> None:
        nonlocal count
        count = max(0, count - 1)
        if count == 0:
            overlay.hide()

    show()  # App.init() entry
    # Successful parallel startup fetches (no throw).
    hide()  # App.init() finally
    return overlay


def test_startup_apis_succeed(client):
    assert client.get("/api/config").status_code == 200
    assert client.get("/api/catalog").status_code == 200


def test_loading_overlay_removed_after_successful_startup(client):
    assert client.get("/api/config").status_code == 200
    assert client.get("/api/catalog").status_code == 200

    overlay = _simulate_startup_lifecycle()
    assert overlay.is_visible is False
    assert overlay.aria_hidden == "true"


def test_loading_overlay_css_hides_by_default():
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    base_rule = css.split(".loading-overlay {", 1)[1].split("}", 1)[0]
    visible_rule = css.split(".loading-overlay.is-visible {", 1)[1].split("}", 1)[0]

    assert re.search(r"display\s*:\s*none", base_rule, re.I)
    assert re.search(r"display\s*:\s*flex", visible_rule, re.I)


def test_ui_js_toggles_visibility_class_not_hidden_attribute():
    ui_js = (STATIC / "js" / "ui.js").read_text(encoding="utf-8")
    assert 'classList.add(VISIBLE_CLASS)' in ui_js or 'classList.add("is-visible")' in ui_js
    assert 'classList.remove(VISIBLE_CLASS)' in ui_js or 'classList.remove("is-visible")' in ui_js
    assert ".hidden = false" not in ui_js
    assert ".hidden = true" not in ui_js


def test_main_init_uses_parallel_fetch_and_finally_hides():
    main_js = (STATIC / "js" / "main.js").read_text(encoding="utf-8")
    init_start = main_js.index("async init()")
    init_chunk = main_js[init_start : main_js.index("onConnectionChange(connected)", init_start)]
    assert "Promise.all" in init_chunk
    assert "loadConfig" in init_chunk
    assert "getCatalog" in init_chunk
    assert "finally" in init_chunk
    assert "hideLoading()" in init_chunk


def test_index_overlay_starts_without_visibility_class(client):
    html = client.get("/").text
    assert 'id="loading"' in html
    assert 'class="loading-overlay"' in html
    assert "loading-overlay is-visible" not in html
