# Semantic Drive Search - Claude Skill

## What This Does

Search through indexed Google Drive images and videos using natural language descriptions. When building websites, creating content, or looking for specific media, use this to find relevant images and videos from the user's Drive by describing what you need.

## Setup

Add the MCP server to your Claude configuration. In `.claude/settings.json` or Claude Desktop config:

```json
{
  "mcpServers": {
    "semantic-drive-search": {
      "command": "uv",
      "args": [
        "run",
        "--directory", "/home/seif/university/projects/semantic_images",
        "python3", "mcp_server.py"
      ]
    }
  }
}
```

Alternatively, if you prefer to run it directly with the venv activated:

```json
{
  "mcpServers": {
    "semantic-drive-search": {
      "command": "/home/seif/university/projects/semantic_images/.venv/bin/python3",
      "args": ["/home/seif/university/projects/semantic_images/mcp_server.py"]
    }
  }
}
```

### Prerequisites

- Google OAuth must be completed before use. Run the web app (`uvicorn backend.main:app`) and log in via `/auth/login` at least once to generate `token.json`.
- A PostgreSQL database with pgvector must be running and configured in `.env` via `DATABASE_URL`.
- A valid `GOOGLE_API_KEY` must be set in `.env` for Gemini embeddings.

## Available Tools

### search_images

Search indexed Google Drive media using a natural language description. Returns ranked results with file names, similarity scores, and direct Drive links.

**Parameters:**
- `query` (required): Natural language description of what you are looking for.
- `folder_id` (required): The Google Drive folder ID that has been indexed.
- `limit` (optional, default 10): Maximum number of results to return.

**Examples:**
```
search_images("sunset over mountains", folder_id="1aBcDeFgHiJkLmNoPqRsTuVwXyZ")
search_images("people sitting around a conference table", folder_id="1aBcDeFg", limit=5)
search_images("product screenshot with dark mode UI", folder_id="1aBcDeFg")
```

**Returns:** JSON with a list of results, each containing `file_id`, `name`, `mime_type`, `similarity`, and `drive_url`.

### list_indexed_folders

List all Google Drive folders that have been previously indexed. Use this first to discover which folders are available for searching.

**Parameters:** None.

**Returns:** JSON with a list of folders, each containing `folder_id` and `file_count`.

### index_folder

Index all images and videos in a Google Drive folder (including subfolders). Downloads each file, generates a Gemini embedding, and stores it in the vector database. Already-indexed files are automatically skipped.

**Parameters:**
- `folder_id` (required): Google Drive folder ID or full folder URL.

**Note:** This can take a while for large folders. Supported formats: JPEG, PNG, GIF, WebP, MP4, QuickTime, AVI, WebM.

**Returns:** JSON summary with counts of files indexed, skipped, and failed.

### get_image_url

Get the Google Drive viewing URL for a file by its ID.

**Parameters:**
- `file_id` (required): The Google Drive file ID.

**Returns:** A URL string like `https://drive.google.com/file/d/{file_id}/view`.

## Workflow

1. Call `list_indexed_folders` to see what folders are already available.
2. If the folder you need is not indexed yet, call `index_folder` with the folder ID or URL.
3. Use `search_images` with a natural language description to find relevant media.
4. Use `get_image_url` to get shareable links for specific files.

## Example Usage

When building a landing page about outdoor adventures:

```
search_images("mountain hiking trail sunset", folder_id="abc123")
search_images("camping tent in a forest clearing", folder_id="abc123")
search_images("kayaking on a lake", folder_id="abc123", limit=5)
```

When looking for product screenshots:

```
search_images("mobile app login screen", folder_id="def456")
search_images("dashboard with analytics charts", folder_id="def456")
```

When searching for specific people or events:

```
search_images("group photo at the company offsite", folder_id="ghi789")
search_images("presentation slides on stage", folder_id="ghi789")
```

## Tips

- Be descriptive in your queries. "Golden retriever playing fetch on a beach" works better than "dog".
- The search is semantic, not keyword-based. You do not need exact filenames.
- Results include a similarity score from 0 to 1. Scores above 0.5 are usually good matches.
- You can pass a full Google Drive folder URL instead of just the folder ID.
