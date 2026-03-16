"""
Custom exception classes for Semantic Drive Search.

Provides typed exceptions for better error handling and reporting.
"""



class SDSError(Exception):
    """Base exception for all Semantic Drive Search errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# --- Authentication Errors ---

class AuthError(SDSError):
    """Base error for authentication issues."""
    pass


class NotAuthenticatedError(AuthError):
    """User is not authenticated with Google Drive."""

    def __init__(self, message: str = "Not authenticated with Google Drive"):
        super().__init__(message)


class TokenExpiredError(AuthError):
    """OAuth token has expired and cannot be refreshed."""

    def __init__(self, message: str = "OAuth token expired"):
        super().__init__(message)


class OAuthError(AuthError):
    """OAuth flow failed."""

    def __init__(self, message: str, provider_error: str | None = None):
        super().__init__(message, {"provider_error": provider_error})


# --- Database Errors ---

class DatabaseError(SDSError):
    """Base error for database issues."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Cannot connect to the database."""

    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message)


class VectorStoreError(DatabaseError):
    """Error in vector store operations."""

    def __init__(self, message: str, folder_id: str | None = None):
        super().__init__(message, {"folder_id": folder_id})


# --- Embedding Errors ---

class EmbeddingError(SDSError):
    """Base error for embedding generation issues."""
    pass


class GeminiAPIError(EmbeddingError):
    """Error calling the Gemini API."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, {"status_code": status_code})


class RateLimitError(EmbeddingError):
    """Rate limit exceeded for embedding API."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        super().__init__(message, {"retry_after": retry_after})


class UnsupportedMediaTypeError(EmbeddingError):
    """Media type is not supported for embedding."""

    def __init__(self, mime_type: str):
        super().__init__(
            f"Unsupported media type: {mime_type}",
            {"mime_type": mime_type}
        )


class FileTooLargeError(EmbeddingError):
    """File exceeds size limit for embedding."""

    def __init__(self, size: int, max_size: int, mime_type: str):
        super().__init__(
            f"File too large: {size} bytes (max {max_size})",
            {"size": size, "max_size": max_size, "mime_type": mime_type}
        )


# --- Drive Errors ---

class DriveError(SDSError):
    """Base error for Google Drive operations."""
    pass


class DriveQuotaError(DriveError):
    """Google Drive quota exceeded."""

    def __init__(self, message: str = "Drive quota exceeded"):
        super().__init__(message)


class DriveFileNotFoundError(DriveError):
    """File or folder not found in Google Drive."""

    def __init__(self, file_id: str):
        super().__init__(f"File not found: {file_id}", {"file_id": file_id})


class DrivePermissionError(DriveError):
    """Permission denied for Google Drive operation."""

    def __init__(self, file_id: str | None = None):
        super().__init__(
            "Permission denied for Drive operation",
            {"file_id": file_id}
        )


class DriveDownloadError(DriveError):
    """Failed to download file from Google Drive."""

    def __init__(self, file_id: str, reason: str):
        super().__init__(
            f"Failed to download file: {reason}",
            {"file_id": file_id, "reason": reason}
        )


# --- Indexing Errors ---

class IndexingError(SDSError):
    """Base error for indexing operations."""
    pass


class FolderAlreadyIndexingError(IndexingError):
    """Folder is already being indexed."""

    def __init__(self, folder_id: str):
        super().__init__(
            "Folder is already being indexed",
            {"folder_id": folder_id}
        )


class IndexingFailedError(IndexingError):
    """Indexing operation failed."""

    def __init__(self, folder_id: str, reason: str, files_processed: int = 0):
        super().__init__(
            f"Indexing failed: {reason}",
            {"folder_id": folder_id, "files_processed": files_processed}
        )


# --- Search Errors ---

class SearchError(SDSError):
    """Base error for search operations."""
    pass


class EmptyQueryError(SearchError):
    """Search query is empty."""

    def __init__(self):
        super().__init__("Search query cannot be empty")


class FolderNotIndexedError(SearchError):
    """Folder has not been indexed yet."""

    def __init__(self, folder_id: str):
        super().__init__(
            "Folder has not been indexed",
            {"folder_id": folder_id}
        )
