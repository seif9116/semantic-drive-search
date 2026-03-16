"""
CLI for Semantic Drive Search.

Exposes search, indexing, and folder management as subcommands.
Claude agents can call these directly via Bash and parse the JSON output.

Usage:
  python cli.py list-folders
  python cli.py index <folder_id>
  python cli.py search <query> <folder_id> [--limit N]
  python cli.py get-url <file_id>
"""

import json
import re
import time

import typer

from backend.config import settings
from backend.vector_store import VectorStore
from backend import embeddings, auth, drive

app = typer.Typer(help="Semantic Drive Search CLI — search Google Drive images with natural language.")

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


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural language description of what you are looking for."),
    folder_id: str = typer.Argument(..., help="Google Drive folder ID (or full URL) that has been indexed."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum number of results to return."),
) -> None:
    """Search indexed Google Drive images and videos using a natural language query."""
    folder_id = _extract_folder_id(folder_id)

    query_embedding = embeddings.embed_text_with_retry(query)
    if query_embedding is None:
        typer.echo(json.dumps({"error": "Failed to generate query embedding. Try again shortly."}))
        raise typer.Exit(1)

    raw_results = store.search(
        folder_id=folder_id,
        query_embedding=query_embedding,
        limit=limit,
    )

    results = [
        {
            "file_id": r["file_id"],
            "name": r["name"],
            "mime_type": r["mime_type"],
            "similarity": r["similarity"],
            "drive_url": DRIVE_FILE_URL.format(file_id=r["file_id"]),
        }
        for r in raw_results
    ]

    typer.echo(json.dumps({"query": query, "folder_id": folder_id, "results": results}, indent=2))


@app.command(name="list-folders")
def list_folders() -> None:
    """List all Google Drive folders that have been indexed for semantic search."""
    folder_ids = store.list_folders()

    folders = [
        {"folder_id": fid, "file_count": store.get_file_count(fid)}
        for fid in folder_ids
    ]

    typer.echo(json.dumps({"folders": folders}, indent=2))


@app.command()
def index(
    folder_id: str = typer.Argument(..., help="Google Drive folder ID or full folder URL to index."),
) -> None:
    """Index all images and videos in a Google Drive folder for semantic search.

    Already-indexed files are skipped automatically. Supported formats:
    JPEG, PNG, GIF, WebP images and MP4, QuickTime, AVI, WebM videos.
    """
    folder_id = _extract_folder_id(folder_id)

    creds = auth.get_credentials()
    if creds is None:
        typer.echo(json.dumps({
            "error": "Not authenticated with Google Drive. "
                     "Run the web app first and complete OAuth login to create token.json."
        }))
        raise typer.Exit(1)

    try:
        files = drive.list_media_files(creds, folder_id)
    except Exception as e:
        typer.echo(json.dumps({"error": f"Failed to list files in folder: {e}"}))
        raise typer.Exit(1)

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

        if mime_type not in supported_types:
            skipped += 1
            continue

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

        time.sleep(0.5)

    summary: dict = {
        "folder_id": folder_id,
        "total_files_found": total,
        "newly_indexed": indexed,
        "skipped_already_indexed": skipped,
        "failed": failed,
    }

    if errors:
        summary["errors"] = errors[:20]

    typer.echo(json.dumps(summary, indent=2))


@app.command(name="get-url")
def get_url(
    file_id: str = typer.Argument(..., help="The Google Drive file ID."),
) -> None:
    """Get the Google Drive viewing URL for a file."""
    typer.echo(DRIVE_FILE_URL.format(file_id=file_id))


if __name__ == "__main__":
    app()
