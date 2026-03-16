# Contributing to Semantic Drive Search

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Development Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 16 with pgvector extension
- Google Cloud account with Drive API enabled
- Gemini API key

### Quick Start

```bash
# Clone the repository
git clone https://github.com/seif9116/semantic-drive-search.git
cd semantic-drive-search

# Create virtual environment and install dependencies
make install-dev

# Activate the virtual environment
source .venv/bin/activate

# Copy environment template and configure
cp .env.example .env
# Edit .env with your credentials

# Initialize the database
make migrate

# Start the development server
make dev
```

### Environment Variables

Create a `.env` file with:

```env
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_CLIENT_ID=your-oauth-client-id
GOOGLE_CLIENT_SECRET=your-oauth-client-secret
APP_SECRET_KEY=random-secret-for-sessions
DATABASE_URL=postgresql://localhost:5432/semantic_search
EMBEDDING_DIMENSIONS=768
```

## Development Commands

| Command | Description |
|---------|-------------|
| `make dev` | Start development server with auto-reload |
| `make test` | Run all tests |
| `make test-cov` | Run tests with coverage report |
| `make lint` | Run linting with ruff |
| `make format` | Format code with black and ruff |
| `make typecheck` | Run type checking with mypy |
| `make check` | Run all checks (lint, typecheck, test) |

## Code Style

We use the following tools for code quality:

- **ruff** for linting
- **black** for formatting
- **mypy** for type checking
- **pre-commit** for git hooks

Please run `make format` before committing, or install pre-commit hooks:

```bash
pre-commit install
```

## Project Structure

```
semantic-drive-search/
├── backend/
│   ├── __init__.py
│   ├── main.py          # FastAPI application and routes
│   ├── auth.py          # Google OAuth handling
│   ├── config.py        # Configuration management
│   ├── drive.py         # Google Drive API interactions
│   ├── embeddings.py    # Gemini embedding generation
│   ├── vector_store.py  # PostgreSQL/pgvector operations
│   ├── models.py        # Pydantic models
│   ├── cli.py           # Typer CLI commands
│   ├── organizer.py     # Folder organization logic
│   ├── mcp_server.py    # MCP server for Claude integration
│   ├── logging_config.py # Structured logging
│   ├── exceptions.py    # Custom exception classes
│   └── security.py      # Security utilities
├── static/
│   ├── index.html       # Frontend HTML/CSS
│   └── app.js           # Frontend JavaScript
├── tests/
│   ├── conftest.py      # Pytest fixtures
│   ├── test_api.py      # API endpoint tests
│   ├── test_config.py   # Configuration tests
│   ├── test_embeddings.py # Embedding tests
│   └── test_vector_store.py # Vector store tests
├── skills/              # Claude Code skills
├── docs/                # Documentation
├── Makefile             # Development commands
├── pyproject.toml       # Project configuration
└── .env.example         # Environment template
```

## Adding New Features

### Adding a New API Endpoint

1. Add the route in `backend/main.py`
2. Add any new Pydantic models in `backend/models.py`
3. Add tests in `tests/test_api.py`
4. Update the API documentation in `README.md`

### Adding a New CLI Command

1. Add the command function in `backend/cli.py`
2. Use the `@app.command()` decorator
3. Add tests using `typer.testing.CliRunner`

### Adding New Configuration

1. Add the field to `Settings` class in `backend/config.py`
2. Update `.env.example`
3. Update documentation

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_api.py -v

# Run integration tests (requires DATABASE_URL)
make test-integration
```

### Writing Tests

- Use `pytest` fixtures for common setup
- Mock external APIs (Gemini, Drive) in unit tests
- Use the `@requires_db` marker for integration tests
- Aim for >70% code coverage

Example test:

```python
from unittest.mock import patch, MagicMock

def test_search_endpoint(client):
    with patch("backend.main.auth.get_credentials", return_value=MagicMock()), \
         patch("backend.main.embeddings.embed_text_with_retry", return_value=[0.1] * 768):
        resp = client.get("/api/search?q=test&folder_id=abc")
        assert resp.status_code == 200
```

## Pull Request Process

1. Fork the repository and create a feature branch
2. Make your changes, following the code style guidelines
3. Add tests for new functionality
4. Run `make check` to ensure all checks pass
5. Update documentation if needed
6. Submit a pull request

### PR Checklist

- [ ] Code follows the project style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages are clear and descriptive

## Reporting Issues

When reporting issues, please include:

1. Python version
2. Operating system
3. Steps to reproduce
4. Expected behavior
5. Actual behavior
6. Relevant logs (with sensitive info redacted)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.