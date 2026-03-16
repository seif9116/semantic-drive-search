---
name: search-images
description: Search indexed Google Drive images and videos using natural language. Use when the user needs to find images matching a description (e.g. "sunset over mountains", "team photo", "product screenshot").
---

# Search Drive Images

Search indexed Google Drive images/videos using semantic similarity. Results are ranked by how closely they match your description.

## Usage

Run via Bash:

```bash
sds search "<natural language query>" "<folder_id>" --limit <N>
```

If `sds` is not installed, use:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/cli.py search "<query>" "<folder_id>" --limit <N>
```

## Arguments

- `query` (required): Natural language description of what you're looking for
- `folder_id` (required): Google Drive folder ID or full folder URL that has been indexed
- `--limit` (optional, default 10): Max results to return

## Output

JSON with ranked results:

```json
{
  "query": "sunset over mountains",
  "folder_id": "abc123",
  "results": [
    {
      "file_id": "1xYz...",
      "name": "IMG_4521.jpg",
      "mime_type": "image/jpeg",
      "similarity": 0.87,
      "drive_url": "https://drive.google.com/file/d/1xYz.../view"
    }
  ]
}
```

## Tips

- Be descriptive: "golden retriever playing fetch on a beach" works better than "dog"
- Similarity scores above 0.5 are usually good matches
- Run `list-folders` first to find which folder IDs are available

## Examples

```bash
# Finding images for a landing page
sds search "modern office workspace with plants" "1aBcDeFg"

# Looking for product screenshots
sds search "mobile app dark mode dashboard" "1aBcDeFg" --limit 5

# Finding event photos
sds search "group photo at conference" "1aBcDeFg"
```
