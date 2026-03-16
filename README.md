# Semantic Drive Search

Search your Google Drive images and videos using natural language. Powered by Google's [Gemini Embedding 2](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-embedding-2/) — the first natively multimodal embedding model.

Type "sunset over mountains" and get back the most visually similar images from your Drive folder, ranked by semantic similarity.

## How it works

1. Connect your Google Drive via OAuth2
2. Paste a folder URL — the app downloads each image/video and generates a 768-dimensional embedding using `gemini-embedding-2-preview`
3. Embeddings are stored in PostgreSQL with pgvector
4. Type a text query — it gets embedded in the same vector space and matched against your images via cosine similarity
5. Results are returned ranked by relevance with similarity scores

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension
- A [Google AI API key](https://aistudio.google.com/apikey) for Gemini
- Google Cloud OAuth2 credentials with Drive API enabled

### PostgreSQL setup

```bash
# Install pgvector (Ubuntu/Debian)
sudo apt install postgresql-16-pgvector

# Create the database
createdb semantic_search

# pgvector extension is created automatically on first run
```

### Google Cloud setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Google Drive API**
4. Go to **APIs & Services > Credentials**
5. Create an **OAuth 2.0 Client ID** (Web application)
6. Add `http://localhost:8000/auth/callback` as an authorized redirect URI
7. Note your Client ID and Client Secret

### Install and run

```bash
git clone https://github.com/seif9116/semantic-drive-search.git
cd semantic-drive-search

# Create venv and install
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env:
#   GOOGLE_API_KEY=your-gemini-api-key
#   GOOGLE_CLIENT_ID=your-oauth-client-id
#   GOOGLE_CLIENT_SECRET=your-oauth-client-secret
#   DATABASE_URL=postgresql://localhost:5432/semantic_search

# Run
uvicorn backend.main:app --reload
```

Open http://localhost:8000

## CLI (Claude Integration)

A CLI is included so Claude agents can search your Drive images directly via shell commands. All commands output JSON, making them easy to parse programmatically.

### Install the CLI

```bash
uv pip install -e .
# or: pip install -e .
```

This installs the `sds` command. You can also run commands directly with `python cli.py`.

### Commands

| Command | Description |
|---------|-------------|
| `sds list-folders` | List all folders that have been indexed |
| `sds index <folder_id>` | Index a new Google Drive folder |
| `sds search <query> <folder_id>` | Search indexed images/videos with natural language |
| `sds get-url <file_id>` | Get the Drive URL for a file ID |

### Workflow

```bash
# 1. See what's available
sds list-folders

# 2. Index a new folder (if needed)
sds index "https://drive.google.com/drive/folders/FOLDER_ID"

# 3. Find matching images
sds search "sunset over mountains" FOLDER_ID

# 4. Get a shareable link
sds get-url FILE_ID
```

### Claude Code integration

Add a skill entry in `claude-skill.md` and tell Claude to use `sds` (or `python /path/to/cli.py`) via Bash. See [claude-skill.md](claude-skill.md) for full usage examples.

## REST API

The search endpoint can also be called programmatically:

```
GET /api/search?q=sunset+over+mountains&folder_id=FOLDER_ID&limit=20
```

Response:
```json
{
  "query": "sunset over mountains",
  "results": [
    {
      "file_id": "abc123",
      "name": "IMG_4521.jpg",
      "mime_type": "image/jpeg",
      "similarity": 0.8723,
      "thumbnail_url": "/api/media/abc123/thumbnail"
    }
  ]
}
```

### All endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/login` | Start Google OAuth2 flow |
| `GET` | `/auth/callback` | OAuth2 callback |
| `GET` | `/auth/status` | Check auth status |
| `POST` | `/auth/logout` | Log out |
| `POST` | `/api/index` | Index a Drive folder (`{ "folder_id": "..." }`) |
| `GET` | `/api/index/status/{id}` | Polling indexing status |
| `GET` | `/api/index/status-stream/{id}` | SSE indexing progress |
| `GET` | `/api/folders` | List indexed folders |
| `DELETE` | `/api/folders/{id}` | Delete a folder's index |
| `GET` | `/api/search` | Semantic search (`?q=...&folder_id=...`) |
| `GET` | `/api/media/{id}` | Proxy file from Drive |
| `GET` | `/api/media/{id}/thumbnail` | Proxy thumbnail |

## Tech stack

- **Backend:** FastAPI
- **Embeddings:** Gemini Embedding 2 (`gemini-embedding-2-preview`, 768 dimensions)
- **Vector store:** PostgreSQL + pgvector (cosine similarity)
- **CLI:** Typer
- **Drive:** Google Drive API v3 (read-only)
- **Frontend:** Vanilla HTML/CSS/JS with Instrument Serif + DM Sans

## Testing

```bash
source .venv/bin/activate
python3 -m pytest tests/ -v

# Integration tests (requires DATABASE_URL)
DATABASE_URL=postgresql://localhost:5432/semantic_search python3 -m pytest tests/ -v
```

## Supported formats

- **Images:** JPEG, PNG, GIF, WebP (up to 20MB)
- **Videos:** MP4, QuickTime, AVI, WebM (up to 100MB)
