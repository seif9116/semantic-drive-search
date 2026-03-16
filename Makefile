# Semantic Drive Search - Development Makefile
# 
# Usage:
#   make dev       - Start development server
#   make test      - Run all tests
#   make lint      - Run linting and type checking
#   make format    - Format code with black/ruff
#   make migrate   - Run database migrations
#   make reset-db  - Reset the database (WARNING: destroys data)

.PHONY: dev test lint format check migrate reset-db clean install help

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
VENV := .venv
ACTIVATE := source $(VENV)/bin/activate &&
PYTEST := $(ACTIVATE) pytest
RUFF := $(ACTIVATE) ruff
BLACK := $(ACTIVATE) black
MYPY := $(ACTIVATE) mypy

# ---- Development ----

dev: ## Start the development server with auto-reload
	@echo "Starting development server..."
	$(ACTIVATE) uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-cli: ## Start the CLI interactive mode
	@echo "Starting CLI..."
	$(ACTIVATE) sds

# ---- Installation ----

install: ## Create virtual environment and install dependencies
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Installing dependencies..."
	$(ACTIVATE) pip install -e ".[dev]"
	@echo "Done! Run 'source .venv/bin/activate' to activate."

install-dev: install ## Install with development dependencies
	@echo "Installing development tools..."
	$(ACTIVATE) pip install ruff black mypy pre-commit
	@echo "Setting up pre-commit hooks..."
	$(ACTIVATE) pre-commit install
	@echo "Done!"

# ---- Testing ----

test: ## Run all tests
	@echo "Running tests..."
	$(PYTEST) tests/ -v

test-cov: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	$(PYTEST) tests/ -v --cov=backend --cov-report=term-missing --cov-report=html

test-integration: ## Run integration tests (requires DATABASE_URL)
	@echo "Running integration tests..."
	DATABASE_URL=postgresql://localhost:5432/semantic_search $(PYTEST) tests/ -v -m integration

# ---- Code Quality ----

lint: ## Run linting with ruff
	@echo "Running linter..."
	$(RUFF) check backend/

format: ## Format code with black and ruff
	@echo "Formatting code..."
	$(BLACK) backend/ tests/
	$(RUFF) check --fix backend/

typecheck: ## Run type checking with mypy
	@echo "Running type checker..."
	$(MYPY) backend/

check: lint typecheck test ## Run all checks (lint, typecheck, test)

# ---- Database ----

migrate: ## Run database migrations (create tables if needed)
	@echo "Running migrations..."
	$(ACTIVATE) $(PYTHON) -c "from backend.vector_store import VectorStore; from backend.config import settings; VectorStore(settings.database_url, settings.embedding_dimensions); print('Database schema initialized.')"

reset-db: ## Reset the database (WARNING: destroys all data)
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@echo "Dropping tables..."
	$(ACTIVATE) $(PYTHON) -c "\
import psycopg; \
from backend.config import settings; \
conn = psycopg.connect(settings.database_url); \
conn.execute('DROP TABLE IF EXISTS embeddings CASCADE'); \
conn.execute('DROP EXTENSION IF EXISTS vector CASCADE'); \
conn.commit(); \
print('Database reset complete.')"
	@$(MAKE) migrate

# ---- Docker ----

docker-build: ## Build Docker image
	docker build -t semantic-drive-search .

docker-run: ## Run Docker container
	docker run -p 8000:8000 --env-file .env semantic-drive-search

# ---- Cleanup ----

clean: ## Remove build artifacts and cache
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
	@echo "Done!"

# ---- Help ----

help: ## Show this help message
	@echo "Semantic Drive Search - Available commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make dev        # Start development server"
	@echo "  make test       # Run tests"
	@echo "  make check      # Run all checks"