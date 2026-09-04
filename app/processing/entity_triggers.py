"""Section 4.3's entity-trigger safety net: presence of certain entities in
an article the classifier called "apolitical" overrides that call and
routes the article through pro/anti classification instead.

Deliberately not an ML/NER model - the doc specifies this as a safety net
*independent* of the classifier's own judgment (it exists precisely to
catch the classifier's blind spots), so it should fail differently than the
classifier does. A plain keyword/regex list is transparent, needs no model
download, costs nothing, and is trivial for you to extend - edit the lists
below, no code changes needed elsewhere. It will have false positives (e.g.
"Union Minister" mentioned only in passing) and false negatives (an
official referred to only by name, with no title) - that's an acceptable
trade for a safety net whose job is to over-trigger review, not to classify
precisely.
"""

import re

from app.text_utils import boundary_pattern as _boundary_pattern


_POLITICAL_TITLES = [
    "mla",
    "mlas",
    "mp",
    "mps",
    "member of parliament",
    "member of the legislative assembly",
    "rajya sabha",
    "lok sabha",
    "chief minister",
    "prime minister",
    "union minister",
    "cabinet minister",
    "deputy chief minister",
    "governor",
    "lieutenant governor",
    "cm",
    "pm",
]

# Boundary matching matters here: short acronyms like "mp" or "cm" would
# otherwise match as substrings inside ordinary words ("championship",
# "comment"). All titles are routed through this the same way for
# consistency, even the multi-word ones that wouldn't strictly need it.
_TITLE_PATTERNS = [_boundary_pattern(title) for title in _POLITICAL_TITLES]

_MINISTRY_PATTERN = re.compile(r"\bministry of [a-z&, ]+", re.IGNORECASE)

_TENDER_CONTRACT_TERMS = [
    "government tender",
    "public tender",
    "tender process",
    "government contract",
    "awarded the contract",
    "awarded a contract",
    "contract awarded",
]
_TENDER_PATTERNS = [_boundary_pattern(term) for term in _TENDER_CONTRACT_TERMS]

# National + major state parties. Not exhaustive - extend as needed.
_POLITICAL_PARTIES = [
    "bjp",
    "bharatiya janata party",
    "indian national congress",
    "congress party",
    "aam aadmi party",
    "aap",
    "trinamool congress",
    "tmc",
    "dmk",
    "aiadmk",
    "shiv sena",
    "nationalist congress party",
    "ncp",
    "janata dal",
    "rashtriya janata dal",
    "rjd",
    "samajwadi party",
    "bahujan samaj party",
    "bsp",
    "cpi(m)",
    "cpi (m)",
    "communist party of india",
    "ysrcp",
    "telugu desam party",
    "tdp",
    "bharat rashtra samithi",
    "brs",
    "jharkhand mukti morcha",
    "jmm",
    "lok janshakti party",
    "jd(u)",
    "janata dal (united)",
    # Tamilaga Vettri Kazhagam - founded too recently to be in this model's
    # training data; added after winning the May 2026 Tamil Nadu election
    # (see app/data/jurisdiction_seed.py). A reminder that this list needs
    # the same "did a new party show up" maintenance as the ruling-party
    # lookup table - a new/regional party won't be in any pretrained
    # model's knowledge until well after it matters.
    "tvk",
    "tamilaga vettri kazhagam",
]
_PARTY_PATTERNS = [_boundary_pattern(party) for party in _POLITICAL_PARTIES]


def detect_trigger_entities(text: str) -> list[str]:
    """Returns the distinct trigger terms found in `text` (empty if none)."""
    found = set()

    for title, pattern in zip(_POLITICAL_TITLES, _TITLE_PATTERNS):
        if pattern.search(text):
            found.add(title)

    if _MINISTRY_PATTERN.search(text):
        found.add("ministry reference")

    for term, pattern in zip(_TENDER_CONTRACT_TERMS, _TENDER_PATTERNS):
        if pattern.search(text):
            found.add(term)

    for party, pattern in zip(_POLITICAL_PARTIES, _PARTY_PATTERNS):
        if pattern.search(text):
            found.add(party)

    return sorted(found)


def has_trigger_entity(text: str) -> bool:
    return bool(detect_trigger_entities(text))
