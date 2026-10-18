.PHONY: help install lint typecheck test collect report all clean

help:
	@echo "irsi Makefile targets"
	@echo "  install   Install in editable mode + dev deps"
	@echo "  lint      Run ruff if available"
	@echo "  typecheck Run mypy if available"
	@echo "  test      Run pytest"
	@echo "  collect   Collect verified sources"
	@echo "  report    Build report from stored data"
	@echo "  all       Collect + report"
	@echo "  clean     Remove build artifacts and local reports (keep raw data/cache as configured)"

install:
	pip install -e .
	@pip show ruff >/dev/null 2>&1 || pip install ruff
	@pip show mypy >/dev/null 2>&1 || pip install mypy
	@pip show pytest >/dev/null 2>&1 || pip install pytest

lint:
	@if command -v ruff >/dev/null 2>&1; then ruff check src tests; else echo "ruff missing; run make install"; fi

typecheck:
	@if command -v mypy >/dev/null 2>&1; then mypy src; else echo "mypy missing; run make install"; fi

test:
	python -m pytest -q

collect:
	irsi collect

report:
	irsi report

all:
	irsi all

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache
	rm -f reports/*.html
