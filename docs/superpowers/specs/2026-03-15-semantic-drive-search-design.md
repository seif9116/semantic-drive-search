# Semantic Drive Search - Design Spec

## Problem

When building websites, you often need to find the right image or video from a large Google Drive folder. Manually browsing hundreds of files is slow. This app lets you describe what you're looking for in natural language and returns the most semantically similar media from your Drive folder.

## Solution

A web application that:
1. Connects to a Google Drive folder via OAuth2
2. Indexes all images/videos using Gemini Embedding 2 (`gemini-embedding-2-preview`)
3. Stores embeddings in ChromaDB for fast retrieval
4. Provides a search UI where you type a text query and get matching images/videos ranked by similarity
5. Exposes an API endpoint so Claude (or any tool) can programmatically search

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐
│   Browser    │────▶│           FastAPI Backend             │
│  (Search UI) │◀────│                                      │
└─────────────┘     │  ┌────────┐ ┌──────────┐ ┌────────┐ │
                    │  │ Drive  │ │ Gemini   │ │ChromaDB│ │
                    │  │ Client │ │ Embed 2  │ │ Vector │ │
                    │  └────────┘ └──────────┘ └────────┘ │
                    └──────────────────────────────────────┘
                         │              │            │
                    Google Drive   Gemini API    Local Storage
                      API v3
```

## Tech Stack

- **Backend:** FastAPI (Python 3.12+)
- **Embeddings:** Gemini Embedding 2 (`gemini-embedding-2-preview`) via `google-genai` SDK
- **Vector Store:** ChromaDB (persistent local storage)
- **Drive Integration:** Google Drive API v3 via `google-api-python-client`
- **Auth:** OAuth2 for Google Drive, API key for Gemini
- **Frontend:** Vanilla HTML/CSS/JS with Tailwind CSS (served by FastAPI)
- **Image Proxy:** Backend proxies Drive images to avoid CORS/auth issues in browser

## Data Flow

### Indexing Flow
1. User provides Google Drive folder ID (from URL)
2. Backend authenticates via OAuth2, lists all image/video files in folder (recursive)
3. For each file:
   - Download to temp storage
   - Generate embedding via Gemini Embedding 2
   - Store embedding + metadata (file ID, name, mime type, thumbnail link) in ChromaDB
4. Track indexing progress via SSE (Server-Sent Events)

### Search Flow
1. User types text query (e.g., "sunset over mountains")
2. Backend generates text embedding via Gemini Embedding 2 (same model, same vector space)
3. ChromaDB cosine similarity search returns top-K results
4. Backend returns results with metadata + proxied thumbnail URLs
5. Frontend displays results as a responsive grid

## API Endpoints

### Auth
- `GET /auth/login` - Redirect to Google OAuth2 consent screen
- `GET /auth/callback` - OAuth2 callback, stores tokens in session
- `GET /auth/status` - Check if user is authenticated

### Indexing
- `POST /api/index` - Start indexing a folder `{ folder_id: string }`
- `GET /api/index/status` - SSE stream of indexing progress
- `GET /api/folders` - List indexed folders

### Search
- `GET /api/search?q={query}&limit={n}&folder_id={id}` - Semantic search
- Response: `{ results: [{ file_id, name, mime_type, similarity, thumbnail_url }] }`

### Media
- `GET /api/media/{file_id}` - Proxy file content from Drive
- `GET /api/media/{file_id}/thumbnail` - Proxy thumbnail

## Embedding Strategy

- **Model:** `gemini-embedding-2-preview`
- **Dimensions:** 768 (Matryoshka truncation for storage efficiency, still high quality)
- **Images:** Embed raw image bytes directly
- **Videos:** Use Gemini Files API to upload, then embed (supports native video)
- **Text queries:** Embed with same model for unified vector space
- **Batch size:** Up to 6 images per embed request (API limit)

## ChromaDB Schema

- **Collection per folder:** `folder_{folder_id}`
- **Document ID:** Google Drive file ID
- **Embedding:** 768-dim float vector
- **Metadata:**
  - `name`: filename
  - `mime_type`: file MIME type
  - `drive_id`: Google Drive file ID
  - `folder_id`: parent folder ID
  - `created_time`: file creation time
  - `size`: file size in bytes
  - `thumbnail_link`: Drive thumbnail URL (if available)

## Authentication

### Google Drive (OAuth2)
- User clicks "Connect Google Drive" in the UI
- Redirected to Google consent screen (scope: `drive.readonly`)
- Tokens stored server-side in encrypted session
- Refresh tokens used for long-lived access

### Gemini API
- API key stored in `.env` file as `GOOGLE_API_KEY`
- Passed to `google-genai` client

## Error Handling

- Rate limiting: Exponential backoff on Gemini API 429s
- Large files: Skip files > 20MB for images, > 100MB for videos
- Unsupported formats: Log and skip, report in indexing status
- Auth expiry: Auto-refresh OAuth tokens, redirect to re-auth if refresh fails

## Security

- OAuth tokens encrypted at rest
- No Drive file content stored permanently (only embeddings + metadata)
- CORS restricted to same-origin
- API key never exposed to frontend

## Frontend Design

- Clean, minimal search interface
- Large search bar at top
- Results displayed as responsive image grid
- Click to view full-size image/video
- Folder selector for multi-folder support
- Indexing progress indicator
- Dark/light mode support
