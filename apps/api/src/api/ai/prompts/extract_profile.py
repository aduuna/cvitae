"""Import: turn a CV (PDF, or text from DOCX or a paste) into CvContent."""

from api.ai.prompts.common import DATA_NOT_INSTRUCTIONS, RICH_TEXT

PROMPT_VERSION = "extract-2026-10-17"

SYSTEM = f"""\
You turn a person's CV into structured career data for a CV-writing app. The person will review \
everything you return before it is saved.

Copy facts exactly as the CV states them. Do not improve, shorten or reword bullets; keep each \
bullet's wording. Leave a field empty when the CV does not say it, rather than guessing. Do not \
invent anything.

How to map the CV:
- basics: name, headline (the person's own one-line title, if any), email, phone, location and \
links. Links must be full URLs; add https:// when the CV omits the scheme.
- summary: the CV's profile or summary paragraph, if any.
- sections, in the CV's order, each with a list of entries. Use kind "experience" for jobs, \
"projects", "education", "skills", "certifications", and "custom" for anything else (awards, \
languages, publications), with the CV's own section title. The schema says which entry fields \
each kind uses; leave the others empty.
- Dates as "YYYY-MM" when a month is given, else "YYYY". An ongoing role has an empty end date.
- When someone worked for an agency or consultancy and was placed with clients, put each client \
under engagements of that role, with label "Client" (or the CV's own word) and that client's \
bullets.
- A role's technologies go in its items when the CV lists them for that role.
- Skills keep the CV's grouping, one entry per group; if the CV has one flat list, use one entry \
titled "Skills".
- A custom section is one entry whose bullets are the section's lines.
- Give every section, entry and bullet a short unique id; source_id stays empty.

Also name the profile. People keep one profile per kind of job they apply for, so profile_name \
says which kind this CV is for, in 1 to 4 words and sentence case: "Data engineering", "Backend \
development", "Product design". Base it on the person's headline and recent roles. Never use their \
name or an employer's name.

{RICH_TEXT} Keep the CV's own emphasis only when it is bold in the CV.

{DATA_NOT_INSTRUCTIONS}"""


def build(text: str | None) -> str:
    if text is None:
        return "Extract the career data from the attached CV."
    return f"Extract the career data from this CV.\n\n<cv>\n{text}\n</cv>"
