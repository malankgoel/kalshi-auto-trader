.PHONY: install test check

PYTHON ?= .venv/bin/python

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -q

check: test
	$(PYTHON) -m compileall -q kalshi_auto_trader tests execute_trades.py
