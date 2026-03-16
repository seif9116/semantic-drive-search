import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from backend.config import settings

# Shared Drive params — required for Google Workspace accounts
_SHARED = {"supportsAllDrives": True, "includeItemsFromAllDrives": True}


def get_drive_service(creds: Credentials):
    return build("drive", "v3", credentials=creds)


def list_media_files(creds: Credentials, folder_id: str) -> list[dict]:
    """List all image and video files in a Drive folder (recursive)."""
    service = get_drive_service(creds)
    all_files = []

    # Build mime type query
    image_types = settings.supported_image_types
    video_types = settings.supported_video_types
    mime_queries = [f"mimeType='{mt}'" for mt in image_types + video_types]
    mime_filter = " or ".join(mime_queries)

    query = f"'{folder_id}' in parents and ({mime_filter}) and trashed=false"

    page_token = None
    while True:
        response = service.files().list(
            q=query,
            spaces="drive",
            corpora="allDrives",
            fields="nextPageToken, files(id, name, mimeType, size, createdTime, thumbnailLink)",
            pageToken=page_token,
            pageSize=100,
            **_SHARED,
        ).execute()

        files = response.get("files", [])
        for f in files:
            size = int(f.get("size", 0))
            mime = f.get("mimeType", "")

            # Skip files that are too large
            if mime in image_types and size > settings.max_image_size:
                continue
            if mime in video_types and size > settings.max_video_size:
                continue

            all_files.append({
                "id": f["id"],
                "name": f["name"],
                "mimeType": mime,
                "size": size,
                "createdTime": f.get("createdTime", ""),
                "thumbnailLink": f.get("thumbnailLink", ""),
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    # Also recurse into subfolders
    subfolder_query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    page_token = None
    while True:
        response = service.files().list(
            q=subfolder_query,
            spaces="drive",
            corpora="allDrives",
            fields="nextPageToken, files(id)",
            pageToken=page_token,
            pageSize=100,
            **_SHARED,
        ).execute()

        for subfolder in response.get("files", []):
            all_files.extend(list_media_files(creds, subfolder["id"]))

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_files


def download_file(creds: Credentials, file_id: str) -> bytes:
    """Download a file's content from Drive."""
    service = get_drive_service(creds)
    request = service.files().get_media(fileId=file_id, **_SHARED)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return buffer.getvalue()


def create_folder(creds: Credentials, name: str, parent_id: str) -> str:
    """Create a subfolder inside parent_id and return its new folder ID."""
    service = get_drive_service(creds)
    folder = service.files().create(
        body={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
        fields="id",
        **_SHARED,
    ).execute()
    return folder["id"]


def get_file_parents(creds: Credentials, file_id: str) -> list[str]:
    """Return the parent folder IDs for a file."""
    service = get_drive_service(creds)
    f = service.files().get(fileId=file_id, fields="parents", **_SHARED).execute()
    return f.get("parents", [])


def move_file(creds: Credentials, file_id: str, new_parent_id: str, old_parent_id: str) -> None:
    """Move a file to new_parent_id, removing it from old_parent_id."""
    service = get_drive_service(creds)
    service.files().update(
        fileId=file_id,
        addParents=new_parent_id,
        removeParents=old_parent_id,
        fields="id, parents",
        **_SHARED,
    ).execute()


def get_folder_name(creds: Credentials, folder_id: str) -> str:
    """Get the name of a Drive folder."""
    service = get_drive_service(creds)
    folder = service.files().get(fileId=folder_id, fields="name", **_SHARED).execute()
    return folder.get("name", folder_id)
