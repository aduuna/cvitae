import pytest

from cvcore.models import CvContent


@pytest.fixture
def content() -> CvContent:
    return CvContent.model_validate(
        {
            "basics": {
                "name": "Ada Lovelace",
                "headline": "Data engineer",
                "links": [{"label": "GitHub", "url": "https://github.com/ada"}],
            },
            "summary": "Engineer with **9 years** of experience and [[main domain]] focus.",
            "sections": [
                {
                    "id": "s1",
                    "kind": "experience",
                    "title": "Experience",
                    "experience": [
                        {
                            "id": "e1",
                            "org": "Acme",
                            "role": "Engineer",
                            "dates": {"start": "2021-03"},
                            "stack": ["Python"],
                            "bullets": [
                                {"id": "b1", "text": "Cut costs by **40%**", "source_id": "x"},
                                {"id": "b2", "text": "Served [[number of users]] users"},
                            ],
                            "engagements": [
                                {
                                    "id": "g1",
                                    "name": "Barclays",
                                    "bullets": [{"id": "b3", "text": "Built [[what]]"}],
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": "s2",
                    "kind": "projects",
                    "title": "Projects",
                    "projects": [
                        {"id": "p1", "name": "Vitae", "bullets": [{"id": "b4", "text": "Typst"}]}
                    ],
                },
                {
                    "id": "s3",
                    "kind": "custom",
                    "title": "Awards",
                    "custom": [{"id": "b5", "text": "Best paper"}],
                },
            ],
        }
    )
