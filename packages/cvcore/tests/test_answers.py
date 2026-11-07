import json
from pathlib import Path

import pytest

from cvcore.ai import SkillMention
from cvcore.answers import (
    Limits,
    Material,
    finish,
    fit,
    for_drafting,
    guard_numbers,
    inferred_skills,
    tidy,
    word_count,
)
from cvcore.models import CvContent

FIXTURES = Path(__file__).resolve().parents[3] / "templates" / "fixtures"


@pytest.fixture
def sample() -> CvContent:
    return CvContent.model_validate(json.loads((FIXTURES / "profile-sample.json").read_text()))


@pytest.fixture
def material(sample: CvContent) -> Material:
    return Material(sample, ad="We run 40 pipelines across 3 regions.")


def test_drafting_leaves_out_contact_details(sample: CvContent) -> None:
    drafted = for_drafting(sample)

    assert (drafted.basics.email, drafted.basics.phone, drafted.basics.links) == ("", "", [])
    assert drafted.basics.name == sample.basics.name
    assert drafted.sections == sample.sections
    assert sample.basics.email, "the source is not changed"


def test_material_mentions_skills_stack_and_text(material: Material) -> None:
    assert material.mentions("Kafka")  # a skill
    assert material.mentions("postgresql")  # a stack entry, any case
    assert material.mentions("Harbour Bank")  # a client
    assert material.mentions("BigQuery")
    assert not material.mentions("Databricks")
    assert not material.mentions("Snow")  # whole words only
    assert not material.mentions("  ")


def test_ad_counts_for_numbers_not_skills(sample: CvContent) -> None:
    material = Material(sample, ad="Experience with Databricks; 40 pipelines.")

    assert not material.mentions("Databricks")
    assert ("40", "") in material.numbers


def test_tidy_drops_bold_and_extra_space() -> None:
    text = "  I **led** the   move.\n\n\n\nThen   more.\n- one\n- two  "

    assert tidy(text) == "I led the move.\n\nThen more.\n- one\n- two"
    assert tidy(text, multiline=False) == "I led the move. Then more. - one - two"


def test_tidy_replaces_em_dashes() -> None:
    assert tidy("I run Airflow \u2014 backfills and partitions.") == (
        "I run Airflow, backfills and partitions."
    )


def test_numbers_the_material_gives_stay(material: Material) -> None:
    allowed = material.numbers

    assert guard_numbers("A team of 5 engineers and 12 systems.", allowed) == (
        "A team of 5 engineers and 12 systems."
    )
    assert guard_numbers("Since 2017, and $4,800 a month.", allowed) == (
        "Since 2017, and $4,800 a month."
    )
    assert guard_numbers("We have 40 pipelines.", allowed) == "We have 40 pipelines."


def test_new_numbers_become_placeholders(material: Material) -> None:
    text = guard_numbers("I built 170 dbt models and cut costs by 35%.", material.numbers)

    assert text == (
        "I built [[check this number: 170]] dbt models and cut costs by [[check this number: 35%]]."
    )


def test_placeholders_and_names_with_digits_are_left_alone(material: Material) -> None:
    text = "I moved [[how many]] jobs to S3 and EC2, about [[200 models]]."

    assert guard_numbers(text, material.numbers) == text


def test_fit_drops_whole_sentences() -> None:
    text = "One two three. Four five six. Seven eight nine."

    assert fit(text, Limits(max_words=7)) == ("One two three. Four five six.", True)
    assert fit(text, Limits(max_chars=20)) == ("One two three.", True)
    assert fit(text, Limits(max_words=9)) == (text, False)
    assert fit(text, Limits()) == (text, False)


def test_fit_cuts_one_long_sentence_at_a_word() -> None:
    text = "I moved every nightly batch job to incremental models over two quarters"

    fitted, shortened = fit(text, Limits(max_words=5))
    assert (fitted, shortened) == ("I moved every nightly batch", True)
    fitted, _ = fit(text, Limits(max_chars=30))
    assert fitted == "I moved every nightly batch"
    assert len(fitted) <= 30


def test_fit_never_leaves_half_a_placeholder() -> None:
    fitted, _ = fit("I cut the run time by [[how many minutes]] each night", Limits(max_words=7))

    assert fitted == "I cut the run time by"


def test_word_count() -> None:
    assert word_count("  one two\n\nthree ") == 3
    assert word_count("") == 0


def test_inferred_skills_are_named_ones_the_material_lacks(material: Material) -> None:
    text = "At Northwind I ran Spark jobs on Databricks and modelled them in dbt with Looker."
    skills = [
        SkillMention(skill="Databricks", based_on=["Spark", "Airflow", "Cobol"]),
        SkillMention(skill="dbt", based_on=[]),  # in the material
        SkillMention(skill="Snowflake", based_on=["BigQuery"]),  # not in the answer
    ]

    found = inferred_skills(text, skills, material, keywords=["Looker", "databricks", "Kafka"])

    assert [(s.skill, s.based_on) for s in found] == [
        ("Databricks", ["Spark", "Airflow"]),  # Cobol is not in the material
        ("Looker", []),  # a job keyword the model did not report
    ]


def test_inferred_skills_are_capped(material: Material) -> None:
    names = ["Looker", "Tableau", "Dagster", "Prefect", "Flink", "Druid"]
    skills = [SkillMention(skill=name, based_on=["Spark"]) for name in names]

    found = inferred_skills(" ".join(names), skills, material)

    assert [s.skill for s in found] == names[:5]


def test_finish(material: Material) -> None:
    answer = finish(
        "f12",
        "At **Northwind** I moved 170 Spark jobs to Databricks.\n\nIt took [[how long]].",
        [SkillMention(skill="Databricks", based_on=["Spark"])],
        question="Describe a time you used Databricks, in 200 words.",
        limits=Limits(max_words=200),
        material=material,
    )

    assert answer.model_dump() == {
        "id": "f12",
        "text": (
            "At Northwind I moved [[check this number: 170]] Spark jobs to Databricks.\n\n"
            "It took [[how long]]."
        ),
        "inferred": [{"skill": "Databricks", "based_on": ["Spark"]}],
        "placeholders": 2,
        "shortened": False,
    }


def test_finish_allows_numbers_from_the_question(material: Material) -> None:
    answer = finish(
        "q",
        "I would start within 90 days.",
        [],
        question="What would you do in your first 90 days?",
        limits=Limits(multiline=False, max_chars=20),
        material=material,
    )

    assert (answer.text, answer.shortened, answer.placeholders) == ("I would start within", True, 0)


def test_finish_with_no_draft(material: Material) -> None:
    answer = finish("q", "", [], question="Why us?", limits=Limits(), material=material)

    assert (answer.text, answer.inferred, answer.placeholders) == ("", [], 0)
