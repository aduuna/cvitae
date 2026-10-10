"""USD prices per million tokens, by model id (docs/BACKEND.md, Cost tracking).

Checked on 2026-10-10 against Anthropic's model table, ai.google.dev/gemini-api/docs/pricing and
MiMo's pricing page. Input is priced at the cache-miss rate, so the cost of a run that hit a
provider's automatic cache is slightly overstated. Unknown models record `cost_usd = None` and log a
warning.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

MILLION = Decimal(1_000_000)


@dataclass(frozen=True)
class Price:
    input: Decimal
    output: Decimal


@dataclass(frozen=True)
class Period:
    starts: date
    price: Price
    long_prompt: tuple[int, Price] | None = None
    """Above this many input tokens, the whole request is billed at this price."""


def _price(input: str, output: str) -> Price:
    return Price(Decimal(input), Decimal(output))


PRICES: dict[str, tuple[Period, ...]] = {
    "claude-sonnet-5-5": (Period(date.min, _price("2.00", "10.00")),),
    "claude-haiku-5-5": (
        Period(date.min, _price("0.10", "0.50"), long_prompt=(100_000, _price("0.50", "2.50"))),
    ),
    "gemini-3.8-flash": (
        Period(date.min, _price("0.75", "3.75")),
        Period(date(2027, 1, 1), _price("1.50", "7.50")),
    ),
    "gemini-3.5-flash-lite": (Period(date.min, _price("0.30", "2.50")),),
    "mimo-v2.6-flash": (Period(date.min, _price("0.14", "0.28")),),
    "mimo-v2.6-pro": (Period(date.min, _price("0.435", "0.87")),),
}


def cost_usd(
    model: str, input_tokens: int, output_tokens: int, on: date | None = None
) -> Decimal | None:
    periods = PRICES.get(model)
    if not periods:
        logger.warning("no price for model", extra={"model": model})
        return None
    on = on or datetime.now(UTC).date()
    period = max((p for p in periods if p.starts <= on), key=lambda p: p.starts)
    price = period.price
    if period.long_prompt and input_tokens > period.long_prompt[0]:
        price = period.long_prompt[1]
    total = (input_tokens * price.input + output_tokens * price.output) / MILLION
    return total.quantize(Decimal("0.000001"))
