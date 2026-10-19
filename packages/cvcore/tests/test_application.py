import json
from pathlib import Path

import pytest

from cvcore.application import (
    YearMonth,
    classify_links,
    degree_field,
    degree_level,
    parse_date,
    split_name,
    to_application_data,
)
from cvcore.models import CvContent

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"


@pytest.fixture
def sample() -> CvContent:
    return CvContent.model_validate(json.loads((FIXTURES / "profile-sample.json").read_text()))


def test_sample_profile(sample: CvContent) -> None:
    data = to_application_data(sample)

    assert data.name.model_dump() == {
        "full": "Ama Owusu-Mensah",
        "first": "Ama",
        "middle": "",
        "last": "Owusu-Mensah",
    }
    assert (data.email, data.phone) == ("ama@example.com", "+44 20 7946 0958")
    assert (data.location.city, data.location.country, data.location.country_code) == (
        "London",
        "United Kingdom",
        "GB",
    )
    assert data.links.github == "https://github.com/example"
    assert data.links.linkedin == "https://www.linkedin.com/in/example"
    assert data.summary.startswith("Data engineer with 9 years of experience")
    assert (data.current_company, data.current_title) == (
        "Northwind Consulting",
        "Lead data engineer",
    )
    assert [role.company for role in data.experience] == [
        "Northwind Consulting",
        "Brightline Analytics",
        "Kente Labs",
    ]
    assert data.education[0].model_dump() == {
        "id": "edu-ug",
        "institution": "University of Ghana",
        "degree": "BSc Computer Science",
        "level": "bachelor",
        "field": "Computer Science",
        "location": "Legon, Ghana",
        "start": {"year": 2011, "month": 9},
        "end": {"year": 2015, "month": 6},
    }
    assert data.certifications[1].model_dump() == {
        "name": "Solutions Architect Associate",
        "issuer": "Amazon Web Services",
        "date": "2022",
    }
    # The sample has one placeholder, in a client engagement's bullet.
    assert data.placeholders == 1


def test_role_description_has_bullets_then_engagements(sample: CvContent) -> None:
    role = to_application_data(sample).experience[0]

    assert role.current is True
    assert role.start == YearMonth(year=2021, month=3)
    assert role.end is None
    assert role.description.splitlines() == [
        "- Lead a team of 5 engineers delivering data platforms for financial-services clients.",
        "",
        "Client: Harbour Bank, London, UK",
        "- Migrated 140 nightly batch jobs from on-premise Hadoop to Spark on EMR, cutting runtime"
        " by 62%.",
        "- Built a streaming fraud-signal pipeline on Kafka that serves [[number of analysts]]"
        " analysts.",
        "",
        "Client: Meridian Retail, Manchester, UK",
        "- Designed a dbt project of 300+ models with tests and documentation that analysts now"
        " extend themselves.",
    ]


def test_past_role(sample: CvContent) -> None:
    role = to_application_data(sample).experience[1]

    assert role.current is False
    assert role.end == YearMonth(year=2021, month=2)
    assert role.stack == ["Python", "PostgreSQL", "Airflow", "GCP"]


def test_skills_are_groups_then_stacks_without_repeats(sample: CvContent) -> None:
    skills = to_application_data(sample).skills

    assert skills[:4] == ["Python", "SQL", "Scala", "C#"]
    assert skills.count("Python") == 1
    assert "PostgreSQL" in skills
    assert "MySQL" in skills


def test_counts_placeholders_in_summary_and_bullets(content: CvContent) -> None:
    data = to_application_data(content)

    assert data.summary == "Engineer with 9 years of experience and [[main domain]] focus."
    assert data.placeholders == 3


def test_no_current_role() -> None:
    content = CvContent.model_validate(
        {
            "basics": {"name": "Ada"},
            "sections": [
                {
                    "id": "s",
                    "kind": "experience",
                    "title": "Experience",
                    "experience": [
                        {
                            "id": "e",
                            "org": "Acme",
                            "role": "Engineer",
                            "dates": {"start": "2020", "end": "2021"},
                        }
                    ],
                }
            ],
        }
    )
    data = to_application_data(content)

    assert (data.current_company, data.current_title) == ("", "")
    assert data.experience[0].start == YearMonth(year=2020)
    assert data.experience[0].description == ""
    assert data.name.first == "Ada"
    assert data.name.last == ""


@pytest.mark.parametrize(
    ("name", "parts"),
    [
        ("", ("", "", "", "")),
        ("Ada", ("Ada", "Ada", "", "")),
        ("Ada Lovelace", ("Ada Lovelace", "Ada", "", "Lovelace")),
        (
            "  Vincent  Aduuna Frimpong ",
            ("Vincent Aduuna Frimpong", "Vincent", "Aduuna", "Frimpong"),
        ),
    ],
)
def test_split_name(name: str, parts: tuple[str, str, str, str]) -> None:
    split = split_name(name)

    assert (split.full, split.first, split.middle, split.last) == parts


def test_classify_links() -> None:
    links = classify_links(
        [
            "https://uk.linkedin.com/in/ada",
            "https://ada.dev/",
            "https://x.com/ada",
            "https://github.com/ada",
            "https://github.com/ada-work",
            "https://blog.ada.dev/",
            "https://gitlab.com/ada",
            "https://stackoverflow.com/users/1/ada",
        ]
    )

    assert links.model_dump() == {
        "linkedin": "https://uk.linkedin.com/in/ada",
        "github": "https://github.com/ada",
        "gitlab": "https://gitlab.com/ada",
        "twitter": "https://x.com/ada",
        "stackoverflow": "https://stackoverflow.com/users/1/ada",
        "website": "https://ada.dev/",
        "other": ["https://github.com/ada-work", "https://blog.ada.dev/"],
    }


def test_a_lookalike_host_is_not_the_site() -> None:
    assert classify_links(["https://notgithub.com/ada"]).website == "https://notgithub.com/ada"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2024-01", YearMonth(year=2024, month=1)),
        ("2024-1", YearMonth(year=2024, month=1)),
        ("2024", YearMonth(year=2024)),
        ("2024-13", YearMonth(year=2024)),
        ("Jan 2024", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_date(text: str | None, expected: YearMonth | None) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    ("degree", "level", "field"),
    [
        ("BSc Computer Science", "bachelor", "Computer Science"),
        ("B.Sc. Computer Science", "bachelor", "Computer Science"),
        ("BSc (Hons) Software Engineering", "bachelor", "Software Engineering"),
        ("BA, Economics", "bachelor", "Economics"),
        ("Bachelor of Science in Physics", "bachelor", "Physics"),
        ("Bachelor of Arts", "bachelor", ""),
        (
            "Bachelor's degree in Mathematics and Statistics",
            "bachelor",
            "Mathematics and Statistics",
        ),
        ("MSc Data Science", "master", "Data Science"),
        ("Master of Engineering", "master", ""),
        ("MBA", "master", ""),
        (
            "MEng Electrical and Electronic Engineering",
            "master",
            "Electrical and Electronic Engineering",
        ),
        ("PhD in Machine Learning", "doctorate", "Machine Learning"),
        ("DPhil Statistics", "doctorate", "Statistics"),
        ("Associate of Arts", "associate", ""),
        ("WASSCE", "high_school", ""),
        ("A-levels", "high_school", ""),
        ("Certificate in Data Analysis", "", "Data Analysis"),
        ("Bootcamp", "", ""),
    ],
)
def test_degree_level_and_field(degree: str, level: str, field: str) -> None:
    assert (degree_level(degree), degree_field(degree)) == (level, field)
