"""The fact guard against the sample profile, with the kinds of changes a model really makes."""

from collections.abc import Callable
from pathlib import Path

import pytest

from cvcore.factguard import FactReport, as_placeholder, check, number_tokens
from cvcore.models import (
    Bullet,
    CertificationItem,
    CvContent,
    DateRange,
    EducationItem,
    Engagement,
    ExperienceItem,
    Link,
    ProjectItem,
    Section,
    SkillGroup,
)
from cvcore.render import iter_bullets

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"


@pytest.fixture
def source() -> CvContent:
    content = CvContent.model_validate_json((FIXTURES / "profile-sample.json").read_text())
    content.sections.append(
        Section(
            id="sec-extra",
            kind="projects",
            title="Projects",
            projects=[
                ProjectItem(
                    id="p-ledger",
                    name="Typeset",
                    year="2024",
                    bullets=[Bullet(id="b-p-1", text="Validates **2** ledger formats.")],
                )
            ],
        )
    )
    content.sections.append(
        Section(
            id="sec-awards",
            kind="custom",
            title="Awards",
            custom=[Bullet(id="b-c-1", text="Speaker at PyData London 2023.")],
        )
    )
    return content


def tailor(source: CvContent, edit: Callable[[CvContent], None] | None = None) -> CvContent:
    """A tailored copy that points every bullet at its source, then `edit` applied."""
    content = source.model_copy(deep=True)
    for bullet in iter_bullets(content):
        bullet.source_id = bullet.id
    if edit:
        edit(content)
    return content


def experience(content: CvContent, item_id: str) -> ExperienceItem:
    return next(i for s in content.sections for i in s.experience if i.id == item_id)


def bullet(content: CvContent, bullet_id: str) -> Bullet:
    return next(b for b in iter_bullets(content) if b.id == bullet_id)


def kinds(report: FactReport) -> list[str]:
    return [issue.kind for issue in report.issues]


def test_an_unchanged_tailoring_passes(source: CvContent) -> None:
    tailored = tailor(source)

    report = check(source, tailored)

    assert report.issues == []
    assert report.content == tailored


def test_selecting_and_reordering_passes(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        section = content.sections[0]
        section.experience = list(reversed(section.experience[:2]))
        experience(content, "exp-brightline").bullets.pop()
        content.sections.reverse()

    report = check(source, tailor(source, edit))

    assert report.issues == []


def test_rewording_with_the_same_numbers_passes(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        bullet(
            content, "b-hb-1"
        ).text = "Cut nightly runtime **62%** by moving **140** Hadoop batch jobs to Spark on EMR."
        bullet(content, "b-bl-2").text = "Saved 4800 dollars a month on cloud spend."
        bullet(content, "b-kl-1").text = "Processed 1.2 million mobile-money payments a month."

    report = check(source, tailor(source, edit))

    assert report.issues == []


def test_new_numbers_become_placeholders(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        bullet(
            content, "b-hb-1"
        ).text = "Moved **140** jobs to Spark, cutting runtime by **75%** for 30 teams."

    report = check(source, tailor(source, edit))

    assert bullet(report.content, "b-hb-1").text == (
        "Moved **140** jobs to Spark, cutting runtime by "
        "**[[check this number: 75%]]** for [[check this number: 30]] teams."
    )
    assert [(i.kind, i.value, i.bullet_id) for i in report.issues] == [
        ("new_number", "75%", "b-hb-1"),
        ("new_number", "30", "b-hb-1"),
    ]


def test_a_number_from_another_bullet_is_still_new(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        bullet(content, "b-nw-1").text = "Lead a team of **5 engineers** across 12 clients."

    report = check(source, tailor(source, edit))

    assert "[[check this number: 12]]" in bullet(report.content, "b-nw-1").text


def test_a_changed_unit_is_a_new_number(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        bullet(content, "b-hb-1").text = "Moved 140 jobs, cutting runtime 62x."

    report = check(source, tailor(source, edit))

    assert [i.value for i in report.issues] == ["62x"]


def test_digits_inside_words_are_not_numbers(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        bullet(content, "b-hb-1").text = "Moved 140 jobs to Spark on EMR with S3 and EC2, v2 APIs."

    report = check(source, tailor(source, edit))

    assert report.issues == []


def test_placeholders_are_left_alone(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        bullet(
            content, "b-hb-2"
        ).text = "Fraud signals on Kafka for [[number of analysts, e.g. 40]]."

    report = check(source, tailor(source, edit))

    assert report.issues == []


@pytest.mark.parametrize("source_id", [None, "made-up"])
def test_bullets_without_a_known_source_become_placeholders(
    source: CvContent, source_id: str | None
) -> None:
    def edit(content: CvContent) -> None:
        experience(content, "exp-kente").bullets.append(
            Bullet(id="new", text="Led **Kubernetes** migration [[when]].", source_id=source_id)
        )

    report = check(source, tailor(source, edit))

    added = bullet(report.content, "new")
    assert added.text == "[[Led Kubernetes migration when.]]"
    assert added.source_id is None
    assert kinds(report) == ["new_claim"]
    assert "not in your profile" in report.issues[0].message


def test_a_bullet_moved_to_another_employer_is_a_new_claim(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        moved = experience(content, "exp-northwind").bullets.pop()
        experience(content, "exp-kente").bullets.append(moved)

    report = check(source, tailor(source, edit))

    assert kinds(report) == ["new_claim"]
    assert "comes from another entry" in report.issues[0].message
    assert bullet(report.content, "b-nw-1").text.startswith("[[Lead a team of 5 engineers")


def test_moving_between_a_role_and_its_clients_keeps_the_employer(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        northwind = experience(content, "exp-northwind")
        northwind.bullets.append(northwind.engagements[0].bullets.pop())

    report = check(source, tailor(source, edit))

    assert report.issues == []


def test_project_and_custom_bullets_keep_their_entries(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        bullet(content, "b-p-1").text = "Validates **2** ledger formats in C# and Python."
        bullet(content, "b-c-1").text = "Spoke at PyData London 2023."

    report = check(source, tailor(source, edit))

    assert report.issues == []


def test_changed_facts_revert(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        item = experience(content, "exp-brightline")
        item.role = "Senior data engineer"
        item.dates = DateRange(start="2016-01", end="2021-02")
        item.location = "Remote"
        experience(content, "exp-northwind").engagements[0].name = "Harbour Bank Group"

    report = check(source, tailor(source, edit))

    item = experience(report.content, "exp-brightline")
    assert (item.role, item.dates.start, item.location) == (
        "Data engineer",
        "2017-09",
        experience(source, "exp-brightline").location,
    )
    assert experience(report.content, "exp-northwind").engagements[0].name == "Harbour Bank"
    assert kinds(report) == ["changed_fact"] * 4
    role = next(issue for issue in report.issues if issue.value == "Senior data engineer")
    assert role.message == "Kept the role from your profile."


def test_entries_with_rewritten_ids_are_matched_by_name(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        item = experience(content, "exp-kente")
        item.id = "kente-labs"

    report = check(source, tailor(source, edit))

    assert report.issues == []
    assert experience(report.content, "exp-kente").org == "Kente Labs"


def test_invented_entries_are_removed(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        content.sections[0].experience.append(
            ExperienceItem(
                id="x", org="Stripe", role="Staff engineer", dates=DateRange(start="2014")
            )
        )
        experience(content, "exp-northwind").engagements.append(Engagement(id="y", name="Monzo"))

    report = check(source, tailor(source, edit))

    orgs = [item.org for item in report.content.sections[0].experience]
    assert "Stripe" not in orgs
    clients = [e.name for e in experience(report.content, "exp-northwind").engagements]
    assert "Monzo" not in clients
    assert kinds(report) == ["new_claim", "new_claim"]


def test_stack_entries_must_belong_to_the_same_role(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        # Spark is in Northwind's stack, not Kente's; MySQL is Kente's own.
        experience(content, "exp-kente").stack = ["Java", "mysql", "Spark"]

    report = check(source, tailor(source, edit))

    assert experience(report.content, "exp-kente").stack == ["Java", "mysql"]
    assert [(i.kind, i.value) for i in report.issues] == [("new_skill", "Spark")]


def test_skills_must_be_in_the_profile(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        skills = next(s for s in content.sections if s.kind == "skills")
        skills.skills[0].items = ["python", "Snowflake", "Kafka", "Hadoop"]
        skills.skills.append(SkillGroup(id="g", label="Ops", items=["Kubernetes"]))

    report = check(source, tailor(source, edit))

    skills = next(s for s in report.content.sections if s.kind == "skills")
    # Kafka and Hadoop are mentioned in bullets, so they are the user's skills.
    assert skills.skills[0].items == ["python", "Kafka", "Hadoop"]
    assert [group.label for group in skills.skills] == [
        group.label for group in next(s for s in source.sections if s.kind == "skills").skills
    ]
    assert [(i.kind, i.value) for i in report.issues] == [
        ("new_skill", "Snowflake"),
        ("new_skill", "Kubernetes"),
    ]


def test_contact_details_revert(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        content.basics.name = "Ama Mensah"
        content.basics.email = "ama@other.example"
        content.basics.links = [Link(label="site", url="https://example.org")]  # type: ignore[arg-type]

    report = check(source, tailor(source, edit))

    assert report.content.basics == source.basics
    assert kinds(report) == ["changed_fact"] * 3


def test_headlines_may_be_reworded_but_not_given_numbers(source: CvContent) -> None:
    reworded = check(source, tailor(source, lambda c: setattr(c.basics, "headline", "Data lead")))
    numbered = check(
        source, tailor(source, lambda c: setattr(c.basics, "headline", "Data lead, 15 years"))
    )

    assert reworded.content.basics.headline == "Data lead"
    assert reworded.issues == []
    assert numbered.content.basics.headline == source.basics.headline
    assert kinds(numbered) == ["changed_fact"]


def test_the_summary_may_use_any_number_from_the_profile(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        content.summary = "Led **5 engineers**, moved 140 jobs and cut runtime 62%, over 15 years."

    report = check(source, tailor(source, edit))

    assert report.content.summary.endswith("over [[check this number: 15]] years.")
    assert [(i.kind, i.bullet_id) for i in report.issues] == [("new_number", None)]


def test_education_projects_and_certifications_revert(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        for section in content.sections:
            for item in section.education:
                item.degree = "MSc Computer Science"
            for project in section.projects:
                project.year = "2020"
            for cert in section.certifications:
                cert.issuer = "Someone else"
        content.sections[0].education.append(
            EducationItem(id="z", institution="MIT", degree="PhD", dates=DateRange(start="2010"))
        )
        content.sections[0].certifications.append(
            CertificationItem(id="q", name="CKA", issuer="CNCF")
        )
        content.sections[0].projects.append(ProjectItem(id="w", name="Unicorn"))

    report = check(source, tailor(source, edit))

    def facts(content: CvContent) -> list[tuple[str, ...]]:
        return (
            [(i.institution, i.degree) for s in content.sections for i in s.education]
            + [(p.name, p.year) for s in content.sections for p in s.projects]
            + [(c.name, c.issuer) for s in content.sections for c in s.certifications]
        )

    assert facts(report.content) == facts(source)
    assert kinds(report).count("new_claim") == 3
    # One degree, two project years, two certification issuers.
    assert kinds(report).count("changed_fact") == 5


def test_an_entry_with_a_new_id_and_new_details_cannot_be_matched(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        for section in content.sections:
            for item in section.education:
                item.id = "renamed"
                item.degree = "MSc Computer Science"

    report = check(source, tailor(source, edit))

    assert [i for s in report.content.sections for i in s.education] == []
    assert kinds(report) == ["new_claim"]


def test_bullet_ids_are_made_unique(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        for item in experience(content, "exp-brightline").bullets:
            item.id = "same"

    report = check(source, tailor(source, edit))

    ids = [b.id for b in iter_bullets(report.content)]
    assert len(ids) == len(set(ids))
    assert report.issues == []


def test_the_input_is_not_changed_and_the_result_is_deterministic(source: CvContent) -> None:
    tailored = tailor(source, lambda c: setattr(bullet(c, "b-hb-1"), "text", "Cut 99% of runtime."))
    before = tailored.model_copy(deep=True)

    first, second = check(source, tailored), check(source, tailored)

    assert tailored == before
    assert first == second


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("$4,800 and 62% and 1.2M", {("4800", ""), ("62", "%"), ("1.2", "m")}),
        ("300+ models, 5x faster, 10k users", {("300", "+"), ("5", "x"), ("10", "k")}),
        ("S3, EC2, v2.0, k8s, 3rd", set()),
        ("in 2023.", {("2023", "")}),
    ],
)
def test_number_tokens(text: str, tokens: set[tuple[str, str]]) -> None:
    assert number_tokens(text) == tokens


def test_placeholder_text_cannot_break_out() -> None:
    assert as_placeholder("a ]] b [[c]] **d**") == "[[a ] ] b c d]]"
    assert as_placeholder("**  **") == ""


def test_empty_unsourced_bullets_are_dropped(source: CvContent) -> None:
    def edit(content: CvContent) -> None:
        experience(content, "exp-kente").bullets.append(Bullet(id="empty", text="** **"))

    report = check(source, tailor(source, edit))

    assert [b.id for b in experience(report.content, "exp-kente").bullets] == ["b-kl-1"]
    assert kinds(report) == ["new_claim"]
