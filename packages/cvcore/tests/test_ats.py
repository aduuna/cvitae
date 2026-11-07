import json
from pathlib import Path

import pytest

from cvcore import ats
from cvcore.ai import JobAnalysis
from cvcore.models import Basics, CvContent, ExperienceItem, Section

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"

# What the job analysis makes of templates/fixtures/job-data-engineer.txt.
JOB = JobAnalysis(
    title="Senior Data Engineer, Payments Platform",
    company="Lumen Payments",
    seniority="senior",
    must_have=[
        "5 or more years building data pipelines in production",
        "Strong Python and SQL",
        "Hands-on experience with Spark, Kafka and Airflow",
        "Experience with a cloud data warehouse",
        "Experience in financial services or payments",
    ],
    nice_to_have=["dbt", "Snowflake", "Kubernetes", "Data contracts or schema registries"],
    keywords=[
        "Python",
        "SQL",
        "Spark",
        "Kafka",
        "Airflow",
        "dbt",
        "AWS",
        "Snowflake",
        "Kubernetes",
        "data warehouse",
        "streaming pipelines",
        "financial services",
    ],
    summary="Own batch and streaming pipelines for a payments company.",
)


@pytest.fixture
def sample() -> CvContent:
    return CvContent.model_validate(json.loads((FIXTURES / "profile-sample.json").read_text()))


def job(*keywords: str, title: str = "", must: tuple[str, ...] = ()) -> JobAnalysis:
    return JobAnalysis(
        title=title,
        company="",
        seniority="",
        must_have=list(must),
        nice_to_have=[],
        keywords=list(keywords),
        summary="",
    )


def cv(summary: str = "", *, headline: str = "", role: str = "Engineer") -> CvContent:
    return CvContent(
        basics=Basics(name="Ada", headline=headline),
        summary=summary,
        sections=[
            Section(
                id="s1",
                kind="experience",
                title="Experience",
                experience=[
                    ExperienceItem.model_validate(
                        {"id": "e1", "org": "Acme", "role": role, "dates": {"start": "2020"}}
                    )
                ],
            )
        ],
    )


def found(text: str, term: str, description: str = "") -> bool:
    report = ats.score(cv(text), job(term), description=description)
    return bool(report.keywords[0].found_in)


def by_term(report: ats.AtsReport) -> dict[str, ats.AtsKeyword]:
    return {keyword.term: keyword for keyword in report.keywords}


def test_scores_the_sample_cv_against_the_fixture_job(sample: CvContent) -> None:
    report = ats.score(sample, JOB)

    # Required: Python, SQL, Spark, Kafka, Airflow, financial services found (18 of 21); preferred:
    # dbt (2 of 6); other: AWS (1 of 2); the title (3 of 3). 24 of 32 points.
    assert (report.score, report.band) == (75, "good")
    assert (report.title, report.title_found) == ("Data Engineer", True)
    keywords = by_term(report)
    assert [k.importance for k in report.keywords] == ["required"] * 7 + ["preferred"] * 3 + [
        "other"
    ] * 2
    assert keywords["Python"].found_in == ["experience", "projects", "skills"]
    assert keywords["SQL"].found_in == ["skills"]  # PostgreSQL and MySQL are other words
    assert keywords["AWS"].found_in == ["experience", "skills", "certifications"]
    assert keywords["financial services"].found_in == ["experience"]  # "financial-services"
    assert keywords["data warehouse"].found_in == []  # "first warehouse": literal, like a search
    assert keywords["Snowflake"].found_in == []
    assert all(k.in_profile is None for k in report.keywords)


def test_missing_keywords_are_looked_up_in_the_profile(sample: CvContent) -> None:
    tailored = sample.model_copy(deep=True)
    tailored.sections = [s for s in tailored.sections if s.kind != "skills"]

    keywords = by_term(ats.score(tailored, JOB, profile=sample))

    assert (keywords["SQL"].found_in, keywords["SQL"].in_profile) == ([], True)
    assert (keywords["Snowflake"].found_in, keywords["Snowflake"].in_profile) == ([], False)
    assert keywords["Python"].in_profile is None  # found, so not looked up


def test_a_user_title_overrides_the_analysed_one(sample: CvContent) -> None:
    report = ats.score(sample, JOB, title="Analytics Engineer")

    assert (report.title, report.title_found) == ("Analytics Engineer", False)


def test_the_title_counts_in_the_headline_or_a_role_only() -> None:
    analysis = job(title="Data Engineer")

    assert ats.score(cv(headline="Senior data engineer"), analysis).title_found
    assert ats.score(cv(role="Data Engineer II"), analysis).title_found
    assert not ats.score(cv("Data engineer with 9 years"), analysis).title_found


@pytest.mark.parametrize(
    ("text", "term", "expected"),
    [
        ("Built services in JavaScript.", "Java", False),
        ("Built services in Java.", "JAVA", True),
        ("Ran batch pipelines.", "Pipeline", True),
        ("Owned the data pipeline.", "data pipelines", True),
        ("Led cost optimisation.", "Optimization", True),
        ("Modelling and analysing churn.", "modeling", True),
        ("Wrote C and Rust.", "C++", False),
        ("Wrote C++ services.", "C++", True),
        ("APIs on Node.js.", "Node.js", True),
        ("APIs on Node.js.", "API", True),
        ("Shipped CI/CD for 40 services.", "CI/CD", True),
        ("Ran the platform team.", "data platform", False),
    ],
)
def test_matching_is_literal_on_whole_words(text: str, term: str, expected: bool) -> None:
    assert found(text, term) is expected


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("Front ends in JS and TypeScript.", "JavaScript"),
        ("Ran K8s clusters.", "Kubernetes"),
        ("Migrated to Postgres.", "PostgreSQL"),
        ("Certified on Amazon Web Services.", "AWS"),
        ("Batch jobs on Spark.", "Apache Spark"),
        ("Built ML features.", "machine learning"),
    ],
)
def test_known_short_forms_match(text: str, term: str) -> None:
    assert found(text, term)


def test_abbreviations_the_ad_spells_out_match() -> None:
    ad = "You will own our Key Performance Indicators (KPIs) and the Total Cost of Ownership (TCO)."

    assert found("Defined the team's KPIs.", "Key Performance Indicators", ad)
    assert found("Cut the total cost of ownership by a third.", "TCO", ad)
    assert not found("Cut the total cost of ownership by a third.", "TCO")
    # The initials must spell the abbreviation.
    assert not found("Ran the plan.", "PRS", "Plan of Record (PRS)")


def test_placeholders_are_not_content() -> None:
    assert not found("Led the [[Kafka migration]].", "Kafka")
    assert found("Led the **Kafka** migration.", "Kafka")


def test_the_same_keyword_counts_once() -> None:
    report = ats.score(cv("AWS"), job("AWS", "Amazon Web Services", "aws", " ", "Spark"))

    assert [k.term for k in report.keywords] == ["AWS", "Spark"]
    assert report.score == 50


def test_importance_comes_from_the_requirements() -> None:
    analysis = JobAnalysis(
        title="",
        company="",
        seniority="",
        must_have=["Strong Python"],
        nice_to_have=["Some Go"],
        keywords=["Go", "Rust", "Python"],
        summary="",
    )

    report = ats.score(cv("Python and Rust"), analysis)

    assert [(k.term, k.importance) for k in report.keywords] == [
        ("Python", "required"),
        ("Go", "preferred"),
        ("Rust", "other"),
    ]
    assert report.score == 100 * 4 // 6


@pytest.mark.parametrize(
    ("hits", "score", "band"),
    [
        (0, 0, "limited"),
        (1, 25, "limited"),
        (2, 50, "partial"),
        (3, 75, "good"),
        (4, 100, "strong"),
    ],
)
def test_bands(hits: int, score: int, band: str) -> None:
    terms = ["Rust", "Go", "Scala", "Elixir"]

    report = ats.score(cv(" ".join(terms[:hits])), job(*terms))

    assert (report.score, report.band) == (score, band)


def test_nothing_to_match_has_no_score() -> None:
    report = ats.score(cv("Python"), job())

    assert (report.score, report.band, report.title, report.keywords) == (None, None, "", [])


@pytest.mark.parametrize(
    ("title", "core"),
    [
        ("Senior Data Engineer, Payments Platform", "Data Engineer"),
        ("Lead Software Engineer - Payments", "Software Engineer"),
        ("Data Engineer \N{EN DASH} Remote", "Data Engineer"),
        ("Head of Data", "Data"),
        ("Staff Engineer II (Remote)", "Engineer"),
        ("Product Manager at Acme", "Product Manager"),
        ("Sr. Analyst", "Analyst"),
        ("Senior", "Senior"),
        ("", ""),
    ],
)
def test_core_title(title: str, core: str) -> None:
    assert ats.core_title(title) == core


def test_checks_pass_for_the_sample_cv(sample: CvContent) -> None:
    sample.sections[0].experience[0].engagements[0].bullets[1].text = "Built a pipeline."

    checks = ats.checks(sample, pages=1, target_pages=1)

    assert [(c.id, c.ok) for c in checks] == [
        ("contact", True),
        ("headings", True),
        ("placeholders", True),
        ("length", True),
    ]
    assert checks[3].message == "Fits on 1 page."


def test_checks_say_what_to_fix(sample: CvContent) -> None:
    sample.basics.phone = ""
    sample.basics.location = " "
    sample.sections[0].title = "Where I have worked"
    sample.sections[3].title = "Things I know"

    checks = {c.id: c for c in ats.checks(sample, pages=3, target_pages=2)}

    assert not checks["contact"].ok
    assert checks["contact"].message == (
        "Add your phone and location to the header, where parsers look for them."
    )
    assert checks["headings"].message == (
        'Rename "Where I have worked" and "Things I know" to a title parsers recognise, such as '
        '"Experience" and "Skills".'
    )
    assert checks["placeholders"].message == (
        "Fill in 1 placeholder. A parser reads them as they are written."
    )
    assert checks["length"].message == "Runs to 3 pages, over this template's 2 pages."


def test_custom_sections_take_any_title_and_length_needs_both_counts(sample: CvContent) -> None:
    sample.sections[-1].title = "Spoken"

    checks = ats.checks(sample, pages=2)

    assert [c.id for c in checks] == ["contact", "headings", "placeholders"]
    assert checks[1].ok
