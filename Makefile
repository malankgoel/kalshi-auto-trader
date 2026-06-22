.PHONY: install lint test check

PYTHON ?= .venv/bin/python

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -q

lint:
	$(PYTHON) -m ruff check kalshi_auto_trader tests execute_trades.py

check: lint test
	$(PYTHON) -m compileall -q kalshi_auto_trader tests execute_trades.py
