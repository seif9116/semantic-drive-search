from unittest.mock import patch, MagicMock
from backend.embeddings import embed_image, embed_text, MODEL, embed_image_with_retry


def _make_mock_result(dims=768):
    mock_embedding = MagicMock()
    mock_embedding.values = [0.1] * dims
    mock_result = MagicMock()
    mock_result.embeddings = [mock_embedding]
    return mock_result


@patch("backend.embeddings.get_client")
def test_embed_image(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _make_mock_result()
    mock_get_client.return_value = mock_client

    result = embed_image(b"fake-image-bytes", "image/jpeg")

    assert len(result) == 768
    assert all(v == 0.1 for v in result)
    mock_client.models.embed_content.assert_called_once()
    call_kwargs = mock_client.models.embed_content.call_args
    assert call_kwargs.kwargs["model"] == MODEL


@patch("backend.embeddings.get_client")
def test_embed_text(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _make_mock_result()
    mock_get_client.return_value = mock_client

    result = embed_text("sunset over mountains")

    assert len(result) == 768
    mock_client.models.embed_content.assert_called_once()


@patch("backend.embeddings.get_client")
def test_embed_image_with_retry(mock_get_client):
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _make_mock_result()
    mock_get_client.return_value = mock_client

    embedding, file_hash = embed_image_with_retry(b"fake-image-bytes", "image/jpeg", compute_hash=True)

    assert len(embedding) == 768
    assert file_hash is not None
    assert len(file_hash) == 64  # SHA-256 hex digest


@patch("backend.embeddings.get_client")
def test_embed_image_with_retry_empty(mock_get_client):
    """Empty bytes should return None."""
    embedding, file_hash = embed_image_with_retry(b"", "image/jpeg")
    assert embedding is None
    assert file_hash is None
