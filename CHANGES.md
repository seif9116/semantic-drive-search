# Changelog

All notable changes to Semantic Drive Search are documented here.

## [0.2.0] - 2026-03-16

### Performance Improvements

#### Backend
- **HNSW Vector Index**: Added HNSW index for fast approximate nearest neighbor search on embeddings (10-100x faster queries on large datasets)
- **Composite Index**: Added composite index on `(folder_id, file_id)` for faster file lookups
- **File Hash Index**: Added index on `file_hash` for embedding cache lookups
- **Search Response Caching**: Implemented in-memory LRU cache for repeated search queries (5-minute TTL)
- **Pagination**: Added `offset` and `min_similarity` parameters to search endpoint for cursor-based pagination
- **Batch Embedding**: Added `embed_batch_async()` for concurrent embedding generation

#### Database Schema
- Added `file_hash` column for content-based deduplication
- Added `last_modified` timestamp for incremental re-indexing
- All indexes created automatically on first run

### New Features

#### API Endpoints
- `GET /health` - Health check endpoint for monitoring (checks DB, Gemini API, auth status)
- `GET /api/similar/{file_id}` - "More like this" endpoint to find visually similar images

#### CLI Commands
- `sds search --min-score 0.7` - Filter results by minimum similarity score
- `sds search --top 10` - Alias for `--limit`
- `sds index --force` - Re-index all files from scratch
- `sds index --watch` - Continuously monitor for new files
- `sds export <folder_id> --format csv|json` - Export indexed metadata
- `sds stats <folder_id>` - Show embedding statistics (count, similarity distribution)
- `sds similar <file_id> --folder <id>` - Find similar images from CLI

#### Frontend
- **Infinite Scroll**: Results load automatically as you scroll
- **Similarity Badges**: Color-coded badges (green >80%, yellow >65%, red <65%)
- **Keyboard Navigation**: Arrow keys to navigate images in modal
- **Search-as-you-type**: Debounced 300ms, no submit button needed

### Reliability & Error Handling

- **Structured Logging**: Added `backend/logging_config.py` with JSON/human formatters
- **Custom Exceptions**: Added `backend/exceptions.py` with typed exception classes
- **Better Error Messages**: Improved error handling in indexing pipeline with detailed logging
- **Graceful Degradation**: App starts even without DB connection (OAuth-only mode)

### Security

- **Rate Limiting**: Added `backend/security.py` with configurable rate limits
- **Input Validation**: Added validation for folder IDs and search queries
- **Security Headers**: CSP, X-Frame-Options, X-Content-Type-Options headers
- **Filename Sanitization**: Safe display of user-provided filenames

### Developer Experience

- **Makefile**: Added `make dev`, `make test`, `make lint`, `make format`, etc.
- **Pre-commit Hooks**: Configured ruff, black, mypy, bandit
- **GitHub Actions CI**: Automated lint, test, build on push/PR
- **CONTRIBUTING.md**: Comprehensive contribution guidelines
- **pyproject.toml**: Added ruff, black, mypy, pytest configurations

### Bug Fixes

- Fixed embedding function signature to return `(embedding, file_hash)` tuple
- Fixed CLI index command to use new embedding API
- Fixed modal close button not working in some cases

### Breaking Changes

- `embed_image_with_retry()` now returns a tuple `(embedding, file_hash)` instead of just `embedding`
- `VectorStore.add_embedding()` accepts optional `file_hash` parameter
- `VectorStore.search()` accepts `offset` and `min_similarity` parameters

---

## [0.1.0] - Initial Release

- Semantic search for Google Drive images and videos
- Gemini Embedding 2 integration
- PostgreSQL + pgvector storage
- FastAPI backend with OAuth
- Typer CLI
- MCP server for Claude integration