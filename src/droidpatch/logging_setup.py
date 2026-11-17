"""JSON logging configuration for the FastAPI service."""

import json
import logging
from typing import Any

from droidpatch.config import Settings


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log entry."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if hasattr(record, "status"):
            payload["status"] = record.status
        if hasattr(record, "path"):
            payload["path"] = record.path
        if hasattr(record, "method"):
            payload["method"] = record.method
        if hasattr(record, "duration_ms"):
            payload["duration_ms"] = record.duration_ms
        if hasattr(record, "records"):
            payload["records"] = record.records
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def setup_logging(settings: Settings | None = None) -> None:
    """Initialize a single JSON logging handler on the root logger."""
    settings = settings or Settings()
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root_logger.addHandler(handler)
    else:
        handler = root_logger.handlers[0]
        handler.setFormatter(JsonFormatter())

    root_logger.propagate = False
