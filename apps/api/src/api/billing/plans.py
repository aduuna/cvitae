"""Plans and their limits (docs/PRODUCT.md, Plans and limits). Change limits here only."""

from dataclasses import dataclass
from typing import Literal

Plan = Literal["free", "pro"]


@dataclass(frozen=True)
class PlanLimits:
    id: Plan
    label: str
    documents: int
    """CVs a user may keep."""
    profiles: int
    templates: int
    """Custom templates (made from the user's own CV) a user may keep."""
    ai_runs: int
    """Per calendar month (UTC). A run is one import, one job analysis, one tailoring, one AI
    edit, one request for drafted answers or one custom template."""
    counts_failed_runs: bool
    """Free counts every attempt, so failed calls cannot be used to spend AI tokens for free;
    Pro counts succeeded runs only."""


PLANS: dict[Plan, PlanLimits] = {
    "free": PlanLimits(
        id="free",
        label="Free",
        documents=4,
        profiles=2,
        templates=1,
        ai_runs=20,
        counts_failed_runs=True,
    ),
    "pro": PlanLimits(
        id="pro",
        label="Pro",
        documents=100,
        profiles=10,
        templates=10,
        ai_runs=150,
        counts_failed_runs=False,
    ),
}

UPGRADE: Plan = "pro"
"""The plan a Free user can upgrade to."""
