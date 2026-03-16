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
    try:
        store = vs.VectorStore(
            database_url=settings.database_url,
            dimensions=settings.embedding_dimensions,
        )
    except Exception:
        # Allow app to start without DB (needed for OAuth-only mode)
        store = None
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
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", folder_input)
    if match:
        return match.group(1)
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
