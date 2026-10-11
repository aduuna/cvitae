"""JSON logs on stdout, which Cloud Logging parses (docs/BACKEND.md, Logging and observability).

Fields passed with `extra=` (ids, counts, durations, error codes) become fields of the entry. Never
pass user content: CVs, profiles, job descriptions, files or prompts.
"""

import json
import logging
import sys

# Attributes every LogRecord has; anything else on a record came from `extra=`.
_RECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        entry.update({k: v for k, v in record.__dict__.items() if k not in _RECORD_FIELDS})
        if record.exc_info:
            # Error Reporting reads stack traces from this field.
            entry["stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Send the app's logs to stdout as JSON, at INFO and above."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
