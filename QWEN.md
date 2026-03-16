# 🔬 AUTO-RESEARCH OPTIMIZATION PROMPT
# Project: semantic-drive-search
# https://github.com/seif9116/semantic-drive-search

You are an expert full-stack engineer and AI systems architect conducting a comprehensive 
autonomous optimization pass on this project. Your goal is to improve EVERYTHING — 
performance, reliability, security, UX, code quality, scalability, and developer experience.

Work systematically through each domain below. For each area:
1. Audit the current state
2. Identify specific problems or improvement opportunities
3. Implement the best solution
4. Verify it works (run tests, check imports, etc.)
5. Move to the next item

Do not ask for permission. Do not stop to summarize. Just work.

---

## PHASE 1 — CODEBASE AUDIT

Start by fully reading and understanding the project:

- Read all files in `backend/`
- Read `pyproject.toml`, `.env.example`, `static/`, `tests/`, `skills/`
- Read `claude-skill.md` and `.claude/skills/sds/`
- Build a mental model of every data flow: indexing pipeline, embedding generation, 
  vector storage, search query path, OAuth flow, CLI commands

---

## PHASE 2 — BACKEND PERFORMANCE

### Embedding Pipeline
- [ ] Batch embed multiple images/frames in parallel instead of sequentially
- [ ] Add async concurrency with `asyncio.gather()` for Drive downloads + embedding
- [ ] Implement an embedding cache (file hash → embedding) to skip re-embedding 
      unchanged files on re-index
- [ ] For videos: improve frame sampling strategy (scene-change detection > fixed interval)
- [ ] Add retry logic with exponential backoff for Gemini API calls

### Database / pgvector
- [ ] Ensure the vector column has an HNSW or IVFFlat index for fast ANN search
      (CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops))
- [ ] Add a composite index on (folder_id, file_id) for fast folder-scoped queries
- [ ] Use connection pooling (asyncpg + SQLAlchemy async engine)
- [ ] Review all SQL queries for N+1 problems

### API Performance
- [ ] Add response caching for repeated identical search queries (Redis or in-memory LRU)
- [ ] Stream search results as they are scored instead of waiting for full result set
- [ ] Add pagination to search endpoint (cursor-based, not offset)
- [ ] Compress API responses with gzip middleware

---

## PHASE 3 — SEARCH QUALITY

- [ ] Implement hybrid search: combine vector similarity with BM25 text search on 
      filename + Drive metadata, then use RRF (Reciprocal Rank Fusion) to merge results
- [ ] Add query expansion: use Gemini to rewrite/expand the user's query into 3 
      semantically rich variants, embed all three, average the query vectors
- [ ] Implement result re-ranking: after retrieving top-K candidates, re-rank using 
      a cross-encoder or Gemini's multimodal understanding of the actual image
- [ ] Add negative query support: "sunset but NOT indoors" parsing
- [ ] Expose a `min_similarity` threshold param (default 0.65) to filter junk results
- [ ] Add a "more like this" endpoint: given a file_id, find visually similar images

---

## PHASE 4 — RELIABILITY & ERROR HANDLING

- [ ] Add structured logging (use `structlog` or `logging` with JSON formatter) 
      to every major code path
- [ ] Wrap all external API calls (Gemini, Google Drive) in proper try/except with 
      typed error classes
- [ ] Add health check endpoint `GET /health` that checks DB connectivity, Gemini 
      API reachability, and auth session validity
- [ ] Handle Drive quota errors gracefully — pause, log, resume
- [ ] Handle files that fail to embed (corrupt images, unsupported formats) — 
      skip and record in a `failed_files` table instead of crashing the whole index job
- [ ] Add idempotent re-indexing: track last_modified timestamp per file; 
      only re-embed files that changed

---

## PHASE 5 — SECURITY

- [ ] Audit all environment variables — ensure no secrets are logged
- [ ] Add rate limiting to all API endpoints (slowapi or similar)
- [ ] Validate and sanitize all user inputs (folder URLs, search queries)
- [ ] Ensure OAuth tokens are stored securely (encrypted at rest if persisted)
- [ ] Add CSRF protection to state-changing endpoints
- [ ] Review Drive API scopes — ensure minimum necessary permissions 
      (use `drive.readonly` not full `drive`)
- [ ] Add Content-Security-Policy headers to the frontend
- [ ] Ensure thumbnails/media are served only to authenticated sessions

---

## PHASE 6 — FRONTEND UX

Read `static/` thoroughly, then:

- [ ] Add real-time search-as-you-type (debounced 300ms, no submit button needed)
- [ ] Add infinite scroll to search results
- [ ] Add a lightbox/modal viewer for full-size image preview with keyboard nav
- [ ] Show indexing progress as a live progress bar (connect to the SSE endpoint)
- [ ] Add a "similarity score" badge on each result card (color-coded: green >0.8, 
      yellow >0.65, red <0.65)
- [ ] Add folder selector dropdown (populated from `sds list-folders`)
- [ ] Add dark mode toggle with localStorage persistence
- [ ] Make the UI fully mobile-responsive
- [ ] Add empty state illustrations and better loading skeletons

---

## PHASE 7 — CLI IMPROVEMENTS

- [ ] Add `sds search --top 10 --min-score 0.7 --json` output flag
- [ ] Add `sds index --watch` mode that polls for new files every N minutes
- [ ] Add `sds export <folder_id> --format csv|json` to export all indexed metadata
- [ ] Add `sds stats <folder_id>` to show index size, embedding count, avg similarity 
      distribution of the corpus
- [ ] Improve `sds organize --mode semantic`: show a preview table of cluster labels 
      before moving files; ask for confirmation unless `--yes` is passed
- [ ] Add shell completion (typer supports this natively — enable it)
- [ ] Add `sds reindex <folder_id> --force` to re-embed everything from scratch

---

## PHASE 8 — TESTING

- [ ] Audit existing tests in `tests/` — fix any broken ones
- [ ] Add unit tests for the embedding pipeline (mock Gemini API)
- [ ] Add unit tests for the vector search logic
- [ ] Add integration test for the full index → search round trip
- [ ] Add tests for the CLI commands using `typer.testing.CliRunner`
- [ ] Add a test fixture that creates and tears down a test PostgreSQL schema
- [ ] Target ≥ 70% code coverage; run `pytest --cov=backend` and report

---

## PHASE 9 — DEVELOPER EXPERIENCE

- [ ] Add a `Makefile` with targets: `make dev`, `make test`, `make lint`, 
      `make migrate`, `make reset-db`
- [ ] Add pre-commit hooks: ruff (linting), black (formatting), mypy (type checking)
- [ ] Add type hints to ALL functions in `backend/` that are missing them
- [ ] Run `ruff check --fix` and `black .` across the entire codebase
- [ ] Improve `README.md`: add an architecture diagram (ASCII or Mermaid), 
      troubleshooting section, and a FAQ
- [ ] Add `CONTRIBUTING.md` with dev setup instructions
- [ ] Add GitHub Actions CI workflow: lint + test on every push/PR

---

## PHASE 10 — SCALABILITY & FUTURE-PROOFING

- [ ] Abstract the embedding provider behind an interface so other models 
      (OpenAI CLIP, Cohere multimodal) can be swapped in via config
- [ ] Abstract the vector store behind an interface (pgvector today, 
      Pinecone/Qdrant tomorrow)
- [ ] Add multi-user support: scope all folders and embeddings to a `user_id`
- [ ] Add support for additional file types: PDF (embed each page), 
      HEIC/HEIF images, audio files (via Gemini audio embeddings)
- [ ] Design a background job queue (Celery or ARQ) for indexing so the 
      HTTP request doesn't time out on large folders
- [ ] Add a `GET /api/index/status-stream/{id}` SSE endpoint if not already present
      for live progress (verify it works correctly end-to-end)

---

## COMPLETION CRITERIA

Before finishing, confirm:
- [ ] All tests pass: `pytest tests/ -v`
- [ ] No ruff errors: `ruff check backend/`
- [ ] Type hints complete: `mypy backend/`
- [ ] Server starts cleanly: `uvicorn backend.main:app`
- [ ] A full index → search cycle works end-to-end
- [ ] `CHANGES.md` updated with a summary of every improvement made

Begin with Phase 1. Work autonomously. Ship it.