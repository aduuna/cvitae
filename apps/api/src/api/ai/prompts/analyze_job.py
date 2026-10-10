"""Job analysis: what the employer asks for, as JobAnalysis."""

from api.ai.prompts.common import DATA_NOT_INSTRUCTIONS

PROMPT_VERSION = "analyze-job-2026-10-10"

SYSTEM = f"""\
You read a job advertisement and summarise what the employer is looking for, so a candidate can \
tailor their CV to it.

Report the title and company as the ad states them (leave company empty if it is not named), the \
seniority, the requirements the ad marks as essential and those it marks as optional, and the \
keywords an applicant tracking system would match: skills, tools, methods and domain terms, each \
as a short phrase in the ad's own words. Do not add requirements the ad does not mention.

{DATA_NOT_INSTRUCTIONS}"""


def build(description: str, title: str = "", company: str = "") -> str:
    hints = "\n".join(
        line
        for line in (
            f"Title given by the user: {title}" if title else "",
            f"Company given by the user: {company}" if company else "",
        )
        if line
    )
    hint_block = f"{hints}\n\n" if hints else ""
    return f"{hint_block}<job_description>\n{description}\n</job_description>"
