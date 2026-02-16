"""Structured JSON logging for Google Cloud Logging integration.

Cloud Run captures structured JSON from stdout as Cloud Logging entries,
providing severity levels, timestamps, and trace correlation automatically.
"""

import json
import logging
import sys


class CloudJSONFormatter(logging.Formatter):
    """Formats log records as JSON for Cloud Logging ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudJSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
