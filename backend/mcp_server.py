"""
MCP Server for Semantic Drive Search.

Exposes tools that let Claude agents search Google Drive images and videos
using natural language queries. Built on top of the Semantic Drive Search
backend which uses Gemini embeddings and pgvector for similarity search.
"""

import json
import re
import time

from mcp.server.fastmcp import FastMCP

from backend import auth, drive, embeddings
from backend.config import settings
from backend.vector_store import VectorStore

mcp = FastMCP(
    "Semantic Drive Search",
    dependencies=["google-genai", "psycopg[binary]", "pgvector"],
)

store = VectorStore(
    database_url=settings.database_url,
    dimensions=settings.embedding_dimensions,
)

DRIVE_FILE_URL = "https://drive.google.com/file/d/{file_id}/view"


def _extract_folder_id(folder_input: str) -> str:
    """Extract a folder ID from a Google Drive URL or return the raw ID."""
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", folder_input)
    if match:
        return match.group(1)
    return folder_input.strip()


@mcp.tool()
def search_images(query: str, folder_id: str, limit: int = 10) -> str:
    """Search indexed Google Drive images and videos using a natural language query.

    Embeds the text query and performs a cosine-similarity search against all
    media files previously indexed from the specified Drive folder.

    Args:
        query: A natural language description of what you are looking for.
               Examples: "sunset over mountains", "group photo at dinner",
               "whiteboard with architecture diagram".
        folder_id: The Google Drive folder ID (or full URL) that has been
                   previously indexed. Use list_indexed_folders to discover
                   available folders.
        limit: Maximum number of results to return (default 10).

    Returns:
        A JSON string containing a list of matching files sorted by relevance.
        Each result includes file_id, name, mime_type, similarity score, and
        a direct drive_url to view the file.
    """
    folder_id = _extract_folder_id(folder_id)

    query_embedding = embeddings.embed_text_with_retry(query)
    if query_embedding is None:
        return json.dumps({"error": "Failed to generate query embedding. Try again shortly."})

    raw_results = store.search(
        folder_id=folder_id,
        query_embedding=query_embedding,
        limit=limit,
    )

    results = []
    for r in raw_results:
        results.append({
            "file_id": r["file_id"],
            "name": r["name"],
            "mime_type": r["mime_type"],
            "similarity": r["similarity"],
            "drive_url": DRIVE_FILE_URL.format(file_id=r["file_id"]),
        })

    return json.dumps({"query": query, "folder_id": folder_id, "results": results}, indent=2)


@mcp.tool()
def list_indexed_folders() -> str:
    """List all Google Drive folders that have been indexed for semantic search.

    Returns a JSON string with each folder's ID and the number of files
    currently stored in the index. Use this to discover which folders are
    available before calling search_images.
    """
    folder_ids = store.list_folders()

    folders = []
    for fid in folder_ids:
        folders.append({
            "folder_id": fid,
            "file_count": store.get_file_count(fid),
        })

    return json.dumps({"folders": folders}, indent=2)


@mcp.tool()
def index_folder(folder_id: str) -> str:
    """Index all images and videos in a Google Drive folder for semantic search.

    Downloads every supported media file from the specified folder (including
    subfolders), generates an embedding for each file using Gemini, and stores
    the embeddings in the vector database. Files that have already been indexed
    are skipped automatically.

    This operation can take a while for large folders. Supported media types
    include JPEG, PNG, GIF, WebP images and MP4, QuickTime, AVI, WebM videos.

    Requires prior Google OAuth authentication (a valid token.json must exist).

    Args:
        folder_id: The Google Drive folder ID or a full Drive folder URL.

    Returns:
        A JSON summary with counts of files indexed, skipped, and failed.
    """
    folder_id = _extract_folder_id(folder_id)

    creds = auth.get_credentials()
    if creds is None:
        return json.dumps({
            "error": "Not authenticated with Google Drive. "
                     "Run the web app first and complete OAuth login to create token.json."
        })

    try:
        files = drive.list_media_files(creds, folder_id)
    except Exception as e:
        return json.dumps({"error": f"Failed to list files in folder: {e}"})

    total = len(files)
    indexed = 0
    skipped = 0
    failed = 0
    errors = []

    supported_types = settings.supported_image_types + settings.supported_video_types

    for f in files:
        file_id = f["id"]
        name = f["name"]
        mime_type = f["mimeType"]

        # Skip unsupported mime types (shouldn't happen, but be safe)
        if mime_type not in supported_types:
            skipped += 1
            continue

        # Skip files already in the index
        if store.has_file(folder_id, file_id):
            skipped += 1
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
                indexed += 1
            else:
                failed += 1
                errors.append(f"{name}: embedding returned None")

        except Exception as e:
            failed += 1
            errors.append(f"{name}: {e}")

        # Brief pause between files to respect API rate limits
        time.sleep(0.5)

    summary = {
        "folder_id": folder_id,
        "total_files_found": total,
        "newly_indexed": indexed,
        "skipped_already_indexed": skipped,
        "failed": failed,
    }

    if errors:
        summary["errors"] = errors[:20]  # Cap to avoid huge output

    return json.dumps(summary, indent=2)


@mcp.tool()
def get_image_url(file_id: str) -> str:
    """Get the Google Drive viewing URL for a file.

    A simple utility that constructs the shareable Google Drive link for a
    given file ID. Useful for embedding images in websites or sharing links.

    Args:
        file_id: The Google Drive file ID.

    Returns:
        The Google Drive URL to view the file.
    """
    return DRIVE_FILE_URL.format(file_id=file_id)


@mcp.tool()
def browse_drive(folder_id: str, file_type: str = "all") -> str:
    """Browse all images and videos in a Google Drive folder without indexing.

    Lists the files directly from Drive. Useful for seeing what's in a folder
    before deciding to index it, or when you just need to find a file by name.

    Args:
        folder_id: Google Drive folder ID or full folder URL.
        file_type: Filter results: 'all', 'images', or 'videos'.

    Returns:
        JSON with folder_id, total file count, and list of files with
        file_id, name, mime_type, size, created time, and drive_url.
    """
    folder_id = _extract_folder_id(folder_id)

    creds = auth.get_credentials()
    if creds is None:
        return json.dumps({"error": "Not authenticated. Run `sds auth` first."})

    try:
        files = drive.list_media_files(creds, folder_id)
    except Exception as e:
        return json.dumps({"error": f"Failed to list files: {e}"})

    if file_type == "images":
        files = [f for f in files if f["mimeType"].startswith("image/")]
    elif file_type == "videos":
        files = [f for f in files if f["mimeType"].startswith("video/")]

    results = [
        {
            "file_id": f["id"],
            "name": f["name"],
            "mime_type": f["mimeType"],
            "size_mb": round(f.get("size", 0) / (1024 * 1024), 2),
            "drive_url": DRIVE_FILE_URL.format(file_id=f["id"]),
        }
        for f in files
    ]

    return json.dumps({"folder_id": folder_id, "total_files": len(results), "files": results}, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
