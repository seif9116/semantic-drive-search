"""
CLI for Semantic Drive Search.

Exposes search, indexing, and folder management as subcommands.
Claude agents can call these directly via Bash and parse the JSON output.

Usage:
  sds                          → setup wizard (if unconfigured) or status
  sds setup                    → run setup wizard
  sds list-folders
  sds index <folder_id>
  sds search <query> <folder_id> [--limit N]
  sds get-url <file_id>
"""

import json
import re
import time
from pathlib import Path

import typer

DRIVE_FILE_URL = "https://drive.google.com/file/d/{file_id}/view"
SDS_DIR = Path.home() / ".sds"
SDS_SETTINGS = SDS_DIR / "settings.json"

# ── Setup helpers ─────────────────────────────────────────────────────────────

_FIELDS = [
    {
        "key": "GOOGLE_API_KEY",
        "label": "Google (Gemini) API Key",
        "hint": "From https://aistudio.google.com/app/apikey",
        "secret": True,
    },
    {
        "key": "GOOGLE_CLIENT_ID",
        "label": "Google OAuth Client ID",
        "hint": "From Google Cloud Console → APIs & Services → Credentials",
        "secret": False,
    },
    {
        "key": "GOOGLE_CLIENT_SECRET",
        "label": "Google OAuth Client Secret",
        "hint": "Same credentials page as Client ID",
        "secret": True,
    },
    {
        "key": "DATABASE_URL",
        "label": "PostgreSQL Database URL",
        "hint": "e.g. postgresql://user:pass@localhost:5432/semantic_search",
        "secret": False,
        "default": "postgresql://localhost:5432/semantic_search",
    },
]


def _load_saved() -> dict:
    if SDS_SETTINGS.exists():
        try:
            return json.loads(SDS_SETTINGS.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save(data: dict) -> None:
    SDS_DIR.mkdir(parents=True, exist_ok=True)
    SDS_SETTINGS.write_text(json.dumps(data, indent=2))
    SDS_SETTINGS.chmod(0o600)


def _is_configured() -> bool:
    saved = _load_saved()
    return bool(saved.get("GOOGLE_API_KEY") and saved.get("DATABASE_URL"))


def _mask(value: str) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


# ── App ───────────────────────────────────────────────────────────────────────

app = typer.Typer(
    help="Semantic Drive Search — search Google Drive images with natural language.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback()
def _default(ctx: typer.Context) -> None:
    """Run setup wizard when invoked with no subcommand."""
    if ctx.invoked_subcommand is not None:
        return

    if _is_configured():
        _cmd_status()
    else:
        typer.echo("")
        typer.echo("  Welcome to Semantic Drive Search")
        typer.echo("  ─────────────────────────────────────")
        typer.echo("  No configuration found. Let's get you set up.")
        typer.echo("")
        _run_setup()


# ── Setup command ─────────────────────────────────────────────────────────────

def _run_setup() -> None:
    saved = _load_saved()

    typer.echo("  You will need:")
    typer.echo("    • A Google Gemini API key (for embeddings)")
    typer.echo("    • Google OAuth credentials (for Drive access)")
    typer.echo("    • A PostgreSQL connection string (with pgvector)")
    typer.echo("")
    typer.echo("  Press Enter to keep an existing value. Ctrl+C to quit.")
    typer.echo("")

    updated: dict = dict(saved)

    for field in _FIELDS:
        key = field["key"]
        current = saved.get(key, field.get("default", ""))
        display_current = _mask(current) if field.get("secret") else (current or "(not set)")

        typer.echo(f"  {field['label']}")
        typer.echo(f"  {field['hint']}")
        if current:
            typer.echo(f"  Current: {display_current}")

        prompt_text = "  › "
        if field.get("secret"):
            value = typer.prompt(prompt_text, default="", hide_input=True, show_default=False)
        else:
            value = typer.prompt(prompt_text, default=current or "", show_default=bool(current))

        if value:
            updated[key] = value
        elif current:
            updated[key] = current  # keep existing

        typer.echo("")

    _save(updated)

    typer.echo("  ✓ Settings saved to ~/.sds/settings.json")
    typer.echo("")
    typer.echo("  Next steps:")
    typer.echo("    1. Run `uvicorn backend.main:app` and visit /auth/login to")
    typer.echo("       complete Google OAuth (creates token.json).")
    typer.echo("    2. Run `sds index <folder_id>` to index a Drive folder.")
    typer.echo("    3. Run `sds search \"your query\" <folder_id>` to search.")
    typer.echo("")


@app.command()
def setup() -> None:
    """Run the interactive setup wizard to configure API keys and database."""
    typer.echo("")
    typer.echo("  Semantic Drive Search — Setup")
    typer.echo("  ─────────────────────────────────────")
    typer.echo("")
    _run_setup()


# ── Status command ─────────────────────────────────────────────────────────────

def _cmd_status() -> None:
    saved = _load_saved()

    typer.echo("")
    typer.echo("  Semantic Drive Search")
    typer.echo("  ─────────────────────────────────────")
    typer.echo("")

    rows = [
        ("Gemini API Key", _mask(saved.get("GOOGLE_API_KEY", ""))),
        ("OAuth Client ID", saved.get("GOOGLE_CLIENT_ID", "(not set)")),
        ("OAuth Client Secret", _mask(saved.get("GOOGLE_CLIENT_SECRET", ""))),
        ("Database URL", saved.get("DATABASE_URL", "(not set)")),
    ]
    for label, val in rows:
        status = "✓" if val and val != "(not set)" else "✗"
        typer.echo(f"  {status}  {label}: {val}")

    typer.echo("")
    typer.echo("  Commands: search · list-folders · index · get-url · setup")
    typer.echo("  Run `sds --help` for full usage.")
    typer.echo("")


@app.command()
def status() -> None:
    """Show current configuration status."""
    _cmd_status()


# ── Search command ─────────────────────────────────────────────────────────────

@app.command()
def search(
    query: str = typer.Argument(..., help="Natural language description of what you are looking for."),
    folder_id: str = typer.Argument(..., help="Google Drive folder ID (or full URL) that has been indexed."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum number of results to return."),
) -> None:
    """Search indexed Google Drive images and videos using a natural language query."""
    from backend.config import settings
    from backend.vector_store import VectorStore
    from backend import embeddings

    folder_id = _extract_folder_id(folder_id)

    store = VectorStore(database_url=settings.database_url, dimensions=settings.embedding_dimensions)
    query_embedding = embeddings.embed_text_with_retry(query)
    if query_embedding is None:
        typer.echo(json.dumps({"error": "Failed to generate query embedding. Try again shortly."}))
        raise typer.Exit(1)

    raw_results = store.search(folder_id=folder_id, query_embedding=query_embedding, limit=limit)

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


# ── List-folders command ───────────────────────────────────────────────────────

@app.command(name="list-folders")
def list_folders() -> None:
    """List all Google Drive folders that have been indexed for semantic search."""
    from backend.config import settings
    from backend.vector_store import VectorStore

    store = VectorStore(database_url=settings.database_url, dimensions=settings.embedding_dimensions)
    folder_ids = store.list_folders()

    folders = [
        {"folder_id": fid, "file_count": store.get_file_count(fid)}
        for fid in folder_ids
    ]

    typer.echo(json.dumps({"folders": folders}, indent=2))


# ── Index command ──────────────────────────────────────────────────────────────

@app.command()
def index(
    folder_id: str = typer.Argument(..., help="Google Drive folder ID or full folder URL to index."),
) -> None:
    """Index all images and videos in a Google Drive folder for semantic search.

    Already-indexed files are skipped automatically. Supported formats:
    JPEG, PNG, GIF, WebP images and MP4, QuickTime, AVI, WebM videos.
    """
    from backend.config import settings
    from backend.vector_store import VectorStore
    from backend import embeddings, auth, drive

    folder_id = _extract_folder_id(folder_id)
    store = VectorStore(database_url=settings.database_url, dimensions=settings.embedding_dimensions)

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


# ── Organize command ──────────────────────────────────────────────────────────

@app.command()
def organize(
    folder_id: str = typer.Argument(..., help="Google Drive folder ID or URL to organize."),
    mode: str = typer.Option("semantic", "--mode", "-m", help="Organization strategy: 'date' or 'semantic'."),
    clusters: int = typer.Option(10, "--clusters", "-k", help="Number of clusters (semantic mode only)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview the proposed organization without moving any files."),
) -> None:
    """Organize a Drive folder using unsupervised learning.

    \b
    Modes:
      date      Group files into 'YYYY - Month' subfolders using Drive upload date.
      semantic  Cluster the embedding space with k-means, name each cluster with
                Gemini vision, then move files into the named subfolders.

    \b
    Examples:
      sds organize FOLDER_ID --mode date --dry-run
      sds organize FOLDER_ID --mode semantic --clusters 8
      sds organize FOLDER_ID --mode semantic --dry-run
    """
    from backend import auth, organizer

    folder_id = _extract_folder_id(folder_id)

    if mode not in ("date", "semantic"):
        typer.echo(json.dumps({"error": "Invalid mode. Choose 'date' or 'semantic'."}))
        raise typer.Exit(1)

    creds = auth.get_credentials()
    if creds is None:
        typer.echo(json.dumps({
            "error": "Not authenticated with Google Drive. "
                     "Run the web app and complete OAuth login to create token.json."
        }))
        raise typer.Exit(1)

    if mode == "date":
        result = organizer.organize_by_date(creds, folder_id, dry_run=dry_run)
    else:
        result = organizer.organize_semantic(creds, folder_id, k=clusters, dry_run=dry_run)

    typer.echo(json.dumps(result, indent=2))


# ── Get-url command ────────────────────────────────────────────────────────────

@app.command(name="get-url")
def get_url(
    file_id: str = typer.Argument(..., help="The Google Drive file ID."),
) -> None:
    """Get the Google Drive viewing URL for a file."""
    typer.echo(DRIVE_FILE_URL.format(file_id=file_id))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_folder_id(folder_input: str) -> str:
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", folder_input)
    if match:
        return match.group(1)
    return folder_input.strip()


if __name__ == "__main__":
    app()
