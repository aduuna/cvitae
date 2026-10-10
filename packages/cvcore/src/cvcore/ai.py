"""What the AI tasks return (docs/BACKEND.md, Tasks). Every model passes `llm_schema`, so both
providers can produce it with structured output."""

from pydantic import Field

from cvcore.models import CvContent, CvModel


class JobAnalysis(CvModel):
    title: str = Field(description="The job title as advertised.")
    company: str = Field(description="The hiring company; empty when the ad does not say.")
    seniority: str = Field(description="For example junior, mid, senior, lead or principal.")
    must_have: list[str] = Field(description="Requirements the ad marks as essential.")
    nice_to_have: list[str] = Field(description="Requirements the ad marks as optional.")
    keywords: list[str] = Field(
        description="Skills, tools and domain terms an applicant tracking system would match."
    )
    summary: str = Field(description="Two or three sentences on what the role is about.")


class BulletChange(CvModel):
    source_id: str = Field(description="Id of the profile bullet this change is about.")
    rationale: str = Field(description="One sentence on why it was kept, reworded or moved.")


class TailoredCv(CvModel):
    content: CvContent = Field(description="The tailored CV.")
    changes: list[BulletChange] = Field(description="One entry per bullet that was reworded.")
    missing_keywords: list[str] = Field(
        description="Job keywords the profile does not cover. Never added to the CV."
    )
