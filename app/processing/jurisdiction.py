"""Section 4.2: jurisdiction guessing (from article text) and ruling-party
resolution (via the date-ranged lookup table).

These two things are deliberately separate: guessing WHICH jurisdiction an
article concerns requires understanding the text (a real classification
task, done here with a cheap keyword heuristic for the local provider - an
LLM provider could do this more accurately as part of its own prompt), while
resolving the ruling PARTY for a known jurisdiction+date is a pure lookup
per Section 4.2 ("resolved via a date-ranged lookup table, not hardcoded").
"""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import JurisdictionRulingParty

# Full names only, not abbreviations (e.g. no "UP", "MP", "TN") - short
# abbreviations collide too easily with ordinary English words/acronyms in
# news text and would produce false jurisdiction guesses.
INDIAN_STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]

# Delhi is handled separately from the plain list above: "New Delhi" is the
# dateline/seat of the central government, so a bare mention of it is not a
# signal about Delhi's own state government. Only treat it as a Delhi-state
# jurisdiction signal when paired with a state-government-specific term.
DELHI_STATE_MARKERS = [
    "delhi government",
    "delhi cabinet",
    "delhi assembly",
    "delhi cm",
    "delhi chief minister",
    "chief minister of delhi",
]

# Jammu and Kashmir is in INDIAN_STATES like any other state (its own
# Assembly and CM make it a normal state-jurisdiction target, unlike
# Delhi's central-government ambiguity), but it's also commonly referred to
# by three names that are NOT its own full name. "Kashmir" and "Jammu" are
# real place names (not abbreviations - they don't fall under the "full
# names only" rule above), and "J&K" is an abbreviation but, unlike "UP" or
# "MP", doesn't collide with an ordinary English word or an unrelated
# political acronym, so the collision risk that rule exists for doesn't
# apply here. Keys are matched lowercase, same as everything else in this
# module.
STATE_ALIASES: dict[str, str] = {
    "j&k": "Jammu and Kashmir",
    "kashmir": "Jammu and Kashmir",
    "jammu": "Jammu and Kashmir",
}


def guess_jurisdiction_keyword(text: str) -> str:
    """Cheap heuristic for the local provider: first state name mentioned
    wins; falls back to "centre" if none found. An LLM provider can do
    better by reasoning about context rather than just presence of a name.
    """
    lowered = text.lower()

    for marker in DELHI_STATE_MARKERS:
        if marker in lowered:
            return "state:Delhi"

    for state in INDIAN_STATES:
        if state.lower() in lowered:
            return f"state:{state}"

    for alias, state in STATE_ALIASES.items():
        if alias in lowered:
            return f"state:{state}"

    return "centre"


def resolve_ruling_party(db: Session, jurisdiction: str, as_of: datetime | date) -> str | None:
    """Looks up the ruling party for `jurisdiction` effective on `as_of`.
    Returns None if the table has no matching row (jurisdiction not seeded,
    or date falls outside every effective_from/effective_to range) - callers
    should treat that as "unresolved", not crash the pipeline over it.
    """
    if isinstance(as_of, datetime):
        as_of = as_of.date()

    stmt = (
        select(JurisdictionRulingParty)
        .where(
            JurisdictionRulingParty.jurisdiction == jurisdiction,
            JurisdictionRulingParty.effective_from <= as_of,
        )
        .where(
            (JurisdictionRulingParty.effective_to.is_(None)) | (JurisdictionRulingParty.effective_to >= as_of)
        )
        .order_by(JurisdictionRulingParty.effective_from.desc())
        .limit(1)
    )
    row = db.execute(stmt).scalar_one_or_none()
    return row.ruling_party if row else None
