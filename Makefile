.PHONY: help install install-dev test test-unit test-integration coverage lint format clean

help:
	@echo "Available commands:"
	@echo "  install        Install package in production mode"
	@echo "  install-dev    Install package in development mode with test dependencies"
	@echo "  test           Run all tests"
	@echo "  test-unit      Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  coverage       Run tests with coverage report"
	@echo "  lint           Run code quality checks"
	@echo "  format         Format code with black and isort"
	@echo "  clean          Remove build artifacts and cache files"

install:
	pip install -e .

install-dev:
	pip install -e .
	pip install -r requirements-dev.txt

test:
	pytest

test-unit:
	pytest -m unit

test-integration:
	pytest -m integration

coverage:
	pytest --cov=sceptre_sync --cov-report=term-missing --cov-report=html

lint:
	flake8 sceptre_sync tests
	mypy sceptre_sync
	isort --check-only sceptre_sync tests
	black --check sceptre_sync tests

format:
	isort sceptre_sync tests
	black sceptre_sync tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
