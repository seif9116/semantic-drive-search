---
name: list-folders
description: List all Google Drive folders that have been indexed for semantic search. Use before searching to discover available folder IDs.
---

# List Indexed Folders

Show all Drive folders that have been indexed and are ready for searching.

## Usage

```bash
sds list-folders
```

Install with `pip install semantic-drive-search` if `sds` is not available.

## Output

```json
{
  "folders": [
    { "folder_id": "1aBcDeFg", "file_count": 142 },
    { "folder_id": "2xYzAbCd", "file_count": 37 }
  ]
}
```
