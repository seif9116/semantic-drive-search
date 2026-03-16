import os
import pytest
from unittest.mock import patch, MagicMock, call

from backend.vector_store import VectorStore

DATABASE_URL = os.getenv("DATABASE_URL", "")
requires_db = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL not set")


# --- Unit tests (mocked, always run) ---


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_add_embedding_executes_upsert(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    store.add_embedding(
        folder_id="f1",
        file_id="abc",
        embedding=[0.1] * 768,
        metadata={"name": "test.jpg", "mime_type": "image/jpeg"},
    )

    mock_ctx.execute.assert_called_once()
    sql = mock_ctx.execute.call_args[0][0]
    assert "INSERT INTO embeddings" in sql
    assert "ON CONFLICT" in sql


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_search_returns_formatted_results(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_ctx.execute.return_value.fetchall.return_value = [
        ("file1", "sunset.jpg", "image/jpeg", "f1", 0.9512),
        ("file2", "beach.jpg", "image/jpeg", "f1", 0.8234),
    ]
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    results = store.search(folder_id="f1", query_embedding=[0.1] * 768, limit=5)

    assert len(results) == 2
    assert results[0]["file_id"] == "file1"
    assert results[0]["name"] == "sunset.jpg"
    assert results[0]["similarity"] == 0.9512
    assert results[1]["similarity"] == 0.8234


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_search_empty_returns_empty(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_ctx.execute.return_value.fetchall.return_value = []
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    results = store.search(folder_id="empty", query_embedding=[0.0] * 768, limit=5)
    assert results == []


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_delete_folder_executes_delete(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    store.delete_folder("test_folder")

    sql = mock_ctx.execute.call_args[0][0]
    assert "DELETE FROM embeddings" in sql


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_has_file_true(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_ctx.execute.return_value.fetchone.return_value = (1,)
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    assert store.has_file("f1", "exists") is True


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_has_file_false(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_ctx.execute.return_value.fetchone.return_value = None
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    assert store.has_file("f1", "missing") is False


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_get_file_count(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_ctx.execute.return_value.fetchone.return_value = (42,)
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    assert store.get_file_count("f1") == 42


@patch("backend.vector_store.VectorStore._init_db")
@patch("backend.vector_store.VectorStore._get_conn")
def test_list_folders(mock_conn, mock_init):
    mock_ctx = MagicMock()
    mock_ctx.execute.return_value.fetchall.return_value = [("folder_a",), ("folder_b",)]
    mock_conn.return_value.__enter__ = lambda s: mock_ctx
    mock_conn.return_value.__exit__ = MagicMock(return_value=False)

    store = VectorStore(database_url="postgresql://fake", dimensions=768)
    folders = store.list_folders()
    assert folders == ["folder_a", "folder_b"]


# --- Integration tests (require real PostgreSQL with pgvector) ---


@requires_db
def test_integration_add_search_delete():
    """Full integration test against a real PostgreSQL database."""
    store = VectorStore(database_url=DATABASE_URL, dimensions=768)

    # Clean up first
    store.delete_folder("_test_integration")

    # Add
    store.add_embedding(
        folder_id="_test_integration",
        file_id="int_file_1",
        embedding=[1.0, 0.0, 0.0] + [0.0] * 765,
        metadata={"name": "test.jpg", "mime_type": "image/jpeg", "folder_id": "_test_integration"},
    )
    store.add_embedding(
        folder_id="_test_integration",
        file_id="int_file_2",
        embedding=[0.0, 1.0, 0.0] + [0.0] * 765,
        metadata={"name": "other.jpg", "mime_type": "image/jpeg", "folder_id": "_test_integration"},
    )

    assert store.get_file_count("_test_integration") == 2
    assert store.has_file("_test_integration", "int_file_1") is True
    assert store.has_file("_test_integration", "int_file_missing") is False

    # Search
    results = store.search(
        folder_id="_test_integration",
        query_embedding=[1.0, 0.0, 0.0] + [0.0] * 765,
        limit=5,
    )
    assert len(results) == 2
    assert results[0]["file_id"] == "int_file_1"
    assert results[0]["similarity"] > results[1]["similarity"]

    # Delete
    store.delete_folder("_test_integration")
    assert store.get_file_count("_test_integration") == 0
