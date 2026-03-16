"""
Structured logging configuration for Semantic Drive Search.

Provides JSON-formatted logs suitable for production environments
and human-readable logs for development.
"""

import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Try to import structlog for structured logging, fall back to standard logging
try:
    import structlog  # noqa: F401
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def json_formatter(record: logging.LogRecord) -> str:
    """Format log records as JSON for production."""
    log_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }

    # Add extra fields if present
    if hasattr(record, "folder_id"):
        log_data["folder_id"] = record.folder_id
    if hasattr(record, "file_id"):
        log_data["file_id"] = record.file_id
    if hasattr(record, "duration_ms"):
        log_data["duration_ms"] = record.duration_ms
    if hasattr(record, "error"):
        log_data["error"] = record.error

    # Add exception info if present
    if record.exc_info:
        log_data["exception"] = logging.Formatter().formatException(record.exc_info)

    import json
    return json.dumps(log_data)


def human_formatter(record: logging.LogRecord) -> str:
    """Format log records for human readability (development)."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    level = record.levelname.ljust(5)
    logger = record.name.split(".")[-1]

    base = f"{timestamp} | {level} | {logger} | {record.getMessage()}"

    # Add extra fields
    extras = []
    if hasattr(record, "folder_id"):
        extras.append(f"folder={record.folder_id[:12]}...")
    if hasattr(record, "file_id"):
        extras.append(f"file={record.file_id[:12]}...")
    if hasattr(record, "duration_ms"):
        extras.append(f"duration={record.duration_ms}ms")

    if extras:
        base += f" | {' '.join(extras)}"

    if record.exc_info:
        base += f"\n{logging.Formatter().formatException(record.exc_info)}"

    return base


class StructuredLogger:
    """
    A logger that supports structured logging with extra fields.

    Usage:
        log = get_logger(__name__)
        log.info("Indexing started", folder_id="abc123")
        log.error("Failed to embed", file_id="xyz", error=str(e))
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO)

        # Only add handler if not already configured
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)

            # Use JSON in production, human-readable in development
            import os
            if os.getenv("LOG_FORMAT", "human").lower() == "json":
                handler.setFormatter(logging.Formatter())
                handler.formatter.format = json_formatter
            else:
                handler.setFormatter(logging.Formatter())
                handler.formatter.format = human_formatter

            self._logger.addHandler(handler)

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """Log with extra fields attached to the record."""
        extra = {}
        for key, value in kwargs.items():
            extra[key] = value

        self._logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, **kwargs)

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        extra = {}
        for key, value in kwargs.items():
            extra[key] = value
        self._logger.exception(msg, extra=extra)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger for the given module name."""
    return StructuredLogger(name)


# Configure root logger
def configure_logging(level: str = "INFO", log_format: str = "human") -> None:
    """
    Configure logging for the entire application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_format: Output format ('json' or 'human')
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add new handler
    handler = logging.StreamHandler(sys.stdout)

    if log_format.lower() == "json":
        handler.setFormatter(logging.Formatter())
        handler.formatter.format = json_formatter
    else:
        handler.setFormatter(logging.Formatter())
        handler.formatter.format = human_formatter

    root_logger.addHandler(handler)
