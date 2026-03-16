import pytest
from backend.vector_store import VectorStore


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=str(tmp_path / "chroma"), dimensions=768)


def test_add_and_search(store):
    store.add_embedding(
        folder_id="test_folder",
        file_id="file_1",
        embedding=[0.1] * 768,
        metadata={"name": "sunset.jpg", "mime_type": "image/jpeg", "folder_id": "test_folder"},
    )

    results = store.search(folder_id="test_folder", query_embedding=[0.1] * 768, limit=5)
    assert len(results) == 1
    assert results[0]["file_id"] == "file_1"
    assert results[0]["name"] == "sunset.jpg"
    assert results[0]["similarity"] >= 0.99


def test_search_empty_collection(store):
    results = store.search(folder_id="nonexistent", query_embedding=[0.0] * 768, limit=5)
    assert results == []


def test_add_multiple_and_rank(store):
    store.add_embedding(
        folder_id="f1",
        file_id="a",
        embedding=[1.0, 0.0, 0.0] + [0.0] * 765,
        metadata={"name": "a.jpg", "mime_type": "image/jpeg", "folder_id": "f1"},
    )
    store.add_embedding(
        folder_id="f1",
        file_id="b",
        embedding=[0.9, 0.1, 0.0] + [0.0] * 765,
        metadata={"name": "b.jpg", "mime_type": "image/jpeg", "folder_id": "f1"},
    )
    store.add_embedding(
        folder_id="f1",
        file_id="c",
        embedding=[0.0, 1.0, 0.0] + [0.0] * 765,
        metadata={"name": "c.jpg", "mime_type": "image/jpeg", "folder_id": "f1"},
    )

    results = store.search(folder_id="f1", query_embedding=[1.0, 0.0, 0.0] + [0.0] * 765, limit=3)
    assert results[0]["file_id"] == "a"
    assert results[1]["file_id"] == "b"
    assert results[0]["similarity"] > results[1]["similarity"] > results[2]["similarity"]


def test_delete_folder(store):
    store.add_embedding(
        folder_id="del_me",
        file_id="x",
        embedding=[0.5] * 768,
        metadata={"name": "x.jpg", "mime_type": "image/jpeg", "folder_id": "del_me"},
    )
    assert store.get_file_count("del_me") == 1
    store.delete_folder("del_me")
    assert store.get_file_count("del_me") == 0


def test_get_file_count_nonexistent(store):
    assert store.get_file_count("nope") == 0


def test_has_file(store):
    store.add_embedding(
        folder_id="f",
        file_id="exists",
        embedding=[0.1] * 768,
        metadata={"name": "e.jpg", "mime_type": "image/jpeg", "folder_id": "f"},
    )
    assert store.has_file("f", "exists") is True
    assert store.has_file("f", "missing") is False
