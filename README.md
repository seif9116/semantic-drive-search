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

### Install

```bash
pip install semantic-drive-search
```

This installs the `sds` command globally.

### First run — setup wizard

Run `sds` with no arguments. If no configuration exists it launches an interactive wizard that asks for your API keys and database URL, then saves them to `~/.sds/settings.json` (chmod 600):

```
  Welcome to Semantic Drive Search
  ─────────────────────────────────────
  No configuration found. Let's get you set up.

  Gemini API Key
  From https://aistudio.google.com/app/apikey
  › ****

  Google OAuth Client ID
  ...

  ✓ Settings saved to ~/.sds/settings.json
```

Run `sds setup` at any time to update credentials. Run `sds status` to see what's configured.

Settings are loaded in priority order: `~/.sds/settings.json` → environment variables → `.env` file. Existing `.env`-based setups keep working without changes.

### Commands

| Command | Description |
|---------|-------------|
| `sds` | Setup wizard (first run) or status (already configured) |
| `sds setup` | Re-run the setup wizard to update credentials |
| `sds status` | Show current configuration (secrets masked) |
| `sds list-folders` | List all folders that have been indexed |
| `sds index <folder_id>` | Index a new Google Drive folder |
| `sds search <query> <folder_id>` | Search indexed images/videos with natural language |
| `sds get-url <file_id>` | Get the Drive URL for a file ID |
| `sds organize <folder_id>` | Organize a Drive folder by date or semantic clustering |

### Workflow

```bash
# 0. Configure credentials (first time only)
sds

# 1. See what's available
sds list-folders

# 2. Index a new folder (if needed)
sds index "https://drive.google.com/drive/folders/FOLDER_ID"

# 3. Find matching images
sds search "sunset over mountains" FOLDER_ID

# 4. Get a shareable link
sds get-url FILE_ID
```

### Organize a folder

Automatically organize a Drive folder into subfolders:

```bash
# By date — groups files into "YYYY - Month" subfolders
sds organize FOLDER_ID --mode date

# By semantic similarity — k-means clustering + Gemini-named folders
sds organize FOLDER_ID --mode semantic --clusters 8

# Preview without moving files
sds organize FOLDER_ID --mode semantic --dry-run
```

### Claude Code skill

Install the `/sds` skill so Claude Code can search your Drive images in any project:

```bash
# From a local clone
./install-skill.sh

# Or directly from GitHub
curl -fsSL https://raw.githubusercontent.com/seif9116/semantic-drive-search/master/install-skill.sh | bash
```

This installs the skill to `~/.claude/skills/sds/`, registers the MCP server, and installs the `sds` CLI. After installation, restart Claude Code and type `/sds` to use it.

You can also load the full plugin (includes sub-skills for each command):

```bash
claude plugin add /path/to/semantic-drive-search
```

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
