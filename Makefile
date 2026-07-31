.PHONY: install start test lint harness clean

PYTHON ?= python3
VENV ?= .venv
PIP = $(VENV)/bin/pip
PY = $(VENV)/bin/python

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

start:
	$(PY) -m uvicorn webapp.app:app --reload --port 8000

test:
	$(PY) -m pytest

harness:
	$(PY) -m harness config/environment.json

clean:
	rm -rf $(VENV) .pytest_cache __pycache__ webapp/__pycache__ engine/__pycache__
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
