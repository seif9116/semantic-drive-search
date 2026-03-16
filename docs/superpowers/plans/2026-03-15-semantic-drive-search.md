# Semantic Drive Search Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that indexes Google Drive images/videos using Gemini Embedding 2 and provides semantic text-to-image search.

**Architecture:** FastAPI backend handles OAuth2 with Google Drive, downloads media, generates embeddings via Gemini Embedding 2, stores them in ChromaDB, and serves a vanilla HTML/JS frontend with Tailwind CSS. The backend proxies Drive media to avoid CORS/auth issues.

**Tech Stack:** Python 3.12+, FastAPI, google-genai, google-api-python-client, chromadb, uvicorn, python-dotenv, Tailwind CSS (CDN)

**Spec:** `docs/superpowers/specs/2026-03-15-semantic-drive-search-design.md`

---

## File Structure

```
semantic_images/
├── .env.example              # Template for required env vars
├── .gitignore                # Python + data ignores
├── pyproject.toml            # Project config + dependencies
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI app, routes, CORS, static files
│   ├── config.py             # Settings loaded from .env
│   ├── auth.py               # Google OAuth2 flow (login, callback, token storage)
│   ├── drive.py              # Google Drive API: list files, download, thumbnails
│   ├── embeddings.py         # Gemini Embedding 2: embed images, text, video
│   ├── vector_store.py       # ChromaDB: store embeddings, similarity search
│   └── models.py             # Pydantic request/response models
├── static/
│   ├── index.html            # Main search UI
│   └── app.js                # Frontend logic (auth, indexing, search, display)
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Shared fixtures
│   ├── test_config.py
│   ├── test_vector_store.py
│   ├── test_embeddings.py
│   └── test_api.py
└── data/                     # ChromaDB persistent storage (gitignored)
```

---

## Chunk 1: Project Scaffolding + Config

### Task 1: Initialize project

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `pyproject.toml`
- Create: `backend/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /home/seif/university/projects/semantic_images
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
__pycache__/
*.py[cod]
.env
.venv/
data/
*.egg-info/
dist/
build/
.pytest_cache/
credentials.json
token.json
```

- [ ] **Step 3: Create .env.example**

```
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_CLIENT_ID=your-oauth-client-id
GOOGLE_CLIENT_SECRET=your-oauth-client-secret
APP_SECRET_KEY=random-secret-for-sessions
CHROMA_PERSIST_DIR=./data
EMBEDDING_DIMENSIONS=768
```

- [ ] **Step 4: Create pyproject.toml**

```toml
[project]
name = "semantic-drive-search"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "google-genai>=1.0.0",
    "google-api-python-client>=2.160.0",
    "google-auth-oauthlib>=1.2.0",
    "chromadb>=0.6.0",
    "python-dotenv>=1.0.0",
    "python-multipart>=0.0.20",
    "itsdangerous>=2.2.0",
    "starlette[full]>=0.45.0",
    "httpx>=0.28.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "httpx>=0.28.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 5: Create empty __init__.py files**

Create `backend/__init__.py` and `tests/__init__.py` (empty files).

- [ ] **Step 6: Set up venv and install deps**

```bash
cd /home/seif/university/projects/semantic_images
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

- [ ] **Step 7: Commit scaffolding**

```bash
git add .gitignore .env.example pyproject.toml backend/__init__.py tests/__init__.py
git commit -m "chore: initialize project scaffolding"
```

### Task 2: Config module

**Files:**
- Create: `backend/config.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write config module**

`backend/config.py`:
```python
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "change-me-in-production")
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./data")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    redirect_uri: str = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
    max_image_size: int = 20 * 1024 * 1024  # 20MB
    max_video_size: int = 100 * 1024 * 1024  # 100MB
    supported_image_types: tuple = ("image/jpeg", "image/png", "image/gif", "image/webp")
    supported_video_types: tuple = ("video/mp4", "video/quicktime", "video/x-msvideo", "video/webm")

    @property
    def supported_media_types(self) -> tuple:
        return self.supported_image_types + self.supported_video_types


settings = Settings()
```

- [ ] **Step 2: Write test**

`tests/conftest.py`:
```python
import pytest
```

`tests/test_config.py`:
```python
from backend.config import Settings


def test_default_settings():
    s = Settings()
    assert s.embedding_dimensions == 768
    assert s.max_image_size == 20 * 1024 * 1024
    assert "image/jpeg" in s.supported_image_types
    assert "video/mp4" in s.supported_video_types
    assert len(s.supported_media_types) == len(s.supported_image_types) + len(s.supported_video_types)
```

- [ ] **Step 3: Run test**

```bash
cd /home/seif/university/projects/semantic_images
source .venv/bin/activate
python3 -m pytest tests/test_config.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/config.py tests/conftest.py tests/test_config.py
git commit -m "feat: add config module with settings"
```

---

## Chunk 2: Pydantic Models + Vector Store

### Task 3: Pydantic models

**Files:**
- Create: `backend/models.py`

- [ ] **Step 1: Write models**

`backend/models.py`:
```python
from pydantic import BaseModel


class IndexRequest(BaseModel):
    folder_id: str


class IndexStatus(BaseModel):
    folder_id: str
    total_files: int
    processed: int
    failed: int
    status: str  # "idle" | "indexing" | "complete" | "error"
    current_file: str = ""


class SearchResult(BaseModel):
    file_id: str
    name: str
    mime_type: str
    similarity: float
    thumbnail_url: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class FolderInfo(BaseModel):
    folder_id: str
    name: str
    file_count: int
    indexed: bool
```

- [ ] **Step 2: Commit**

```bash
git add backend/models.py
git commit -m "feat: add pydantic request/response models"
```

### Task 4: ChromaDB vector store

**Files:**
- Create: `backend/vector_store.py`
- Create: `tests/test_vector_store.py`

- [ ] **Step 1: Write failing test**

`tests/test_vector_store.py`:
```python
import pytest
from backend.vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=str(tmp_path / "chroma"), dimensions=768)


def test_add_and_search(store):
    # Add a fake embedding
    store.add_embedding(
        folder_id="test_folder",
        file_id="file_1",
        embedding=[0.1] * 768,
        metadata={"name": "sunset.jpg", "mime_type": "image/jpeg", "folder_id": "test_folder"},
    )

    # Search with a similar vector
    results = store.search(folder_id="test_folder", query_embedding=[0.1] * 768, limit=5)
    assert len(results) == 1
    assert results[0]["file_id"] == "file_1"
    assert results[0]["name"] == "sunset.jpg"
    assert results[0]["similarity"] >= 0.99


def test_search_empty_collection(store):
    results = store.search(folder_id="nonexistent", query_embedding=[0.0] * 768, limit=5)
    assert results == []


def test_add_multiple_and_rank(store):
    store.add_embedding(
        folder_id="f1",
        file_id="a",
        embedding=[1.0, 0.0, 0.0] + [0.0] * 765,
        metadata={"name": "a.jpg", "mime_type": "image/jpeg", "folder_id": "f1"},
    )
    store.add_embedding(
        folder_id="f1",
        file_id="b",
        embedding=[0.9, 0.1, 0.0] + [0.0] * 765,
        metadata={"name": "b.jpg", "mime_type": "image/jpeg", "folder_id": "f1"},
    )
    store.add_embedding(
        folder_id="f1",
        file_id="c",
        embedding=[0.0, 1.0, 0.0] + [0.0] * 765,
        metadata={"name": "c.jpg", "mime_type": "image/jpeg", "folder_id": "f1"},
    )

    results = store.search(folder_id="f1", query_embedding=[1.0, 0.0, 0.0] + [0.0] * 765, limit=3)
    assert results[0]["file_id"] == "a"
    assert results[1]["file_id"] == "b"
    assert results[0]["similarity"] > results[1]["similarity"] > results[2]["similarity"]


def test_delete_folder(store):
    store.add_embedding(
        folder_id="del_me",
        file_id="x",
        embedding=[0.5] * 768,
        metadata={"name": "x.jpg", "mime_type": "image/jpeg", "folder_id": "del_me"},
    )
    assert store.get_file_count("del_me") == 1
    store.delete_folder("del_me")
    assert store.get_file_count("del_me") == 0


def test_get_file_count_nonexistent(store):
    assert store.get_file_count("nope") == 0


def test_has_file(store):
    store.add_embedding(
        folder_id="f",
        file_id="exists",
        embedding=[0.1] * 768,
        metadata={"name": "e.jpg", "mime_type": "image/jpeg", "folder_id": "f"},
    )
    assert store.has_file("f", "exists") is True
    assert store.has_file("f", "missing") is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_vector_store.py -v
```
Expected: FAIL (module not found)

- [ ] **Step 3: Write implementation**

`backend/vector_store.py`:
```python
import chromadb


class VectorStore:
    def __init__(self, persist_dir: str, dimensions: int = 768):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.dimensions = dimensions

    def _get_or_create_collection(self, folder_id: str):
        name = f"folder_{folder_id.replace('-', '_')}"
        # ChromaDB collection names: 3-63 chars, alphanumeric + underscores
        name = name[:63]
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_embedding(
        self,
        folder_id: str,
        file_id: str,
        embedding: list[float],
        metadata: dict,
    ):
        collection = self._get_or_create_collection(folder_id)
        collection.upsert(
            ids=[file_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    def search(
        self,
        folder_id: str,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[dict]:
        try:
            collection = self._get_or_create_collection(folder_id)
            if collection.count() == 0:
                return []
        except Exception:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(limit, collection.count()),
            include=["metadatas", "distances"],
        )

        items = []
        for i, file_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            similarity = 1 - distance  # cosine distance to similarity
            meta = results["metadatas"][0][i]
            items.append({
                "file_id": file_id,
                "name": meta.get("name", ""),
                "mime_type": meta.get("mime_type", ""),
                "similarity": round(similarity, 4),
                "folder_id": meta.get("folder_id", ""),
            })

        return items

    def delete_folder(self, folder_id: str):
        name = f"folder_{folder_id.replace('-', '_')}"[:63]
        try:
            self.client.delete_collection(name=name)
        except ValueError:
            pass

    def get_file_count(self, folder_id: str) -> int:
        try:
            collection = self._get_or_create_collection(folder_id)
            return collection.count()
        except Exception:
            return 0

    def has_file(self, folder_id: str, file_id: str) -> bool:
        try:
            collection = self._get_or_create_collection(folder_id)
            result = collection.get(ids=[file_id])
            return len(result["ids"]) > 0
        except Exception:
            return False

    def list_folders(self) -> list[str]:
        collections = self.client.list_collections()
        return [c.name.replace("folder_", "", 1) for c in collections]
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_vector_store.py -v
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/vector_store.py tests/test_vector_store.py
git commit -m "feat: add ChromaDB vector store with search"
```

---

## Chunk 3: Embeddings Module

### Task 5: Gemini Embedding 2 wrapper

**Files:**
- Create: `backend/embeddings.py`
- Create: `tests/test_embeddings.py`

- [ ] **Step 1: Write embeddings module**

`backend/embeddings.py`:
```python
import time
from google import genai
from google.genai import types
from backend.config import settings

MODEL = "gemini-embedding-2-preview"


def get_client() -> genai.Client:
    return genai.Client(api_key=settings.google_api_key)


def embed_image(image_bytes: bytes, mime_type: str, dimensions: int | None = None) -> list[float]:
    """Generate embedding for a single image."""
    client = get_client()
    dims = dimensions or settings.embedding_dimensions
    result = client.models.embed_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.EmbedContentConfig(output_dimensionality=dims),
    )
    return list(result.embeddings[0].values)


def embed_text(text: str, dimensions: int | None = None) -> list[float]:
    """Generate embedding for a text query."""
    client = get_client()
    dims = dimensions or settings.embedding_dimensions
    result = client.models.embed_content(
        model=MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=dims),
    )
    return list(result.embeddings[0].values)


def embed_image_with_retry(
    image_bytes: bytes, mime_type: str, max_retries: int = 3
) -> list[float] | None:
    """Embed image with exponential backoff on rate limits."""
    for attempt in range(max_retries):
        try:
            return embed_image(image_bytes, mime_type)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            raise
    return None


def embed_text_with_retry(text: str, max_retries: int = 3) -> list[float] | None:
    """Embed text with exponential backoff on rate limits."""
    for attempt in range(max_retries):
        try:
            return embed_text(text)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            raise
    return None
```

- [ ] **Step 2: Write test (unit test with mock)**

`tests/test_embeddings.py`:
```python
from unittest.mock import patch, MagicMock
from backend.embeddings import embed_image, embed_text, MODEL


def _make_mock_result(dims=768):
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1] * dims
    mock_result = MagicMock()
    mock_result.embeddings = [mock_embedding]
    return mock_result


@patch("backend.embeddings.get_client")
def test_embed_image(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _make_mock_result()
    mock_get_client.return_value = mock_client

    result = embed_image(b"fake-image-bytes", "image/jpeg")

    assert len(result) == 768
    assert all(v == 0.1 for v in result)
    mock_client.models.embed_content.assert_called_once()
    call_kwargs = mock_client.models.embed_content.call_args
    assert call_kwargs.kwargs["model"] == MODEL


@patch("backend.embeddings.get_client")
def test_embed_text(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _make_mock_result()
    mock_get_client.return_value = mock_client

    result = embed_text("sunset over mountains")

    assert len(result) == 768
    mock_client.models.embed_content.assert_called_once()
```

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest tests/test_embeddings.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/embeddings.py tests/test_embeddings.py
git commit -m "feat: add Gemini Embedding 2 wrapper"
```

---

## Chunk 4: Google Drive Integration

### Task 6: OAuth2 auth module

**Files:**
- Create: `backend/auth.py`

- [ ] **Step 1: Write auth module**

`backend/auth.py`:
```python
import json
from pathlib import Path
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from backend.config import settings

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_PATH = Path("token.json")


def get_auth_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.redirect_uri
    return flow


def get_authorization_url() -> tuple[str, str]:
    flow = get_auth_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url, state


def exchange_code(code: str) -> Credentials:
    flow = get_auth_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    _save_token(creds)
    return creds


def get_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)

    if creds and creds.valid:
        return creds

    return None


def _save_token(creds: Credentials):
    TOKEN_PATH.write_text(creds.to_json())


def is_authenticated() -> bool:
    creds = get_credentials()
    return creds is not None and creds.valid


def clear_credentials():
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
```

- [ ] **Step 2: Commit**

```bash
git add backend/auth.py
git commit -m "feat: add Google OAuth2 authentication"
```

### Task 7: Google Drive client

**Files:**
- Create: `backend/drive.py`

- [ ] **Step 1: Write Drive client**

`backend/drive.py`:
```python
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from backend.config import settings


def get_drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def list_media_files(creds: Credentials, folder_id: str) -> list[dict]:
    """List all image and video files in a Drive folder (recursive)."""
    service = get_drive_service(creds)
    all_files = []

    # Build mime type query
    image_types = settings.supported_image_types
    video_types = settings.supported_video_types
    mime_queries = [f"mimeType='{mt}'" for mt in image_types + video_types]
    mime_filter = " or ".join(mime_queries)

    query = f"'{folder_id}' in parents and ({mime_filter}) and trashed=false"

    page_token = None
    while True:
        response = service.files().list(
            q=query,
            spaces="drive",
            fields="nextPageToken, files(id, name, mimeType, size, createdTime, thumbnailLink)",
            pageToken=page_token,
            pageSize=100,
        ).execute()

        files = response.get("files", [])
        for f in files:
            size = int(f.get("size", 0))
            mime = f.get("mimeType", "")

            # Skip files that are too large
            if mime in image_types and size > settings.max_image_size:
                continue
            if mime in video_types and size > settings.max_video_size:
                continue

            all_files.append({
                "id": f["id"],
                "name": f["name"],
                "mimeType": mime,
                "size": size,
                "createdTime": f.get("createdTime", ""),
                "thumbnailLink": f.get("thumbnailLink", ""),
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    # Also recurse into subfolders
    subfolder_query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    page_token = None
    while True:
        response = service.files().list(
            q=subfolder_query,
            spaces="drive",
            fields="nextPageToken, files(id)",
            pageToken=page_token,
            pageSize=100,
        ).execute()

        for subfolder in response.get("files", []):
            all_files.extend(list_media_files(creds, subfolder["id"]))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_files


def download_file(creds: Credentials, file_id: str) -> bytes:
    """Download a file's content from Drive."""
    service = get_drive_service(creds)
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return buffer.getvalue()


def get_folder_name(creds: Credentials, folder_id: str) -> str:
    """Get the name of a Drive folder."""
    service = get_drive_service(creds)
    folder = service.files().get(fileId=folder_id, fields="name").execute()
    return folder.get("name", folder_id)
```

- [ ] **Step 2: Commit**

```bash
git add backend/drive.py
git commit -m "feat: add Google Drive file listing and download"
```

---

## Chunk 5: FastAPI Application

### Task 8: Main FastAPI app with all routes

**Files:**
- Create: `backend/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write FastAPI application**

`backend/main.py`:
```python
import asyncio
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from backend.config import settings
from backend.models import IndexRequest, SearchResponse, SearchResult, FolderInfo
from backend import auth, drive, embeddings, vector_store as vs

# Global state
store: vs.VectorStore | None = None
indexing_status: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    store = vs.VectorStore(
        persist_dir=settings.chroma_persist_dir,
        dimensions=settings.embedding_dimensions,
    )
    yield


app = FastAPI(title="Semantic Drive Search", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.app_secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# --- Auth Routes ---


@app.get("/auth/login")
async def login():
    url, state = auth.get_authorization_url()
    return RedirectResponse(url)


@app.get("/auth/callback")
async def auth_callback(code: str, state: str = ""):
    try:
        auth.exchange_code(code)
        return RedirectResponse("/")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Auth failed: {e}")


@app.get("/auth/status")
async def auth_status():
    return {"authenticated": auth.is_authenticated()}


@app.post("/auth/logout")
async def logout():
    auth.clear_credentials()
    return {"status": "logged out"}


# --- Indexing Routes ---


@app.post("/api/index")
async def start_indexing(req: IndexRequest):
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated with Google Drive")

    folder_id = _extract_folder_id(req.folder_id)

    if indexing_status.get(folder_id, {}).get("status") == "indexing":
        raise HTTPException(status_code=409, detail="Already indexing this folder")

    indexing_status[folder_id] = {
        "folder_id": folder_id,
        "total_files": 0,
        "processed": 0,
        "failed": 0,
        "status": "indexing",
        "current_file": "Listing files...",
    }

    asyncio.create_task(_index_folder(creds, folder_id))

    return {"status": "started", "folder_id": folder_id}


@app.get("/api/index/status/{folder_id}")
async def get_index_status(folder_id: str):
    folder_id = _extract_folder_id(folder_id)
    status = indexing_status.get(folder_id)
    if not status:
        # Check if already indexed
        count = store.get_file_count(folder_id)
        if count > 0:
            return {
                "folder_id": folder_id,
                "total_files": count,
                "processed": count,
                "failed": 0,
                "status": "complete",
                "current_file": "",
            }
        return {"folder_id": folder_id, "status": "idle", "total_files": 0, "processed": 0, "failed": 0, "current_file": ""}
    return status


@app.get("/api/index/status-stream/{folder_id}")
async def index_status_stream(folder_id: str):
    folder_id = _extract_folder_id(folder_id)

    async def event_generator():
        while True:
            status = indexing_status.get(folder_id, {"status": "idle"})
            yield f"data: {json.dumps(status)}\n\n"
            if status.get("status") in ("complete", "error"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/folders")
async def list_folders():
    folder_ids = store.list_folders()
    creds = auth.get_credentials()
    folders = []
    for fid in folder_ids:
        name = fid
        if creds:
            try:
                name = drive.get_folder_name(creds, fid)
            except Exception:
                pass
        folders.append(FolderInfo(
            folder_id=fid,
            name=name,
            file_count=store.get_file_count(fid),
            indexed=True,
        ))
    return folders


@app.delete("/api/folders/{folder_id}")
async def delete_folder(folder_id: str):
    folder_id = _extract_folder_id(folder_id)
    store.delete_folder(folder_id)
    indexing_status.pop(folder_id, None)
    return {"status": "deleted"}


# --- Search Routes ---


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1),
    folder_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
):
    folder_id = _extract_folder_id(folder_id)
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")

    query_embedding = embeddings.embed_text_with_retry(q)
    if query_embedding is None:
        raise HTTPException(status_code=500, detail="Failed to generate query embedding")

    raw_results = store.search(
        folder_id=folder_id,
        query_embedding=query_embedding,
        limit=limit,
    )

    results = [
        SearchResult(
            file_id=r["file_id"],
            name=r["name"],
            mime_type=r["mime_type"],
            similarity=r["similarity"],
            thumbnail_url=f"/api/media/{r['file_id']}/thumbnail",
        )
        for r in raw_results
    ]

    return SearchResponse(query=q, results=results)


# --- Media Proxy Routes ---


@app.get("/api/media/{file_id}")
async def get_media(file_id: str):
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        content = drive.download_file(creds, file_id)
        # Detect mime type from content or default
        return Response(content=content, media_type="application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}")


@app.get("/api/media/{file_id}/thumbnail")
async def get_thumbnail(file_id: str):
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        content = drive.download_file(creds, file_id)
        return Response(content=content, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}")


# --- Root ---


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text())
    return HTMLResponse("<h1>Semantic Drive Search</h1><p>Static files not found.</p>")


# --- Helpers ---


def _extract_folder_id(folder_input: str) -> str:
    """Extract folder ID from a Google Drive URL or raw ID."""
    # Match: https://drive.google.com/drive/folders/FOLDER_ID?...
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", folder_input)
    if match:
        return match.group(1)
    # Already a raw ID
    return folder_input.strip()


async def _index_folder(creds, folder_id: str):
    """Background task to index all media in a Drive folder."""
    try:
        files = drive.list_media_files(creds, folder_id)
        indexing_status[folder_id]["total_files"] = len(files)

        if len(files) == 0:
            indexing_status[folder_id]["status"] = "complete"
            return

        for f in files:
            file_id = f["id"]
            name = f["name"]
            mime_type = f["mimeType"]

            indexing_status[folder_id]["current_file"] = name

            # Skip if already indexed
            if store.has_file(folder_id, file_id):
                indexing_status[folder_id]["processed"] += 1
                continue

            try:
                file_bytes = drive.download_file(creds, file_id)

                if mime_type in settings.supported_image_types:
                    embedding = embeddings.embed_image_with_retry(file_bytes, mime_type)
                else:
                    # For video, try embedding (Gemini supports it)
                    embedding = embeddings.embed_image_with_retry(file_bytes, mime_type)

                if embedding:
                    store.add_embedding(
                        folder_id=folder_id,
                        file_id=file_id,
                        embedding=embedding,
                        metadata={
                            "name": name,
                            "mime_type": mime_type,
                            "folder_id": folder_id,
                            "size": str(f.get("size", 0)),
                        },
                    )
                    indexing_status[folder_id]["processed"] += 1
                else:
                    indexing_status[folder_id]["failed"] += 1

            except Exception as e:
                print(f"Error indexing {name}: {e}")
                indexing_status[folder_id]["failed"] += 1

            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)

        indexing_status[folder_id]["status"] = "complete"
        indexing_status[folder_id]["current_file"] = ""

    except Exception as e:
        indexing_status[folder_id]["status"] = "error"
        indexing_status[folder_id]["current_file"] = str(e)
```

- [ ] **Step 2: Write API tests**

`tests/test_api.py`:
```python
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.main import app, _extract_folder_id


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_extract_folder_id_url():
    url = "https://drive.google.com/drive/folders/1abc_XYZ-123?usp=sharing"
    assert _extract_folder_id(url) == "1abc_XYZ-123"


def test_extract_folder_id_raw():
    assert _extract_folder_id("1abc_XYZ-123") == "1abc_XYZ-123"


def test_auth_status_unauthenticated(client):
    with patch("backend.main.auth.is_authenticated", return_value=False):
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is False


def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_search_requires_auth(client):
    with patch("backend.main.auth.get_credentials", return_value=None):
        resp = client.get("/api/search?q=sunset&folder_id=abc")
        assert resp.status_code == 401
```

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest tests/test_api.py -v
```
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/main.py tests/test_api.py
git commit -m "feat: add FastAPI app with auth, indexing, search, and media proxy"
```

---

## Chunk 6: Frontend

### Task 9: Build search UI

**Files:**
- Create: `static/index.html`
- Create: `static/app.js`

- [ ] **Step 1: Create index.html**

Build a clean, modern search interface with Tailwind CSS. Key features:
- Google Drive auth button
- Folder ID input with "Index" button
- Indexing progress bar
- Large search bar
- Responsive image grid with similarity scores
- Full-size image modal on click
- Dark mode by default
- Use the `frontend-design` skill for high-quality visuals

- [ ] **Step 2: Create app.js**

Frontend logic handling:
- Auth state management (check /auth/status, show login button or folder input)
- Folder indexing (POST /api/index, poll SSE for progress)
- Search (GET /api/search, debounced input, display results grid)
- Image modal (click to view full size via /api/media/{id})
- Indexed folders list (GET /api/folders)

- [ ] **Step 3: Verify frontend loads**

```bash
cd /home/seif/university/projects/semantic_images
source .venv/bin/activate
python3 -m uvicorn backend.main:app --reload --port 8000 &
sleep 2
curl -s http://localhost:8000/ | head -5
kill %1
```
Expected: HTML content returned

- [ ] **Step 4: Commit**

```bash
git add static/
git commit -m "feat: add search UI with Tailwind CSS"
```

---

## Chunk 7: Final Integration

### Task 10: Run full app and verify

- [ ] **Step 1: Run all tests**

```bash
python3 -m pytest tests/ -v
```
Expected: ALL PASS

- [ ] **Step 2: Verify app starts**

```bash
python3 -m uvicorn backend.main:app --port 8000
```
Expected: App starts, serves UI at http://localhost:8000

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: semantic drive search - complete implementation"
```
