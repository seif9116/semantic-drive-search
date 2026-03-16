import time
from google import genai
from google.genai import types
from backend.config import settings

MODEL = "gemini-embedding-2-preview"


def get_client() -> genai.Client:
    return genai.Client(api_key=settings.google_api_key)


def embed_image(image_bytes: bytes, mime_type: str, dimensions: int | None = None) -> list[float]:
    """Generate embedding for a single image."""
    client = get_client()
    dims = dimensions or settings.embedding_dimensions
    result = client.models.embed_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.EmbedContentConfig(output_dimensionality=dims),
    )
    return list(result.embeddings[0].values)


def embed_text(text: str, dimensions: int | None = None) -> list[float]:
    """Generate embedding for a text query."""
    client = get_client()
    dims = dimensions or settings.embedding_dimensions
    result = client.models.embed_content(
        model=MODEL,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=dims),
    )
    return list(result.embeddings[0].values)


def embed_image_with_retry(
    image_bytes: bytes, mime_type: str, max_retries: int = 3
) -> list[float] | None:
    """Embed image with exponential backoff on rate limits."""
    for attempt in range(max_retries):
        try:
            return embed_image(image_bytes, mime_type)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            raise
    return None


def embed_text_with_retry(text: str, max_retries: int = 3) -> list[float] | None:
    """Embed text with exponential backoff on rate limits."""
    for attempt in range(max_retries):
        try:
            return embed_text(text)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            raise
    return None
