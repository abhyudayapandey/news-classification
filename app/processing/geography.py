"""Content-derived geography tagging (state/district/constituency+seat) -
run against any text (article body, tweet text, video title) so a piece of
content can be filtered by *where it's about*, not by anything assigned to
an Entity. Per direct instruction: geography tagging must come from the
content itself - article text, posting location, video, tweet, etc - never
from a manual "this politician represents X" tag on Entity.

Deliberately separate from app/processing/jurisdiction.py's
guess_jurisdiction_keyword, which answers a narrower, different question
("which government's establishment is this pro/anti framing about",
Section 4.2) and only ever runs for pro/anti articles, folded into each
ClassificationProvider's own output. Geography here - what place a story or
post is actually about - is a plain fact about the text that applies
equally to apolitical articles and to every social mention, so it's
computed independently of whichever ClassificationProvider ran or what tag
it produced.

State detection reuses jurisdiction.py's own plain-name list. District and
constituency are recognized two ways: an explicit, self-naming phrase in
the text ("X district", "Y Lok Sabha seat" - works for ANY place, seeded
or not), or a bare mention matched against app/data/district_seed.py's
and app/data/constituency_seed.py's curated name lists (see those
modules' own docstrings for scope/confidence - seeded so far for the
states this build is actively being pitched in, not all of India yet).
Bare-name matching is deliberately NOT a blanket "any capitalized word" -
an arbitrary capitalized phrase has no way to be verified here, and a
wrong guess is worse than no guess - it only ever resolves a name that's
actually in one of those seed lists.

A bare name is also disambiguated against `guess_state()`'s own result
before being trusted, since a name can collide across states in real
gazetteer data (a "Jodhpur" district only exists in Rajasthan today, but
that's a property of what's currently seeded, not something the matching
logic assumes in general - see _resolve_bare_district/_resolve_bare_constituency
below). With no state context, a bare match is only trusted when the name
is unique to a single state across everything seeded - otherwise it's
left unresolved rather than guessed wrong.

Posting location (real geotags on a tweet or a video) is the other source
direct instruction calls out - not implemented here: X's recent-search API
response used by app/social/x_api.py doesn't request/return geo fields
(most posts aren't geotagged at all today), and YouTube search results
carry no reliable per-video location either. If either provider ever
starts supplying real location data, it should be preferred over this
text guess, not merged with it - flagged here rather than silently ignored.
"""

import re
from dataclasses import dataclass

from app.data.constituency_seed import CONSTITUENCIES
from app.data.district_seed import DISTRICTS
from app.data.hindi_district_names import HINDI_DISTRICT_NAMES
from app.models.enums import SeatType
from app.processing.jurisdiction import DELHI_STATE_MARKERS, INDIAN_STATES

# Excludes common sentence-initial capitalized words that aren't place
# names (a bare "The"/"In" preceding "Lok Sabha seat" would otherwise be
# captured as if it were the constituency's name) - a real, narrow fix for
# a real false-positive, not general stopword filtering.
_PLACE = r"(?!(?:The|A|An|This|That|Its|In|On|At|Of)\b)[A-Z][a-zA-Z\.]+(?:\s[A-Z][a-zA-Z\.]+){0,2}"

_DISTRICT_RE = re.compile(rf"\b({_PLACE})\s+[Dd]istrict\b")

# Hindi-language local outlets (e.g. City News Rajasthan) conventionally
# open an article's body with a dateline-style lead: the district name in
# Hindi, then a danda ("।") or a period, then the rest of the sentence -
# e.g. "बूंदी। जिला प्रशासन ने..." ("Bundi. The district administration
# has..."). This is a distinct convention from the bare-name/explicit-
# phrase matching below (which is entirely Latin-script and can't match
# Devanagari text at all), so it gets its own regex and its own resolver,
# checked first in guess_district() - a deliberate lede naming its own
# district is at least as trustworthy as an explicit "X district" phrase.
_HINDI_DISTRICT_BY_NAME: dict[str, str] = dict(HINDI_DISTRICT_NAMES)
_HINDI_DISTRICT_LEAD_RE = (
    re.compile(
        r"^\s*(" + "|".join(re.escape(n) for n in sorted(_HINDI_DISTRICT_BY_NAME, key=len, reverse=True)) + r")\s*[।.]",
        re.MULTILINE,
    )
    if _HINDI_DISTRICT_BY_NAME
    else None
)

# Two common orders in real news text: "Baramati Lok Sabha seat" (name
# first) and "the Lok Sabha seat of Baramati" (name after "of").
_CONSTITUENCY_NAME_FIRST_RE = re.compile(
    rf"\b({_PLACE})\s+(Lok Sabha|Vidhan Sabha|[Aa]ssembly)\s+(?:[Cc]onstituency|[Ss]eat)\b"
)
_CONSTITUENCY_OF_RE = re.compile(
    rf"\b(Lok Sabha|Vidhan Sabha|[Aa]ssembly)\s+(?:[Cc]onstituency|[Ss]eat)\s+of\s+({_PLACE})\b"
)

# Bare-name lookups built from the seeded gazetteers (see module docstring).
# Keyed by name -> the set of (state[, seat_type]) it could mean, so a bare
# match can be checked against guess_state()'s result before being trusted.
# Sorted longest-first so e.g. a two-word name matches before a one-word
# name that happens to be its prefix, the same reasoning as _PLACE above.
_DISTRICT_STATES: dict[str, set[str]] = {}
for _name, _state in DISTRICTS:
    _DISTRICT_STATES.setdefault(_name, set()).add(_state)
_BARE_DISTRICT_RE = (
    re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(_DISTRICT_STATES, key=len, reverse=True)) + r")\b")
    if _DISTRICT_STATES
    else None
)

_CONSTITUENCY_STATES: dict[str, set[tuple[str, SeatType]]] = {}
for _name, _state, _seat in CONSTITUENCIES:
    _CONSTITUENCY_STATES.setdefault(_name, set()).add((_state, _seat))
_BARE_CONSTITUENCY_RE = (
    re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(_CONSTITUENCY_STATES, key=len, reverse=True)) + r")\b")
    if _CONSTITUENCY_STATES
    else None
)

# Some states have real MLA seats that share a name with another seat
# elsewhere in the same state (see constituency_seed.py's module
# docstring for the full list and provenance - Gujarat's 5, Rajasthan's
# Shahpura). The bare name (e.g. "Kalol", "Shahpura") is seeded once and
# stays the default/ambiguous bucket; each also has its own explicitly-
# seeded disambiguated name for the other district's seat ("Kalol
# (Panchmahal)", "Shahpura (Bhilwara)"). Confirmed against the ECI's
# official constituency-to-district table (and, for Shahpura, a direct
# web search cross-check - see the collision note in constituency_seed.py).
# When a bare mention's surrounding text also names the OTHER seat's
# district specifically, tag it with the disambiguated name instead of
# the default - staying with the default whenever that context isn't
# there (no guess, or some unrelated district mentioned) rather than
# guessing wrong, the same discipline used throughout this module. A
# content item that can't be disambiguated this way still shows up
# wherever it's queried for the default name; see client_ui.py's
# SEAT_COLLISION_BARE_NAME use for how the "other" seat's own page also
# pulls in that same default-tagged content.
SEAT_COLLISIONS_BY_STATE: dict[str, dict[str, tuple[str, str]]] = {
    "Gujarat": {
        # bare seed name -> (the OTHER seat's real district, its disambiguated name)
        "Kalol": ("Panchmahal", "Kalol (Panchmahal)"),
        "Mandvi": ("Surat", "Mandvi (Surat)"),
        "Jetpur": ("Chhota Udaipur", "Jetpur (Chhota Udaipur)"),
        "Mangrol": ("Surat", "Mangrol (Surat)"),
        "Mahuva": ("Surat", "Mahuva (Surat)"),
    },
    "Rajasthan": {
        "Shahpura": ("Bhilwara", "Shahpura (Bhilwara)"),
    },
    "West Bengal": {
        "Bishnupur": ("Bankura", "Bishnupur (Bankura)"),
    },
    "Bihar": {
        "Kalyanpur": ("Samastipur", "Kalyanpur (Samastipur)"),
        "Pipra": ("Supaul", "Pipra (Supaul)"),
    },
    "Andhra Pradesh": {
        "Gannavaram": ("Krishna", "Gannavaram (Krishna)"),
        "Prathipadu": ("Guntur", "Prathipadu (Guntur)"),
    },
    "Tamil Nadu": {
        "Tiruppattur": ("Sivaganga", "Tiruppattur (Sivaganga)"),
    },
}

# Reverse of the mapping above (disambiguated name -> its bare/default
# name), for query-time use: a client viewing the disambiguated "other"
# seat's page should also see content that only ever made it into the
# ambiguous default bucket (no district context to disambiguate it at
# classification time), not just content confidently tagged with the
# disambiguated name itself. The default seat's own page does the
# opposite on purpose - it does NOT also pull in the disambiguated name's
# content, since that content has already been confidently attributed
# elsewhere. Flat across states since every disambiguated name is
# already a globally unique string.
SEAT_COLLISION_BARE_NAME: dict[str, str] = {
    other_name: bare_name
    for _state, _collisions in SEAT_COLLISIONS_BY_STATE.items()
    for bare_name, (_district, other_name) in _collisions.items()
}


def _resolve_hindi_district_lead(text: str) -> str | None:
    if _HINDI_DISTRICT_LEAD_RE is None:
        return None
    match = _HINDI_DISTRICT_LEAD_RE.search(text)
    return _HINDI_DISTRICT_BY_NAME[match.group(1)] if match else None


def _resolve_bare_district(text: str) -> str | None:
    if _BARE_DISTRICT_RE is None:
        return None
    candidates = list(dict.fromkeys(m.group(1) for m in _BARE_DISTRICT_RE.finditer(text)))
    if not candidates:
        return None
    guessed_state = guess_state(text)
    for name in candidates:
        states = _DISTRICT_STATES[name]
        if guessed_state:
            if guessed_state in states:
                return name
        elif len(states) == 1:
            return name
    return None


def _resolve_bare_constituency(text: str) -> tuple[str, SeatType | None] | None:
    if _BARE_CONSTITUENCY_RE is None:
        return None
    candidates = list(dict.fromkeys(m.group(1) for m in _BARE_CONSTITUENCY_RE.finditer(text)))
    if not candidates:
        return None
    guessed_state = guess_state(text)
    for name in candidates:
        entries = _CONSTITUENCY_STATES[name]
        states = {e[0] for e in entries}
        if guessed_state:
            if guessed_state not in states:
                continue
            resolved_state = guessed_state
        elif len(states) == 1:
            resolved_state = next(iter(states))
        else:
            continue  # name exists in multiple states with no state context - stay honest, try the next candidate
        seat_types = {e[1] for e in entries if e[0] == resolved_state}
        # Same name can be both an MP and an MLA seat in the same state (a
        # real collision, e.g. Jodhpur) - the name itself is still resolved,
        # just not which house, when a bare mention can't tell them apart.
        resolved_seat_type = next(iter(seat_types)) if len(seat_types) == 1 else None
        collision = SEAT_COLLISIONS_BY_STATE.get(resolved_state, {}).get(name)
        if collision:
            other_district, other_name = collision
            if guess_district(text) == other_district:
                name = other_name
        return name, resolved_seat_type
    return None


@dataclass
class GuessedGeography:
    state: str | None = None
    district: str | None = None
    constituency: str | None = None
    seat_type: SeatType | None = None


def _seat_type_for(house: str) -> SeatType:
    return SeatType.MP if house.lower() == "lok sabha" else SeatType.MLA


def guess_state(text: str) -> str | None:
    """Same state list/Delhi handling as jurisdiction.guess_jurisdiction_keyword,
    but returns a bare state name (or None) rather than jurisdiction's own
    "state:<name>"/"centre" encoding - this isn't about establishment
    framing, just "what place is this about", so there's no "centre"
    fallback here: no state mentioned means no state guessed, full stop.
    """
    lowered = text.lower()
    for marker in DELHI_STATE_MARKERS:
        if marker in lowered:
            return "Delhi"
    for state in INDIAN_STATES:
        if state.lower() in lowered:
            return state
    return None


def guess_district(text: str) -> str | None:
    hindi_lead = _resolve_hindi_district_lead(text)
    if hindi_lead:
        return hindi_lead
    match = _DISTRICT_RE.search(text)
    if match:
        return match.group(1).strip()
    return _resolve_bare_district(text)


def guess_constituency(text: str) -> tuple[str, SeatType | None] | None:
    match = _CONSTITUENCY_NAME_FIRST_RE.search(text)
    if match:
        return match.group(1).strip(), _seat_type_for(match.group(2))
    match = _CONSTITUENCY_OF_RE.search(text)
    if match:
        return match.group(2).strip(), _seat_type_for(match.group(1))
    return _resolve_bare_constituency(text)


def guess_geography(text: str) -> GuessedGeography:
    constituency_match = guess_constituency(text)
    return GuessedGeography(
        state=guess_state(text),
        district=guess_district(text),
        constituency=constituency_match[0] if constituency_match else None,
        seat_type=constituency_match[1] if constituency_match else None,
    )
