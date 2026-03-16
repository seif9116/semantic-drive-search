---
name: get-image-url
description: Get the Google Drive viewing URL for a file by its ID. Use after search to get shareable links.
---

# Get Image URL

Returns the Google Drive viewing URL for a file.

## Usage

```bash
sds get-url "<file_id>"
```

Or:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/cli.py get-url "<file_id>"
```

## Output

```
https://drive.google.com/file/d/<file_id>/view
```
