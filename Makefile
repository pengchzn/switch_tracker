.PHONY: setup run collect translate-export translate-import lint test check

PYTHON ?= python3

setup:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements-dev.txt

run:
	$(PYTHON) server.py

collect:
	$(PYTHON) get_switch_data.py

translate-export:
	$(PYTHON) game_translation.py export

translate-import:
	$(PYTHON) game_translation.py import

lint:
	ruff check .

test:
	pytest

check: lint test
