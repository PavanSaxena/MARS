"""Country normalization and legal provider resolution."""
from typing import Any

from .base import LegalProvider, LegalProviderError
from .india import IndiaCodeProvider

PROVIDERS: dict[str, LegalProvider] = {"IN": IndiaCodeProvider()}
COUNTRIES = {
    "IN": "India", "INDIA": "India", "DE": "Germany", "GERMANY": "Germany",
    "UK": "United Kingdom", "GB": "United Kingdom", "UNITED KINGDOM": "United Kingdom",
    "US": "United States", "USA": "United States", "UNITED STATES": "United States",
    "FR": "France", "FRANCE": "France", "CA": "Canada", "CANADA": "Canada",
    "AU": "Australia", "AUSTRALIA": "Australia", "JP": "Japan", "JAPAN": "Japan",
    "BR": "Brazil", "BRAZIL": "Brazil", "CN": "China", "CHINA": "China",
    "RU": "Russia", "RUSSIA": "Russia", "ZA": "South Africa", "SOUTH AFRICA": "South Africa",
    "SG": "Singapore", "SINGAPORE": "Singapore", "NZ": "New Zealand", "NEW ZEALAND": "New Zealand",
    "MX": "Mexico", "MEXICO": "Mexico", "CH": "Switzerland", "SWITZERLAND": "Switzerland",
    "AQ": "Antarctica", "ANTARCTICA": "Antarctica",
}
ISO_CODES = set("AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split())


def normalize_country(country: str) -> tuple[str | None, str]:
    key = " ".join((country or "").strip().upper().replace("_", " ").split())
    name = COUNTRIES.get(key)
    if name:
        code = next((c for c, n in COUNTRIES.items() if len(c) == 2 and n == name), None)
        return code, name
    if len(key) == 2 and key in ISO_CODES:
        return key, key
    return None, ""


def get_provider_for_country(code: str) -> LegalProvider | None:
    return PROVIDERS.get(code.upper())


def resolve_country(country: str) -> dict[str, Any]:
    code, name = normalize_country(country)
    if not code:
        return {"status": "unrecognized", "country": country, "supported": []}
    provider = get_provider_for_country(code)
    return {"status": "supported" if provider else "unsupported", "code": code,
            "country": name, "provider": provider}


def list_supported_jurisdictions() -> dict[str, Any]:
    return {"supported": [{"country": p.jurisdiction, "provider": p.source_name,
                            "authority_level": p.authority_level,
                            "covers": ["statutes", "subordinate_legislation"]}
                           for p in PROVIDERS.values()],
            "fallback_available": True, "fallback_authority": "secondary"}


__all__ = ["PROVIDERS", "LegalProvider", "LegalProviderError", "resolve_country",
           "normalize_country", "get_provider_for_country", "list_supported_jurisdictions"]
