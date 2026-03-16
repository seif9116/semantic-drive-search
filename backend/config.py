import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SDS_DIR = Path.home() / ".sds"
SDS_SETTINGS = SDS_DIR / "settings.json"


def _load_sds_settings() -> dict:
    """Load settings from ~/.sds/settings.json if it exists."""
    if SDS_SETTINGS.exists():
        try:
            return json.loads(SDS_SETTINGS.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _get(key: str, default: str, sds: dict) -> str:
    """Resolve a setting: ~/.sds/settings.json > env var > default."""
    return sds.get(key) or os.getenv(key) or default


_sds = _load_sds_settings()


@dataclass(frozen=True)
class Settings:
    google_api_key: str = _get("GOOGLE_API_KEY", "", _sds)
    google_client_id: str = _get("GOOGLE_CLIENT_ID", "", _sds)
    google_client_secret: str = _get("GOOGLE_CLIENT_SECRET", "", _sds)
    app_secret_key: str = _get("APP_SECRET_KEY", "change-me-in-production", _sds)
    database_url: str = _get("DATABASE_URL", "postgresql:///semantic_search", _sds)
    embedding_dimensions: int = int(_get("EMBEDDING_DIMENSIONS", "768", _sds))
    redirect_uri: str = _get("REDIRECT_URI", "http://localhost:8000/auth/callback", _sds)
    max_image_size: int = 20 * 1024 * 1024  # 20MB
    max_video_size: int = 100 * 1024 * 1024  # 100MB
    supported_image_types: tuple = ("image/jpeg", "image/png", "image/gif", "image/webp")
    supported_video_types: tuple = ("video/mp4", "video/quicktime", "video/x-msvideo", "video/webm")

    @property
    def supported_media_types(self) -> tuple:
        return self.supported_image_types + self.supported_video_types


settings = Settings()
