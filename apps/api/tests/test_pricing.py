from datetime import date
from decimal import Decimal

import pytest

from api.ai.pricing import cost_usd


@pytest.mark.parametrize(
    ("model", "input_tokens", "output_tokens", "on", "expected"),
    [
        ("claude-sonnet-5-5", 10_000, 2_000, None, "0.040000"),
        ("claude-haiku-5-5", 10_000, 2_000, None, "0.002000"),
        # Above 100K input tokens Haiku bills the whole request at the long-prompt rate.
        ("claude-haiku-5-5", 200_000, 1_000, None, "0.102500"),
        ("gemini-3.8-flash", 10_000, 2_000, date(2026, 12, 31), "0.015000"),
        ("gemini-3.8-flash", 10_000, 2_000, date(2027, 1, 1), "0.030000"),
        ("gemini-3.5-flash-lite", 10_000, 2_000, None, "0.008000"),
        ("mimo-v2.6-flash", 10_000, 2_000, None, "0.001960"),
        ("mimo-v2.6-pro", 10_000, 2_000, None, "0.006090"),
    ],
)
def test_costs(
    model: str, input_tokens: int, output_tokens: int, on: date | None, expected: str
) -> None:
    assert cost_usd(model, input_tokens, output_tokens, on) == Decimal(expected)


def test_unknown_models_have_no_cost(caplog: pytest.LogCaptureFixture) -> None:
    assert cost_usd("claude-unknown", 10, 10) is None
    assert "no price for model" in caplog.text
