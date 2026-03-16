from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.main import _extract_folder_id


@pytest.fixture
def client():
    with patch("backend.main.vs.VectorStore") as mock_vs:
        mock_store = MagicMock()
        mock_store.get_file_count.return_value = 0
        mock_store.list_folders.return_value = []
        mock_vs.return_value = mock_store

        from backend.main import app
        with TestClient(app) as c:
            yield c


def test_extract_folder_id_url():
    url = "https://drive.google.com/drive/folders/1abc_XYZ-123?usp=sharing"
    assert _extract_folder_id(url) == "1abc_XYZ-123"


def test_extract_folder_id_raw():
    assert _extract_folder_id("1abc_XYZ-123") == "1abc_XYZ-123"


def test_auth_status_unauthenticated(client):
    with patch("backend.main.auth.is_authenticated", return_value=False):
        resp = client.get("/auth/status")
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is False


def test_root_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_search_requires_auth(client):
    with patch("backend.main.auth.get_credentials", return_value=None):
        resp = client.get("/api/search?q=sunset&folder_id=abc")
        assert resp.status_code == 401


def test_thumbnail_uses_thumbnail_link(client):
    """Thumbnail endpoint should fetch the small Drive thumbnailLink, not the full file."""
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_file_meta = {"thumbnailLink": "https://lh3.googleusercontent.com/fake-thumb"}

    mock_service.files.return_value.get.return_value.execute.return_value = mock_file_meta

    with patch("backend.main.auth.get_credentials", return_value=mock_creds), \
         patch("backend.main.drive.get_drive_service", return_value=mock_service), \
         patch("httpx.AsyncClient") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"\xff\xd8\xff\xe0fake-jpeg-thumbnail"
        mock_resp.headers = {"content-type": "image/jpeg"}

        mock_async_client = MagicMock()
        mock_async_client.__aenter__ = lambda self: _async_return(self)
        mock_async_client.__aexit__ = lambda self, *a: _async_return(None)
        mock_async_client.get = lambda *a, **kw: _async_return(mock_resp)
        mock_httpx.return_value = mock_async_client

        resp = client.get("/api/media/test-file-id/thumbnail")
        assert resp.status_code == 200
        assert resp.content == b"\xff\xd8\xff\xe0fake-jpeg-thumbnail"

    # Verify it requested thumbnailLink, not get_media (full download)
    mock_service.files.return_value.get.assert_called_once_with(
        fileId="test-file-id", fields="thumbnailLink", supportsAllDrives=True,
    )


def test_thumbnail_falls_back_to_full_download(client):
    """When no thumbnailLink is available, fall back to downloading the full file."""
    mock_creds = MagicMock()
    mock_service = MagicMock()
    mock_file_meta = {}  # No thumbnailLink

    mock_service.files.return_value.get.return_value.execute.return_value = mock_file_meta

    with patch("backend.main.auth.get_credentials", return_value=mock_creds), \
         patch("backend.main.drive.get_drive_service", return_value=mock_service), \
         patch("backend.main.drive.download_file", return_value=b"full-file-bytes") as mock_dl:
        resp = client.get("/api/media/test-file-id/thumbnail")
        assert resp.status_code == 200
        assert resp.content == b"full-file-bytes"
        mock_dl.assert_called_once_with(mock_creds, "test-file-id")


def test_thumbnail_requires_auth(client):
    """Thumbnail endpoint should return 401 when not authenticated."""
    with patch("backend.main.auth.get_credentials", return_value=None):
        resp = client.get("/api/media/test-file-id/thumbnail")
        assert resp.status_code == 401


import asyncio

async def _async_return(val):
    return val
