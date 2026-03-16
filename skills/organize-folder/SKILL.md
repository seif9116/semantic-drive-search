---
name: organize-folder
description: Organize a Google Drive folder into subfolders by date or semantic similarity. Use when a folder is messy and needs automatic organization.
disable-model-invocation: true
---

# Organize a Drive Folder

Automatically group files in a Drive folder into subfolders using either date-based or semantic clustering.

## Usage

```bash
# By date — groups into "YYYY - Month" subfolders
sds organize "<folder_id>" --mode date

# By semantic similarity — k-means clustering with Gemini-named folders
sds organize "<folder_id>" --mode semantic --clusters 8

# Preview without moving files
sds organize "<folder_id>" --mode semantic --dry-run
```

Install with `pip install semantic-drive-search` if `sds` is not available.

## Arguments

- `folder_id` (required): Google Drive folder ID or URL
- `--mode` (optional, default "semantic"): `date` or `semantic`
- `--clusters` (optional, default 10): Number of clusters (semantic mode only)
- `--dry-run` (optional): Preview without moving files

## Prerequisites

- For semantic mode: the folder must be indexed first (`sds index <folder_id>`)
- Google OAuth must be completed

## Output

JSON with the proposed or executed grouping:

```json
{
  "folder_id": "abc123",
  "mode": "semantic",
  "dry_run": true,
  "k": 8,
  "total_files": 142,
  "clusters": [
    { "name": "beach_sunsets", "file_count": 23, "files": ["IMG_001.jpg", ...] },
    { "name": "product_screenshots", "file_count": 18, "files": [...] }
  ]
}
```
