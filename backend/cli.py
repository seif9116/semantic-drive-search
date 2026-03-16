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
import sys
import time
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt
from rich import box

DRIVE_FILE_URL = "https://drive.google.com/file/d/{file_id}/view"
SDS_DIR = Path.home() / ".sds"
SDS_SETTINGS = SDS_DIR / "settings.json"

console = Console()

# ── Branding ─────────────────────────────────────────────────────────────────

LOGO = r"""[bold cyan]
    ██████  ██████   ██████
   ██       ██   ██ ██
    █████   ██   ██  █████
        ██  ██   ██      ██
   ██████   ██████  ██████[/]"""

TAGLINE = "[dim]Semantic Drive Search — find any image with words[/]"

OAUTH_GUIDE = """
[bold]To get OAuth credentials, follow these steps:[/]

  [bold cyan]1.[/] Open Google Cloud Console:
     [link=https://console.cloud.google.com/apis/credentials]https://console.cloud.google.com/apis/credentials[/link]

  [bold cyan]2.[/] Click [bold]"+ CREATE CREDENTIALS"[/] → [bold]"OAuth client ID"[/]

  [bold cyan]3.[/] If prompted, configure the consent screen first:
     • User Type: [bold]External[/]
     • App name: anything (e.g. "SDS")
     • Add your email as a test user

  [bold cyan]4.[/] Create OAuth Client ID:
     • Application type: [bold]Web application[/]
     • Authorized redirect URIs: add [bold cyan]http://localhost:8000/auth/callback[/]

  [bold cyan]5.[/] Copy the [bold]Client ID[/] and [bold]Client Secret[/] shown

  [bold cyan]6.[/] Make sure the [bold]Google Drive API[/] is enabled:
     [link=https://console.cloud.google.com/apis/library/drive.googleapis.com]https://console.cloud.google.com/apis/library/drive.googleapis.com[/link]
"""


# ── Setup helpers ─────────────────────────────────────────────────────────────

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
        return "[dim](not set)[/]"
    if len(value) <= 8:
        return "[dim]" + "*" * len(value) + "[/]"
    return value[:4] + "[dim]" + "*" * (len(value) - 8) + "[/]" + value[-4:]


def _prompt_field(label: str, hint: str, current: str = "", secret: bool = False, required: bool = True) -> str:
    """Prompt for a single field with nice formatting."""
    console.print()
    console.print(f"  [bold]{label}[/]")
    console.print(f"  [dim]{hint}[/]")
    if current:
        display = _mask(current) if secret else f"[cyan]{current}[/]"
        console.print(f"  Current: {display}")

    while True:
        if secret:
            value = Prompt.ask("  [bold cyan]›[/]", password=True, default="", console=console, show_default=False)
        else:
            value = Prompt.ask("  [bold cyan]›[/]", default=current or "", console=console, show_default=False)

        value = value.strip()
        if value or current or not required:
            return value if value else current
        console.print("  [red]This field is required.[/]")


def _check_connection(label: str, check_fn) -> bool:
    """Run a check and display pass/fail."""
    try:
        check_fn()
        console.print(f"  [green]✓[/] {label}")
        return True
    except Exception as e:
        console.print(f"  [red]✗[/] {label} — [dim]{e}[/]")
        return False


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
        _run_welcome()


# ── Setup command ─────────────────────────────────────────────────────────────

def _run_welcome() -> None:
    console.print()
    console.print(LOGO)
    console.print()
    console.print(f"  {TAGLINE}")
    console.print()
    console.print(Panel(
        "[bold]First time? Let's get you set up in 3 steps.[/]\n\n"
        "  [bold cyan]Step 1[/]  Gemini API key [dim](for image embeddings)[/]\n"
        "  [bold cyan]Step 2[/]  Google OAuth   [dim](for Drive access)[/]\n"
        "  [bold cyan]Step 3[/]  PostgreSQL     [dim](for vector storage)[/]\n\n"
        "[dim]Press Enter to keep existing values. Ctrl+C to quit.[/]",
        title="[bold] Setup [/]",
        border_style="cyan",
        padding=(1, 2),
    ))
    _run_setup()


def _run_setup() -> None:
    saved = _load_saved()
    updated: dict = dict(saved)

    # ── Step 1: Gemini API Key ────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]Get your free API key from Google AI Studio.[/]\n\n"
        "  [link=https://aistudio.google.com/apikey]https://aistudio.google.com/apikey[/link]",
        title="[bold cyan] Step 1 · Gemini API Key [/]",
        border_style="cyan",
        padding=(1, 2),
    ))

    val = _prompt_field(
        "API Key",
        "Paste your Gemini API key",
        current=saved.get("GOOGLE_API_KEY", ""),
        secret=True,
    )
    if val:
        updated["GOOGLE_API_KEY"] = val

    # ── Step 2: Google OAuth ──────────────────────────────────────────────
    console.print()
    console.print(Panel(
        OAUTH_GUIDE.strip(),
        title="[bold cyan] Step 2 · Google OAuth Credentials [/]",
        border_style="cyan",
        padding=(1, 2),
    ))

    open_console = Prompt.ask(
        "  [bold cyan]Open Cloud Console in browser?[/] [dim](Y/n)[/]",
        default="y",
        console=console,
        show_default=False,
    )
    if open_console.lower() in ("y", "yes", ""):
        webbrowser.open("https://console.cloud.google.com/apis/credentials")
        console.print("  [dim]Opened in browser. Create credentials and come back here.[/]")

    val = _prompt_field(
        "OAuth Client ID",
        "Looks like: 123456789-abc.apps.googleusercontent.com",
        current=saved.get("GOOGLE_CLIENT_ID", ""),
        secret=False,
    )
    if val:
        updated["GOOGLE_CLIENT_ID"] = val

    val = _prompt_field(
        "OAuth Client Secret",
        "Shown alongside the Client ID",
        current=saved.get("GOOGLE_CLIENT_SECRET", ""),
        secret=True,
    )
    if val:
        updated["GOOGLE_CLIENT_SECRET"] = val

    # ── Step 3: PostgreSQL ────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold]You need PostgreSQL with the pgvector extension.[/]\n\n"
        "  [bold]Install pgvector:[/]\n"
        "    [dim]Ubuntu:[/]  sudo apt install postgresql-16-pgvector\n"
        "    [dim]Mac:[/]     brew install pgvector\n\n"
        "  [bold]Create the database:[/]\n"
        "    createdb semantic_search",
        title="[bold cyan] Step 3 · PostgreSQL + pgvector [/]",
        border_style="cyan",
        padding=(1, 2),
    ))

    val = _prompt_field(
        "Database URL",
        "e.g. postgresql://user:pass@localhost:5432/semantic_search",
        current=saved.get("DATABASE_URL", "postgresql://localhost:5432/semantic_search"),
        secret=False,
    )
    if val:
        updated["DATABASE_URL"] = val

    # ── Save ──────────────────────────────────────────────────────────────
    _save(updated)
    console.print()
    console.print(f"  [green]✓[/] Settings saved to [bold]~/.sds/settings.json[/]")

    # ── Verify connections ────────────────────────────────────────────────
    console.print()
    console.print("  [bold]Checking connections...[/]")
    console.print()

    db_ok = _check_connection("PostgreSQL", lambda: _test_db(updated.get("DATABASE_URL", "")))
    api_ok = _check_connection("Gemini API", lambda: _test_gemini(updated.get("GOOGLE_API_KEY", "")))

    # Check OAuth token
    token_path = Path("token.json")
    has_token = token_path.exists()
    if has_token:
        console.print(f"  [green]✓[/] Google Drive token found")
    else:
        console.print(f"  [yellow]![/] Google Drive — needs OAuth login [dim](one-time)[/]")

    # ── Next steps ────────────────────────────────────────────────────────
    console.print()

    if not has_token:
        console.print(Panel(
            "[bold]Complete Google Drive authorization:[/]\n\n"
            "  [bold cyan]1.[/] Start the web server:\n"
            "     [bold]sds auth[/]\n\n"
            "  [bold cyan]2.[/] It will open your browser automatically.\n"
            "     Sign in and allow access to your Drive.\n\n"
            "  [bold cyan]3.[/] After authorization, you can close the server.\n\n"
            "[dim]This creates a token.json file for offline access.\n"
            "You only need to do this once.[/]",
            title="[bold yellow] Action Required [/]",
            border_style="yellow",
            padding=(1, 2),
        ))
    else:
        console.print(Panel(
            "[bold]You're all set! Try these:[/]\n\n"
            "  [bold cyan]sds index[/] [dim]<folder_url>[/]      Index a Drive folder\n"
            "  [bold cyan]sds search[/] [dim]\"query\" <id>[/]     Search your images\n"
            "  [bold cyan]sds list-folders[/]              See indexed folders\n"
            "  [bold cyan]sds status[/]                    Check configuration",
            title="[bold green] Ready [/]",
            border_style="green",
            padding=(1, 2),
        ))
    console.print()


def _test_db(url: str) -> None:
    import psycopg
    with psycopg.connect(url, connect_timeout=5) as conn:
        conn.execute("SELECT 1")


def _test_gemini(api_key: str) -> None:
    if not api_key:
        raise ValueError("No API key")
    from google import genai
    client = genai.Client(api_key=api_key)
    client.models.list()


@app.command()
def setup() -> None:
    """Run the interactive setup wizard to configure API keys and database."""
    console.print()
    console.print(LOGO)
    console.print()
    console.print(f"  {TAGLINE}")
    console.print()
    _run_setup()


# ── Auth command ──────────────────────────────────────────────────────────────

@app.command()
def auth() -> None:
    """Launch a temporary server to complete Google Drive OAuth login."""
    import threading
    from backend.config import settings

    if not settings.google_client_id or not settings.google_client_secret:
        console.print()
        console.print("  [red]✗[/] OAuth credentials not configured. Run [bold]sds setup[/] first.")
        console.print()
        raise typer.Exit(1)

    console.print()
    console.print("  [bold]Starting OAuth server...[/]")
    console.print()
    console.print("  [cyan]→[/] Opening [link=http://localhost:8000/auth/login]http://localhost:8000/auth/login[/link] in your browser")
    console.print("  [dim]  Sign in and allow Drive access. This window will close automatically.[/]")
    console.print()

    # Open browser after a short delay
    def _open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000/auth/login")

    threading.Thread(target=_open_browser, daemon=True).start()

    # Run the server — it will serve the OAuth callback
    import uvicorn
    from backend.main import app as fastapi_app

    # Monkey-patch the callback to stop the server after auth
    from backend.main import auth_callback as _original_callback
    from backend import auth as auth_module

    class _ShutdownAfterAuth(Exception):
        pass

    _got_token = threading.Event()

    original_exchange = auth_module.exchange_code

    def _patched_exchange(code):
        result = original_exchange(code)
        _got_token.set()
        return result

    auth_module.exchange_code = _patched_exchange

    def _watch_for_token():
        _got_token.wait()
        time.sleep(1)
        console.print()
        console.print("  [green]✓[/] Google Drive authorized successfully!")
        console.print("  [dim]  Token saved. You can now close this server (Ctrl+C).[/]")
        console.print()
        import os
        os._exit(0)

    threading.Thread(target=_watch_for_token, daemon=True).start()

    try:
        uvicorn.run(fastapi_app, host="127.0.0.1", port=8000, log_level="error")
    except KeyboardInterrupt:
        pass


# ── Status command ─────────────────────────────────────────────────────────────

def _cmd_status() -> None:
    saved = _load_saved()

    console.print()
    console.print(LOGO)
    console.print()
    console.print(f"  {TAGLINE}")
    console.print()

    table = Table(
        show_header=False,
        box=box.SIMPLE,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("Status", style="bold", width=3)
    table.add_column("Setting", style="bold", min_width=20)
    table.add_column("Value")

    checks = [
        ("GOOGLE_API_KEY", "Gemini API Key", True),
        ("GOOGLE_CLIENT_ID", "OAuth Client ID", False),
        ("GOOGLE_CLIENT_SECRET", "OAuth Client Secret", True),
        ("DATABASE_URL", "Database URL", False),
    ]

    for key, label, secret in checks:
        val = saved.get(key, "")
        icon = "[green]✓[/]" if val else "[red]✗[/]"
        display = _mask(val) if secret else (f"[cyan]{val}[/]" if val else "[dim](not set)[/]")
        table.add_row(icon, label, display)

    # Check token
    token_path = Path("token.json")
    has_token = token_path.exists()
    icon = "[green]✓[/]" if has_token else "[yellow]![/]"
    token_display = "[green]authorized[/]" if has_token else "[yellow]run `sds auth`[/]"
    table.add_row(icon, "Google Drive", token_display)

    console.print(Panel(table, title="[bold] Configuration [/]", border_style="cyan", padding=(1, 0)))

    console.print()
    console.print("  [bold]Commands[/]")
    console.print("  [cyan]search[/] · [cyan]index[/] · [cyan]list-folders[/] · [cyan]get-url[/] · [cyan]organize[/] · [cyan]setup[/] · [cyan]auth[/]")
    console.print("  [dim]Run `sds --help` for full usage.[/]")
    console.print()


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
    from backend import embeddings, auth as auth_module, drive

    folder_id = _extract_folder_id(folder_id)
    store = VectorStore(database_url=settings.database_url, dimensions=settings.embedding_dimensions)

    creds = auth_module.get_credentials()
    if creds is None:
        typer.echo(json.dumps({
            "error": "Not authenticated with Google Drive. "
                     "Run `sds auth` to complete OAuth login."
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
    from backend import auth as auth_module, organizer

    folder_id = _extract_folder_id(folder_id)

    if mode not in ("date", "semantic"):
        typer.echo(json.dumps({"error": "Invalid mode. Choose 'date' or 'semantic'."}))
        raise typer.Exit(1)

    creds = auth_module.get_credentials()
    if creds is None:
        typer.echo(json.dumps({
            "error": "Not authenticated with Google Drive. "
                     "Run `sds auth` to complete OAuth login."
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
