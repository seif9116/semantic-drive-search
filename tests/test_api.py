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
