import asyncio
import json
import re
from contextlib import asynccontextmanager, suppress
from hashlib import md5
from pathlib import Path
from time import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from backend import auth, drive, embeddings
from backend import vector_store as vs
from backend.config import settings
from backend.models import FolderInfo, IndexRequest, SearchResponse, SearchResult

# Global state
store: vs.VectorStore | None = None
indexing_status: dict = {}

# Simple in-memory cache for search results (expires after 5 minutes)
_search_cache: dict = {}
CACHE_TTL_SECONDS = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    global store
    try:
        store = vs.VectorStore(
            database_url=settings.database_url,
            dimensions=settings.embedding_dimensions,
        )
    except Exception as e:
        # Allow app to start without DB (needed for OAuth-only mode)
        print(f"Warning: Could not connect to database ({e}). Search/indexing disabled, OAuth still works.")
        store = None
    yield


def _require_store():
    if store is None:
        raise HTTPException(status_code=503, detail="Database not connected. Check DATABASE_URL in your config.")


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


# --- Health Check ---


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    health = {
        "status": "healthy",
        "database": "unknown",
        "gemini_api": "unknown",
        "auth": "unknown",
    }

    # Check database connectivity
    try:
        if store is not None:
            # Simple query to verify DB connection
            store.list_folders()
            health["database"] = "connected"
        else:
            health["database"] = "not_configured"
            health["status"] = "degraded"
    except Exception as e:
        health["database"] = f"error: {str(e)[:50]}"
        health["status"] = "unhealthy"

    # Check Gemini API
    try:
        if settings.google_api_key:
            # We don't want to make an actual API call on every health check
            # Just verify the key is configured
            health["gemini_api"] = "configured"
        else:
            health["gemini_api"] = "not_configured"
            health["status"] = "degraded"
    except Exception as e:
        health["gemini_api"] = f"error: {str(e)[:50]}"

    # Check auth status
    try:
        if auth.is_authenticated():
            health["auth"] = "authenticated"
        else:
            health["auth"] = "not_authenticated"
    except Exception as e:
        health["auth"] = f"error: {str(e)[:50]}"

    status_code = 200 if health["status"] == "healthy" else 503
    return Response(
        content=json.dumps(health),
        media_type="application/json",
        status_code=status_code,
    )


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
    _require_store()
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
    _require_store()
    folder_id = _extract_folder_id(folder_id)
    status = indexing_status.get(folder_id)
    if not status:
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
    _require_store()
    folder_ids = store.list_folders()
    creds = auth.get_credentials()
    folders = []
    for fid in folder_ids:
        name = fid
        if creds:
            with suppress(Exception):
                name = drive.get_folder_name(creds, fid)
        folders.append(FolderInfo(
            folder_id=fid,
            name=name,
            file_count=store.get_file_count(fid),
            indexed=True,
        ))
    return folders


@app.delete("/api/folders/{folder_id}")
async def delete_folder(folder_id: str):
    _require_store()
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
    offset: int = Query(default=0, ge=0),
    min_similarity: float = Query(default=0.0, ge=0.0, le=1.0),
):
    _require_store()
    folder_id = _extract_folder_id(folder_id)
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Check cache
    cache_key = md5(f"{q}:{folder_id}:{limit}:{offset}:{min_similarity}".encode()).hexdigest()
    cached = _search_cache.get(cache_key)
    if cached and time() - cached["timestamp"] < CACHE_TTL_SECONDS:
        return cached["response"]

    try:
        query_embedding = embeddings.embed_text_with_retry(q)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Embedding service unavailable: {e}")
    if query_embedding is None:
        raise HTTPException(status_code=500, detail="Failed to generate query embedding")

    raw_results = store.search(
        folder_id=folder_id,
        query_embedding=query_embedding,
        limit=limit,
        offset=offset,
        min_similarity=min_similarity,
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

    response = SearchResponse(query=q, results=results)

    # Cache the response
    _search_cache[cache_key] = {"response": response, "timestamp": time()}

    return response


@app.get("/api/similar/{file_id}")
async def find_similar(
    file_id: str,
    folder_id: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    min_similarity: float = Query(default=0.5, ge=0.0, le=1.0),
):
    """Find files similar to a given file (more like this)."""
    _require_store()
    folder_id = _extract_folder_id(folder_id)
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")

    raw_results = store.search_similar(
        file_id=file_id,
        folder_id=folder_id,
        limit=limit,
        min_similarity=min_similarity,
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

    return {"file_id": file_id, "results": results}


# --- Browse Routes ---


@app.get("/api/browse/{folder_id}")
async def browse_folder(folder_id: str):
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    folder_id = _extract_folder_id(folder_id)
    try:
        files = drive.list_media_files(creds, folder_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to list files: {e}")
    return {
        "folder_id": folder_id,
        "total_files": len(files),
        "files": [
            {
                "file_id": f["id"],
                "name": f["name"],
                "mime_type": f["mimeType"],
                "size": f["size"],
                "created_time": f.get("createdTime", ""),
                "thumbnail_url": f"/api/media/{f['id']}/thumbnail",
            }
            for f in files
        ],
    }


# --- Media Proxy Routes ---


@app.get("/api/media/{file_id}")
async def get_media(file_id: str):
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        content = drive.download_file(creds, file_id)
        return Response(content=content, media_type="application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}")


@app.get("/api/media/{file_id}/thumbnail")
async def get_thumbnail(file_id: str):
    creds = auth.get_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        # Fetch the small CDN-hosted thumbnail instead of downloading the full file
        service = drive.get_drive_service(creds)
        file_meta = service.files().get(
            fileId=file_id, fields="thumbnailLink", supportsAllDrives=True,
        ).execute()
        thumbnail_link = file_meta.get("thumbnailLink")
        if thumbnail_link:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(thumbnail_link, follow_redirects=True, timeout=10)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    return Response(content=resp.content, media_type=content_type)
        # Fallback: download the full file if no thumbnail available
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
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", folder_input)
    if match:
        return match.group(1)
    return folder_input.strip()


async def _index_folder(creds, folder_id: str):
    """Background task to index all media in a Drive folder."""
    from backend.logging_config import get_logger
    log = get_logger(__name__)

    try:
        log.info("Starting indexing", folder_id=folder_id)
        files = drive.list_media_files(creds, folder_id)
        indexing_status[folder_id]["total_files"] = len(files)

        if len(files) == 0:
            log.info("No files to index", folder_id=folder_id)
            indexing_status[folder_id]["status"] = "complete"
            return

        for f in files:
            file_id = f["id"]
            name = f["name"]
            mime_type = f["mimeType"]

            indexing_status[folder_id]["current_file"] = name

            # Skip if already indexed
            if store.has_file(folder_id, file_id):
                log.debug("Skipping already indexed file", file_id=file_id)
                indexing_status[folder_id]["processed"] += 1
                continue

            try:
                file_bytes = drive.download_file(creds, file_id)

                # Use the new signature that returns (embedding, file_hash)
                embedding, file_hash = embeddings.embed_image_with_retry(
                    file_bytes, mime_type, compute_hash=True
                )

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
                        file_hash=file_hash,
                    )
                    indexing_status[folder_id]["processed"] += 1
                    log.debug("Indexed file", file_id=file_id)
                else:
                    indexing_status[folder_id]["failed"] += 1
                    log.warning("Failed to generate embedding", file_id=file_id)

            except Exception as e:
                log.error("Error indexing file", file_id=file_id, error=str(e)[:100])
                indexing_status[folder_id]["failed"] += 1

            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)

        processed = indexing_status[folder_id]["processed"]
        failed = indexing_status[folder_id]["failed"]
        log.info(
            "Indexing complete",
            folder_id=folder_id,
            processed=processed,
            failed=failed,
        )
        indexing_status[folder_id]["status"] = "complete"
        indexing_status[folder_id]["current_file"] = ""

    except Exception as e:
        log.error("Indexing failed", folder_id=folder_id, error=str(e)[:100])
        indexing_status[folder_id]["status"] = "error"
        indexing_status[folder_id]["current_file"] = str(e)
