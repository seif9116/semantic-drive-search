---
name: index-folder
description: Index all images and videos in a Google Drive folder for semantic search. Use when a folder hasn't been indexed yet or needs re-indexing.
disable-model-invocation: true
---

# Index a Google Drive Folder

Downloads all images/videos from a Drive folder, generates Gemini embeddings, and stores them in the vector database. Already-indexed files are automatically skipped.

## Usage

```bash
sds index "<folder_id_or_url>"
```

Install with `pip install semantic-drive-search` if `sds` is not available.

## Arguments

- `folder_id` (required): Google Drive folder ID or full folder URL

## Prerequisites

- Google OAuth must be completed first (run the web app and log in once)
- PostgreSQL with pgvector must be running

## Output

JSON summary:

```json
{
  "folder_id": "abc123",
  "total_files_found": 42,
  "newly_indexed": 38,
  "skipped_already_indexed": 4,
  "failed": 0
}
```

## Notes

- Can take a while for large folders (0.5s delay between files for rate limiting)
- Supported: JPEG, PNG, GIF, WebP (up to 20MB), MP4, QuickTime, AVI, WebM (up to 100MB)
- Recursively indexes subfolders
