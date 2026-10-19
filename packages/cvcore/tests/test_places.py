import pytest

from cvcore.places import COUNTRIES, COUNTRY_ALIASES, US_STATES, find_country, parse_place


def summary(location: str) -> tuple[str, str, str]:
    place = parse_place(location)
    return place.city, place.region, place.country.code if place.country else ""


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("London, UK", ("London", "", "GB")),
        ("Accra, Ghana", ("Accra", "", "GH")),
        ("Kumasi, Ashanti, Ghana", ("Kumasi", "Ashanti", "GH")),
        ("Paris; France", ("Paris", "", "FR")),
        ("Austin, TX", ("Austin", "TX", "US")),
        ("Austin, TX, USA", ("Austin", "TX", "US")),
        ("San Francisco, CA", ("San Francisco", "CA", "US")),
        ("Brooklyn, New York, United States", ("Brooklyn", "New York", "US")),
        ("Texas", ("", "Texas", "US")),
        ("Ghana", ("", "", "GH")),
        ("IN", ("", "", "IN")),
        ("Berlin, Brandenburg", ("Berlin", "Brandenburg", "")),
        ("Lagos", ("Lagos", "", "")),
        ("Remote", ("", "", "")),
        ("Remote, UK", ("", "", "GB")),
        ("  ", ("", "", "")),
    ],
)
def test_parse_place(location: str, expected: tuple[str, str, str]) -> None:
    assert summary(location) == expected


def test_place_keeps_what_was_written() -> None:
    place = parse_place("  Austin, TX  ")

    assert place.full == "Austin, TX"
    assert place.region_names == ("TX", "Texas")


def test_georgia_reads_as_the_country() -> None:
    """Both a country and a US state; the code form is the unambiguous US one."""
    assert summary("Tbilisi, Georgia") == ("Tbilisi", "", "GE")
    assert summary("Atlanta, GA") == ("Atlanta", "GA", "US")


def test_country_spellings_include_code_and_aliases() -> None:
    country = find_country("U.K.")

    assert country is not None
    assert country.spellings[:2] == ["United Kingdom", "GB"]
    assert "Great Britain" in country.spellings


def test_codes_match_in_capitals_only() -> None:
    assert find_country("GH") is not None
    assert find_country("gh") is None
    assert find_country("GH", codes=False) is None


def test_tables_are_consistent() -> None:
    assert all(len(code) == 2 and code.isupper() for code in COUNTRIES)
    assert set(COUNTRY_ALIASES) <= set(COUNTRIES)
    assert len(US_STATES) == 51
    assert len(set(COUNTRIES.values())) == len(COUNTRIES)
