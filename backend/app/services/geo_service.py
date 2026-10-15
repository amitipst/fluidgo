"""Address validation shared by companies (and later leads/opportunities).
Data lives in geo_data.py; this module only applies the rules."""
import re
from typing import Optional

from app.services.geo_data import COUNTRIES, STATES, POSTAL_RULES, POSTAL_GENERIC

COUNTRY_CODES = {c for c, _ in COUNTRIES}


def geo_payload() -> dict:
    return {"countries": [{"code": c, "name": n} for c, n in COUNTRIES],
            "states": STATES,
            "postal_hints": {**{c: h for c, (_, h) in POSTAL_RULES.items()}, "_default": POSTAL_GENERIC[1]},
            "postal_patterns": {**{c: p for c, (p, _) in POSTAL_RULES.items()}, "_default": POSTAL_GENERIC[0]}}


def normalize_postal(country: Optional[str], postal: Optional[str]) -> Optional[str]:
    """Validate + tidy a postal/ZIP code for the country; raises ValueError."""
    p = " ".join((postal or "").split())
    if not p:
        return None
    pattern, hint = POSTAL_RULES.get((country or "").upper(), POSTAL_GENERIC)
    if not re.match(pattern, p):
        raise ValueError(f"Postal code is not valid for this country ({hint})")
    return p.upper() if (country or "").upper() in ("GB", "CA") else p


def validate_address(fields: dict) -> dict:
    """fields: any of address_line1/2, city, state, country, postal_code.
    Returns the cleaned subset; raises ValueError with a readable message.
    A country is required as soon as any other address part is given."""
    out = {}
    for k in ("address_line1", "address_line2", "city", "state"):
        if k in fields:
            v = " ".join((fields.get(k) or "").split())
            out[k] = v or None
    country = fields.get("country")
    country = (country or "").strip().upper() or None
    if country and country not in COUNTRY_CODES:
        raise ValueError("Choose a country from the list")
    any_part = any(out.get(k) for k in out) or fields.get("postal_code")
    if any_part and not country:
        raise ValueError("Select a country for the address")
    if "country" in fields:
        out["country"] = country
    if country in STATES and out.get("state") and out["state"] not in STATES[country]:
        raise ValueError("Choose a state from the list")
    if "postal_code" in fields:
        out["postal_code"] = normalize_postal(country, fields.get("postal_code"))
    return out
