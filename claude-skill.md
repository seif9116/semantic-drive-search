# Semantic Drive Search - Claude Skill

## What This Does

Search through indexed Google Drive images and videos using natural language descriptions. When building websites, creating content, or looking for specific media, use this to find relevant images and videos from the user's Drive by describing what you need.

All commands output JSON and are called via Bash.

## Setup

Install the CLI globally:

```bash
pip install semantic-drive-search
```

### Prerequisites

- Google OAuth must be completed before use. Run the web app (`uvicorn backend.main:app`) and log in via `/auth/login` at least once to generate `token.json`.
- A PostgreSQL database with pgvector must be running and configured in `.env` via `DATABASE_URL`.
- A valid `GOOGLE_API_KEY` must be set in `.env` for Gemini embeddings.

## Available Commands

### search

Search indexed Google Drive media using a natural language description. Returns ranked results with file names, similarity scores, and direct Drive links.

**Usage:**
```bash
sds search "<query>" "<folder_id>" [--limit N]
```

**Arguments:**
- `query` (required): Natural language description of what you are looking for.
- `folder_id` (required): The Google Drive folder ID that has been indexed. Accepts a full Drive URL.
- `--limit` (optional, default 10): Maximum number of results to return.

**Examples:**
```bash
sds search "sunset over mountains" "1aBcDeFgHiJkLmNoPqRsTuVwXyZ"
sds search "people sitting around a conference table" "1aBcDeFg" --limit 5
sds search "product screenshot with dark mode UI" "1aBcDeFg"
```

**Returns:** JSON with a list of results, each containing `file_id`, `name`, `mime_type`, `similarity`, and `drive_url`.

### list-folders

List all Google Drive folders that have been previously indexed. Use this first to discover which folders are available for searching.

**Usage:**
```bash
sds list-folders
```

**Returns:** JSON with a list of folders, each containing `folder_id` and `file_count`.

### index

Index all images and videos in a Google Drive folder (including subfolders). Downloads each file, generates a Gemini embedding, and stores it in the vector database. Already-indexed files are automatically skipped.

**Usage:**
```bash
sds index "<folder_id>"
```

**Arguments:**
- `folder_id` (required): Google Drive folder ID or full folder URL.

**Note:** This can take a while for large folders. Supported formats: JPEG, PNG, GIF, WebP, MP4, QuickTime, AVI, WebM.

**Returns:** JSON summary with counts of files indexed, skipped, and failed.

### get-url

Get the Google Drive viewing URL for a file by its ID.

**Usage:**
```bash
sds get-url "<file_id>"
```

**Arguments:**
- `file_id` (required): The Google Drive file ID.

**Returns:** A URL string like `https://drive.google.com/file/d/{file_id}/view`.

### organize

Organize a Google Drive folder into subfolders automatically.

**Usage:**
```bash
sds organize "<folder_id>" [--mode date|semantic] [--clusters N] [--dry-run]
```

**Arguments:**
- `folder_id` (required): Google Drive folder ID or URL.
- `--mode` (optional, default "semantic"): `date` groups by upload month, `semantic` clusters by visual similarity using k-means.
- `--clusters` (optional, default 10): Number of clusters (semantic mode only).
- `--dry-run` (optional): Preview the proposed organization without moving files.

**Examples:**
```bash
sds organize abc123 --mode date --dry-run
sds organize abc123 --mode semantic --clusters 8
```

**Returns:** JSON with the proposed/executed grouping and file counts per folder.

## Workflow

1. Run `sds list-folders` to see what folders are already available.
2. If the folder you need is not indexed yet, run `sds index <folder_id>`.
3. Use `sds search "<description>" <folder_id>` to find relevant media.
4. Use `sds get-url <file_id>` to get shareable links for specific files.

## Example Usage

When building a landing page about outdoor adventures:

```bash
sds search "mountain hiking trail sunset" abc123
sds search "camping tent in a forest clearing" abc123
sds search "kayaking on a lake" abc123 --limit 5
```

When looking for product screenshots:

```bash
sds search "mobile app login screen" def456
sds search "dashboard with analytics charts" def456
```

When searching for specific people or events:

```bash
sds search "group photo at the company offsite" ghi789
sds search "presentation slides on stage" ghi789
```

## Tips

- Be descriptive in your queries. "Golden retriever playing fetch on a beach" works better than "dog".
- The search is semantic, not keyword-based. You do not need exact filenames.
- Results include a similarity score from 0 to 1. Scores above 0.5 are usually good matches.
- You can pass a full Google Drive folder URL instead of just the folder ID.
