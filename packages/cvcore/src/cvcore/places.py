"""Countries and US states by name, code and common spelling, to read a free-text location such as
"London, UK" into city, region and country. Application forms often ask for a country from a list,
so each match also carries the spellings a list might use."""

import re
from dataclasses import dataclass

# ISO 3166-1 alpha-2 code and short English name.
COUNTRIES: dict[str, str] = {
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AG": "Antigua and Barbuda",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BN": "Brunei",
    "BO": "Bolivia",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CD": "Democratic Republic of the Congo",
    "CF": "Central African Republic",
    "CG": "Republic of the Congo",
    "CH": "Switzerland",
    "CI": "Côte d'Ivoire",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cabo Verde",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DM": "Dominica",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FM": "Micronesia",
    "FR": "France",
    "GA": "Gabon",
    "GB": "United Kingdom",
    "GD": "Grenada",
    "GE": "Georgia",
    "GH": "Ghana",
    "GM": "Gambia",
    "GN": "Guinea",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GT": "Guatemala",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HK": "Hong Kong",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros",
    "KN": "Saint Kitts and Nevis",
    "KP": "North Korea",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KZ": "Kazakhstan",
    "LA": "Laos",
    "LB": "Lebanon",
    "LC": "Saint Lucia",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MG": "Madagascar",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macao",
    "MR": "Mauritania",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NE": "Niger",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PR": "Puerto Rico",
    "PS": "Palestine",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "Sao Tome and Principe",
    "SV": "El Salvador",
    "SY": "Syria",
    "SZ": "Eswatini",
    "TD": "Chad",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TL": "Timor-Leste",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "Turkey",
    "TT": "Trinidad and Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "UG": "Uganda",
    "US": "United States",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VA": "Vatican City",
    "VC": "Saint Vincent and the Grenadines",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "VU": "Vanuatu",
    "WS": "Samoa",
    "XK": "Kosovo",
    "YE": "Yemen",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

# Other spellings people write, and that country lists use.
COUNTRY_ALIASES: dict[str, tuple[str, ...]] = {
    "AE": ("UAE", "U.A.E.", "Emirates"),
    "BN": ("Brunei Darussalam",),
    "CD": ("DRC", "DR Congo", "Congo-Kinshasa", "Congo, Democratic Republic of the"),
    "CG": ("Congo", "Congo-Brazzaville", "Congo, Republic of the"),
    "CI": ("Ivory Coast", "Cote d'Ivoire"),
    "CN": ("People's Republic of China", "PRC"),
    "CV": ("Cape Verde",),
    "CZ": ("Czech Republic",),
    "FM": ("Federated States of Micronesia",),
    "GB": (
        "UK",
        "U.K.",
        "Great Britain",
        "Britain",
        "England",
        "Scotland",
        "Wales",
        "Northern Ireland",
        "United Kingdom of Great Britain and Northern Ireland",
    ),
    "HK": ("Hong Kong SAR",),
    "IR": ("Islamic Republic of Iran",),
    "KP": ("DPRK",),
    "KR": ("Korea", "Republic of Korea", "Korea, Republic of"),
    "LA": ("Lao PDR", "Lao People's Democratic Republic"),
    "MD": ("Republic of Moldova",),
    "MK": ("Macedonia",),
    "MM": ("Burma",),
    "MO": ("Macau",),
    "NL": ("The Netherlands", "Holland"),
    "PS": ("State of Palestine",),
    "RU": ("Russian Federation",),
    "SA": ("KSA",),
    "ST": ("São Tomé and Príncipe",),
    "SY": ("Syrian Arab Republic",),
    "SZ": ("Swaziland",),
    "TL": ("East Timor",),
    "TR": ("Türkiye", "Turkiye"),
    "TZ": ("United Republic of Tanzania",),
    "US": ("USA", "U.S.", "U.S.A.", "United States of America", "America"),
    "VA": ("Holy See",),
    "VE": ("Bolivarian Republic of Venezuela",),
    "VN": ("Viet Nam",),
}

US_STATES: dict[str, str] = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

# Locations that name no place.
_NOT_A_CITY = {"remote", "anywhere", "worldwide", "hybrid"}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _country_index() -> dict[str, str]:
    """Names and aliases. Two-letter codes are looked up separately, in capitals only."""
    index: dict[str, str] = {}
    for code, name in COUNTRIES.items():
        index[_key(name)] = code
        for alias in COUNTRY_ALIASES.get(code, ()):
            index[_key(alias)] = code
    return index


_COUNTRY_BY_KEY = _country_index()
_STATE_BY_NAME = {_key(name): code for code, name in US_STATES.items()}


@dataclass(frozen=True)
class Country:
    code: str
    name: str

    @property
    def spellings(self) -> list[str]:
        """The name, the code and the aliases, for matching an option in a country list."""
        return [self.name, self.code, *COUNTRY_ALIASES.get(self.code, ())]


@dataclass(frozen=True)
class Place:
    full: str
    city: str = ""
    region: str = ""
    region_names: tuple[str, ...] = ()
    country: Country | None = None


def _is_code(text: str) -> bool:
    return re.fullmatch(r"[A-Z]{2}", text) is not None


def find_country(text: str, *, codes: bool = True) -> Country | None:
    """A country from its name or an alias, or (with `codes`) its ISO code in capitals."""
    text = text.strip()
    code = _COUNTRY_BY_KEY.get(_key(text))
    if code is None and codes and _is_code(text) and text in COUNTRIES:
        code = text
    return Country(code, COUNTRIES[code]) if code else None


def _us_state(text: str) -> str | None:
    text = text.strip()
    if _is_code(text):
        return text if text in US_STATES else None
    return _STATE_BY_NAME.get(_key(text))


def parse_place(location: str) -> Place:
    """Split "City, Region, Country" as people write it. Unrecognised parts stay as written.

    The last part is read, in order, as a country name, a US state ("Austin, TX": state codes
    clash with country codes, and "City, ST" is the common US form), then a country code. A US
    state implies the United States. A name that is both, like Georgia, reads as the country."""
    full = location.strip()
    parts = [part.strip() for part in re.split(r"[,;]", full) if part.strip()]
    if not parts:
        return Place(full="")

    country = find_country(parts[-1], codes=False)
    if country:
        parts.pop()
    region = ""
    region_names: tuple[str, ...] = ()
    state = _us_state(parts[-1]) if parts and (country is None or country.code == "US") else None
    # A lone part is a state only when it is spelled out: "IN" alone is more likely India.
    if state and (len(parts) > 1 or not _is_code(parts[-1]) or country is not None):
        region = parts.pop()
        region_names = (region, state, US_STATES[state])
        country = country or Country("US", COUNTRIES["US"])
    elif country is None and parts:
        country = find_country(parts[-1])
        if country:
            parts.pop()
    city = parts[0] if parts else ""
    if not region and len(parts) > 1:
        region = parts[1]
        region_names = (region,)
    if _key(city) in _NOT_A_CITY:
        city = ""
    return Place(
        full=full,
        city=city,
        region=region,
        region_names=tuple(dict.fromkeys(region_names)),
        country=country,
    )
