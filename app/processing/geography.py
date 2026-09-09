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

Same "no seeded master list" posture as the rest of this build's geography
work: state detection reuses jurisdiction.py's own plain-name list. District
and constituency are otherwise only recognized via an explicit, self-naming
phrase in the text - "X district", "Y Lok Sabha seat" - never guessed from
a bare place name alone in general, since an arbitrary capitalized word has
no way to be verified here and a wrong guess is worse than no guess.

_KNOWN_BARE_DISTRICTS is the deliberate, narrow exception to that: per
direct instruction, a small curated list of place names this platform is
actively pitching in (Jodhpur, Udaipur), where local outlets simply write
the city name and never spell out "district" - requiring the explicit
phrase would silently geo-tag nothing for exactly the content this list
exists to catch. This is still not a general gazetteer (that posture is
unchanged for every other place name) - it's a short, explicitly vetted
list, extended only when a specific place is worth the same treatment.

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

from app.models.enums import SeatType
from app.processing.jurisdiction import DELHI_STATE_MARKERS, INDIAN_STATES

# Excludes common sentence-initial capitalized words that aren't place
# names (a bare "The"/"In" preceding "Lok Sabha seat" would otherwise be
# captured as if it were the constituency's name) - a real, narrow fix for
# a real false-positive, not general stopword filtering.
_PLACE = r"(?!(?:The|A|An|This|That|Its|In|On|At|Of)\b)[A-Z][a-zA-Z\.]+(?:\s[A-Z][a-zA-Z\.]+){0,2}"

_DISTRICT_RE = re.compile(rf"\b({_PLACE})\s+[Dd]istrict\b")

# Two common orders in real news text: "Baramati Lok Sabha seat" (name
# first) and "the Lok Sabha seat of Baramati" (name after "of").
_CONSTITUENCY_NAME_FIRST_RE = re.compile(
    rf"\b({_PLACE})\s+(Lok Sabha|Vidhan Sabha|[Aa]ssembly)\s+(?:[Cc]onstituency|[Ss]eat)\b"
)
_CONSTITUENCY_OF_RE = re.compile(
    rf"\b(Lok Sabha|Vidhan Sabha|[Aa]ssembly)\s+(?:[Cc]onstituency|[Ss]eat)\s+of\s+({_PLACE})\b"
)

# See module docstring: a short, explicitly curated list of place names
# recognized as a district from a bare mention alone - add to this list
# deliberately, one vetted place at a time, never as a stand-in for a real
# gazetteer.
_KNOWN_BARE_DISTRICTS = ["Jodhpur", "Udaipur"]
_BARE_DISTRICT_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in _KNOWN_BARE_DISTRICTS) + r")\b")


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
    match = _DISTRICT_RE.search(text)
    if match:
        return match.group(1).strip()
    match = _BARE_DISTRICT_RE.search(text)
    return match.group(1) if match else None


def guess_constituency(text: str) -> tuple[str, SeatType] | None:
    match = _CONSTITUENCY_NAME_FIRST_RE.search(text)
    if match:
        return match.group(1).strip(), _seat_type_for(match.group(2))
    match = _CONSTITUENCY_OF_RE.search(text)
    if match:
        return match.group(2).strip(), _seat_type_for(match.group(1))
    return None


def guess_geography(text: str) -> GuessedGeography:
    constituency_match = guess_constituency(text)
    return GuessedGeography(
        state=guess_state(text),
        district=guess_district(text),
        constituency=constituency_match[0] if constituency_match else None,
        seat_type=constituency_match[1] if constituency_match else None,
    )
