# Semantic Drive Search

Search your Google Drive images and videos using natural language. Powered by Google's [Gemini Embedding 2](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-embedding-2/) — the first natively multimodal embedding model.

Type "sunset over mountains" and get back the most visually similar images from your Drive folder, ranked by semantic similarity.

## How it works

1. Connect your Google Drive via OAuth2
2. Paste a folder URL — the app downloads each image/video and generates a 768-dimensional embedding using `gemini-embedding-2-preview`
3. Embeddings are stored locally in ChromaDB
4. Type a text query — it gets embedded in the same vector space and matched against your images via cosine similarity
5. Results are returned ranked by relevance with similarity scores

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [Google AI API key](https://aistudio.google.com/apikey) for Gemini
- Google Cloud OAuth2 credentials with Drive API enabled

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
# Edit .env with your API keys:
#   GOOGLE_API_KEY=your-gemini-api-key
#   GOOGLE_CLIENT_ID=your-oauth-client-id
#   GOOGLE_CLIENT_SECRET=your-oauth-client-secret

# Run
uvicorn backend.main:app --reload
```

Open http://localhost:8000

## API

The search endpoint can be called programmatically (e.g., by Claude when building websites):

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
- **Vector store:** ChromaDB (local persistent storage, cosine similarity)
- **Drive:** Google Drive API v3 (read-only)
- **Frontend:** Vanilla HTML/CSS/JS with Instrument Serif + DM Sans

## Testing

```bash
source .venv/bin/activate
python3 -m pytest tests/ -v
```

## Supported formats

- **Images:** JPEG, PNG, GIF, WebP (up to 20MB)
- **Videos:** MP4, QuickTime, AVI, WebM (up to 100MB)
