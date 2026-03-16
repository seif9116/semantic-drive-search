"""
Embedding generation using Google's Gemini Embedding 2 model.

Provides functions for generating embeddings from images and text,
with retry logic, batch processing, and caching support.
"""

import asyncio
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor

from google import genai
from google.genai import types

from backend.config import settings
from backend.logging_config import get_logger

log = get_logger(__name__)

MODEL = "gemini-embedding-2-preview"

# Thread pool for parallel embedding generation
_executor = ThreadPoolExecutor(max_workers=4)


def get_client() -> genai.Client:
    """Get a Gemini API client."""
    return genai.Client(api_key=settings.google_api_key)


def compute_file_hash(file_bytes: bytes) -> str:
    """Compute a hash of file contents for caching."""
    return hashlib.sha256(file_bytes).hexdigest()


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


def embed_batch(
    items: list[tuple[bytes, str]],  # List of (file_bytes, mime_type)
    dimensions: int | None = None,
) -> list[list[float] | None]:
    """
    Generate embeddings for multiple images in batch.

    Args:
        items: List of (file_bytes, mime_type) tuples
        dimensions: Output dimensions (default from settings)

    Returns:
        List of embeddings (or None for failed items)
    """
    results = []
    client = get_client()
    dims = dimensions or settings.embedding_dimensions

    for file_bytes, mime_type in items:
        try:
            result = client.models.embed_content(
                model=MODEL,
                contents=[types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
                config=types.EmbedContentConfig(output_dimensionality=dims),
            )
            results.append(list(result.embeddings[0].values))
        except Exception as e:
            log.warning(f"Failed to embed item: {e}")
            results.append(None)

    return results


def _is_retryable(e: Exception) -> bool:
    """Check if an exception is transient and worth retrying."""
    err = str(e).lower()
    return any(s in err for s in [
        "429", "resource_exhausted",
        "unable to find the server",
        "name resolution", "connection refused",
        "connection reset", "connection aborted",
        "timed out", "timeout",
        "503", "502", "500",
    ])


def embed_image_with_retry(
    image_bytes: bytes,
    mime_type: str,
    max_retries: int = 3,
    compute_hash: bool = False,
) -> tuple[list[float] | None, str | None]:
    """
    Embed image with exponential backoff on rate limits and transient errors.

    Args:
        image_bytes: Raw image data
        mime_type: MIME type of the image
        max_retries: Maximum number of retry attempts
        compute_hash: Whether to compute and return a file hash

    Returns:
        Tuple of (embedding, file_hash) - embedding may be None on failure
    """
    if not image_bytes:
        return None, None

    file_hash = compute_file_hash(image_bytes) if compute_hash else None

    for attempt in range(max_retries):
        try:
            start = time.time()
            embedding = embed_image(image_bytes, mime_type)
            duration_ms = int((time.time() - start) * 1000)
            log.debug("Embedded image", duration_ms=duration_ms)
            return embedding, file_hash
        except Exception as e:
            if _is_retryable(e) and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                log.warning(f"Retryable error, waiting {wait}s", error=str(e)[:100])
                time.sleep(wait)
                continue
            log.error(f"Failed to embed image after {max_retries} attempts", error=str(e)[:100])
            raise

    return None, file_hash


def embed_text_with_retry(text: str, max_retries: int = 3) -> list[float] | None:
    """Embed text with exponential backoff on rate limits and transient errors."""
    for attempt in range(max_retries):
        try:
            start = time.time()
            embedding = embed_text(text)
            duration_ms = int((time.time() - start) * 1000)
            log.debug("Embedded text query", duration_ms=duration_ms)
            return embedding
        except Exception as e:
            if _is_retryable(e) and attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                log.warning(f"Retryable error, waiting {wait}s", error=str(e)[:100])
                time.sleep(wait)
                continue
            log.error(f"Failed to embed text after {max_retries} attempts", error=str(e)[:100])
            raise
    return None


async def embed_image_async(
    image_bytes: bytes,
    mime_type: str,
    max_retries: int = 3,
    compute_hash: bool = False,
) -> tuple[list[float] | None, str | None]:
    """
    Async wrapper for embedding generation.

    Runs embedding in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        embed_image_with_retry,
        image_bytes,
        mime_type,
        max_retries,
        compute_hash,
    )


async def embed_batch_async(
    items: list[tuple[bytes, str]],
    max_concurrent: int = 4,
) -> list[tuple[list[float] | None, str | None]]:
    """
    Generate embeddings for multiple images concurrently.

    Args:
        items: List of (file_bytes, mime_type) tuples
        max_concurrent: Maximum concurrent embedding requests

    Returns:
        List of (embedding, file_hash) tuples
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def embed_one(file_bytes: bytes, mime_type: str):
        async with semaphore:
            return await embed_image_async(file_bytes, mime_type, compute_hash=True)

    tasks = [embed_one(fb, mt) for fb, mt in items]
    return await asyncio.gather(*tasks)
