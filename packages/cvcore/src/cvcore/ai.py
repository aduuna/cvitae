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


class ImportedCv(CvModel):
    content: CvContent = Field(description="The career data, copied from the CV.")
    profile_name: str = Field(
        description='A suggested profile name, for example "Data engineering".'
    )


class CvEdit(CvModel):
    reply: str = Field(description="What the model says back to the person.")
    content: CvContent = Field(description="The whole CV after the change.")


class SkillMention(CvModel):
    skill: str = Field(description="A skill, tool or technology the answer names.")
    based_on: list[str] = Field(
        description="The skills, tools or roles in the applicant's material it rests on."
    )


class DraftAnswer(CvModel):
    id: str = Field(description="The id of the question this answers.")
    text: str = Field(
        description="The answer in plain text; empty when the question must not be answered."
    )
    skills: list[SkillMention] = Field(
        description=(
            "Every skill, tool or technology the answer names, including those the question "
            "asks about."
        )
    )


class DraftAnswers(CvModel):
    """Drafted answers to application questions. Not CV content: they follow the drafts' rule
    (docs/PRODUCT.md, 8, Answer questions) and never pass through the fact guard."""

    answers: list[DraftAnswer] = Field(description="One answer per question, in order.")


class TailoredCv(CvModel):
    content: CvContent = Field(description="The tailored CV.")
    changes: list[BulletChange] = Field(description="One entry per bullet that was reworded.")
