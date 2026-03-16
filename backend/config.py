from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "change-me-in-production")
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./data")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "768"))
    redirect_uri: str = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
    max_image_size: int = 20 * 1024 * 1024  # 20MB
    max_video_size: int = 100 * 1024 * 1024  # 100MB
    supported_image_types: tuple = ("image/jpeg", "image/png", "image/gif", "image/webp")
    supported_video_types: tuple = ("video/mp4", "video/quicktime", "video/x-msvideo", "video/webm")

    @property
    def supported_media_types(self) -> tuple:
        return self.supported_image_types + self.supported_video_types


settings = Settings()
