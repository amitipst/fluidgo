"""Pure helpers for scripts/backfill_company_links.py (v1.5.0).

Turns the free-text company / person strings on old leads and deals into
Companies and Contacts in the Contacts master. Kept free of DB access so the
rules are unit-testable. Nothing here merges two differently-spelled customers:
"Sunpack Group" and "Sunpack Systems" become two companies and are reported as
a possible duplicate for a person to merge/rename in Contacts.
"""
import difflib
import re
from collections import Counter

_SUFFIX = re.compile(r"\b(pvt|private|ltd|limited|inc|llp|llc|corp|corporation|co|company)\b\.?", re.I)
_TITLE = re.compile(r"\b(mr|mrs|ms|dr|shri|smt)\b\.?", re.I)
_PLACEHOLDER = {"", "na", "n a", "none", "nil", "tbd", "unknown", "test", "-"}


def norm_company(s: str) -> str:
    s = _SUFFIX.sub(" ", (s or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def norm_person(s: str) -> str:
    s = _TITLE.sub(" ", (s or "").lower())
    return re.sub(r"[^a-z]+", " ", s).strip()


def is_usable_company(s: str) -> bool:
    return norm_company(s) not in _PLACEHOLDER and len((s or "").strip()) >= 2


def is_usable_person(s: str) -> bool:
    n = norm_person(s)
    return n not in _PLACEHOLDER and len(n) >= 2


def display_name(spellings: list[str]) -> str:
    """The most-used spelling (ties: the longest, which keeps 'Pvt Ltd')."""
    cleaned = [re.sub(r"\s+", " ", s).strip() for s in spellings if s and s.strip()]
    counts = Counter(cleaned)
    return sorted(counts, key=lambda k: (-counts[k], -len(k), k))[0]


def split_person(s: str) -> tuple[str, str | None]:
    parts = _TITLE.sub(" ", s or "").split()
    if not parts:
        return "", None
    return parts[0].strip(".,").title() if parts[0].islower() else parts[0].strip(".,"), (
        " ".join(parts[1:]).strip(".,") or None)


def _same_head(a: str, b: str) -> bool:
    """Same distinctive first word ('sunpack ...') — likely one customer group."""
    fa, fb = a.split(" ")[0], b.split(" ")[0]
    return len(fa) >= 5 and fa == fb


def similar_pairs(names: list[str], cutoff: float = 0.8) -> list[tuple[str, str]]:
    """Possible duplicates among company names, for a human to review."""
    out, seen = [], set()
    norms = [(n, norm_company(n)) for n in names]
    for i, (a, na) in enumerate(norms):
        for b, nb in norms[i + 1:]:
            if na == nb or (a, b) in seen:
                continue
            if difflib.SequenceMatcher(None, na, nb).ratio() >= cutoff or na.startswith(nb) or nb.startswith(na) or _same_head(na, nb):
                out.append((a, b))
                seen.add((a, b))
    return out
