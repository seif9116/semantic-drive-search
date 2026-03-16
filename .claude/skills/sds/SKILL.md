---
name: sds
description: Semantic Drive Search — use this skill whenever the user wants to search Google Drive images or videos with natural language, index a Drive folder, browse Drive contents, find a specific photo, or set up the SDS MCP server. Also use when the user mentions finding images, searching photos, "find that picture of...", organizing Drive media, or anything related to semantic/visual search of Google Drive files.
user-invocable: true
argument-hint: [search query, folder URL, or "setup"]
---

# Semantic Drive Search

You have access to an MCP server called `semantic-drive-search` that lets you search, index, and browse Google Drive images and videos using natural language. Use the MCP tools directly — don't shell out to the CLI unless the MCP server is unavailable.

## Quick reference

| Task | MCP tool | Example |
|------|----------|---------|
| Search images by description | `search_images` | "sunset photos", "whiteboard diagram" |
| Index a Drive folder | `index_folder` | Pass a folder URL or ID |
| Browse folder contents | `browse_drive` | See what's in a folder before indexing |
| List indexed folders | `list_indexed_folders` | Check what's already indexed |
| Get viewable URL for a file | `get_image_url` | Turn a file_id into a Drive link |

## How to handle user requests

**"Find/search for [description]"** — The most common request. Steps:
1. Call `list_indexed_folders` to find available folders
2. If only one folder exists, use it. If multiple, ask which one (or search all)
3. Call `search_images` once with the user's description as the query. One search is enough — do not run multiple rephrased queries
4. Present results with names, similarity scores, and Drive URLs (via `get_image_url`)
5. If the user says "show me" or "open it", provide the Drive URL

**"Index [folder URL/ID]"** — User wants to index a new folder:
1. Call `index_folder` with the folder URL or ID
2. Report the results: how many files were indexed, skipped, or failed
3. If there are errors, explain them (common: rate limits, auth issues, empty files)

**"What's indexed?" / "What do I have?"** — Status check on indexed folders:
1. Call `list_indexed_folders` — this returns folder IDs and file counts
2. Report the folder IDs and how many files are in each
3. Do NOT call `browse_drive` or list individual files — the user is asking for a summary, not a full file listing. Only enumerate files if they explicitly ask "list all files" or "show me every file"

**"Browse [folder]"** or "What's in this folder?" — Preview without indexing:
1. Call `browse_drive` with the folder URL or ID
2. Summarize: total files, breakdown by type (images vs videos), notable file names

**"Set up" / "How do I get started?"** — Help with initial setup:
1. Check if the MCP server is connected (try `list_indexed_folders`)
2. If not connected, explain the setup:
   - Run `sds setup` in the terminal to configure API keys and database
   - The `.mcp.json` in the repo auto-registers the MCP server
   - After setup, restart Claude Code to pick up the MCP connection
3. If connected but no folders indexed, suggest indexing one

**Natural language that implies search** — Users often say things like:
- "find that picture of the whiteboard from last week"
- "do I have any sunset photos?"
- "where's the screenshot of the error message?"

Treat these as search queries. Extract the descriptive part and use `search_images`.

## Presenting results

When showing search results:
- Include the file name, similarity percentage, and a clickable Drive URL
- Sort by similarity (they come pre-sorted, just preserve order)
- If similarity is below 50%, mention that the matches are weak
- For multiple results, use a clean numbered list

Example output format:
```
Found 3 matches:

1. **sunset_beach.jpg** (87% match) — [View in Drive](https://drive.google.com/file/d/abc123/view)
2. **evening_sky.png** (74% match) — [View in Drive](https://drive.google.com/file/d/def456/view)
3. **golden_hour.jpg** (61% match) — [View in Drive](https://drive.google.com/file/d/ghi789/view)
```

## Fallback: CLI

If the MCP server is not connected, fall back to the CLI. Always activate the venv first:

```bash
source .venv/bin/activate
```

### Core commands

| Command | Description | Example |
|---------|-------------|---------|
| `sds search "query" FOLDER_ID` | Search indexed images by description | `sds search "sunset" 15kjK...` |
| `sds index FOLDER_URL` | Index all media in a Drive folder | `sds index https://drive.google.com/drive/folders/abc` |
| `sds browse FOLDER_ID` | List files in a folder without indexing | `sds browse 15kjK... --type images` |
| `sds list-folders` | Show all indexed folders | `sds list-folders` |
| `sds get-url FILE_ID` | Get a Drive viewing URL for a file | `sds get-url 1abc...` |

### Setup & auth commands

| Command | Description | When to use |
|---------|-------------|-------------|
| `sds setup` | Interactive wizard — configures Gemini API key, OAuth credentials, PostgreSQL | First-time setup or reconfiguring |
| `sds auth` | Launch OAuth flow to authorize Google Drive access | When token is missing or expired |
| `sds status` | Show current config: API key, OAuth, database, token status | Diagnosing connection issues |

### Organization commands

| Command | Description | Example |
|---------|-------------|---------|
| `sds organize FOLDER_ID --mode date` | Organize files into YYYY-Month subfolders | `sds organize abc --mode date --dry-run` |
| `sds organize FOLDER_ID --mode semantic` | Cluster by visual similarity, name folders with Gemini | `sds organize abc --mode semantic -k 8` |

The `--dry-run` flag previews changes without moving files. Use it first.

### CLI options

- `sds search` accepts `--limit N` (default 10)
- `sds browse` accepts `--type all|images|videos` (default all)
- `sds organize` accepts `--clusters N` (default 10, semantic mode only)
- All commands accept folder URLs or raw IDs — URLs are auto-extracted

### Web app

Running `sds` with no arguments launches the web UI at `http://localhost:8000` with a browser-based search interface. Use this when the user wants a visual experience rather than CLI output.

## Common issues

- **"Not authenticated"** — Run `sds auth` to complete OAuth login
- **"Database not connected"** — Check that PostgreSQL is running and `DATABASE_URL` is set
- **"Failed to generate embedding"** — Usually a network issue; retry shortly
- **Empty results** — The folder may not be indexed yet; suggest running `index_folder`
