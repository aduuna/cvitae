"""Structured logs for Cloud Logging."""

import io
import json
import logging
import sys

import pytest

from api.logs import JsonFormatter, configure_logging


def entry(record: logging.LogRecord) -> dict[str, object]:
    return json.loads(JsonFormatter().format(record))


def test_extra_fields_become_fields_of_the_entry() -> None:
    record = logging.makeLogRecord(
        {
            "name": "api.ports.billing",
            "levelname": "WARNING",
            "msg": "paystack call failed",
            "operation": "fetch_plan",
            "status": 404,
            "reason": "Plan ID/code specified is invalid",
        }
    )

    assert entry(record) == {
        "severity": "WARNING",
        "message": "paystack call failed",
        "logger": "api.ports.billing",
        "operation": "fetch_plan",
        "status": 404,
        "reason": "Plan ID/code specified is invalid",
    }


def test_exceptions_carry_their_stack_trace() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        record = logging.getLogger("api").makeRecord(
            "api", logging.ERROR, __file__, 1, "failed", (), exc_info=sys.exc_info()
        )

    logged = entry(record)
    assert (logged["severity"], logged["message"]) == ("ERROR", "failed")
    assert "RuntimeError: boom" in str(logged["stack_trace"])


def test_configure_logging_writes_json_lines_to_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    try:
        configure_logging()
        logging.getLogger("api.ai.tasks").info("ai run", extra={"task": "tailor", "cost_usd": 0.01})
    finally:
        root.handlers, root.level = saved[0], saved[1]

    assert json.loads(out.getvalue()) == {
        "severity": "INFO",
        "message": "ai run",
        "logger": "api.ai.tasks",
        "task": "tailor",
        "cost_usd": 0.01,
    }
