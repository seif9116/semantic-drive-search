from backend.config import Settings


def test_default_settings():
    s = Settings()
    assert s.embedding_dimensions == 768
    assert s.max_image_size == 20 * 1024 * 1024
    assert "image/jpeg" in s.supported_image_types
    assert "video/mp4" in s.supported_video_types
    assert len(s.supported_media_types) == len(s.supported_image_types) + len(s.supported_video_types)
    assert "postgresql" in s.database_url
