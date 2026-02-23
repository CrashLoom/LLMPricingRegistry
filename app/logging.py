from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record as a compact JSON string."""
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        keys = (
            "event",
            "provider",
            "model",
            "status_code",
            "error_code",
            "request_id",
        )
        for key in keys:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> None:
    """Configure logging to emit JSON records when no host config exists."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
