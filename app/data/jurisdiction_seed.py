"""Seed data for the jurisdiction -> ruling party lookup table (Section 4.2).

READ THIS BEFORE TRUSTING THIS DATA. My knowledge of Indian politics has a
training cutoff of January 2026; this seed was written in a session dated
August 2026 - a seven-month gap. Assembly elections due in that window mean
some of these rows are near-certainly stale the moment they're seeded, not
just "due for periodic review" like the rest of the table:

- West Bengal, Kerala, Tamil Nadu, Assam, Puducherry: assembly elections
  were expected around April-May 2026. Given today's date, these have
  almost certainly already happened, and I do not know the results. VERIFY
  THESE FIVE BEFORE RELYING ON THEM FOR ANYTHING.
- Bihar: an assembly election was expected around Oct-Nov 2025, also after
  my cutoff. VERIFY THIS ONE TOO.

Every other row reflects my best knowledge as of the cutoff and should
still be reasonably current (most state governments run fixed 5-year
terms with no election due), but "reasonably current" is not "verified" -
this table is explicitly a manually-maintained one (see
app/models/jurisdiction.py) and you are the one who needs to maintain it.
Cross-check anything this seed says against current news before treating
it as ground truth, especially before this data feeds a real classification
decision.

Coverage: Centre + the ~20 most populous states, not exhaustive. Smaller
states/UTs aren't seeded - add rows for them the same way if you need them.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models import JurisdictionRulingParty

# (jurisdiction, ruling_party, effective_from, confidence_note)
# effective_to is always None here (all "currently in effect" as of the
# cutoff) - add a new row with its own effective_from/effective_to the next
# time any of these actually changes, rather than editing this one in place,
# so the history stays intact for date-ranged lookups on older articles.
JURISDICTION_SEED: list[tuple[str, str, date, str]] = [
    ("centre", "BJP-led NDA", date(2024, 6, 9), "high confidence"),
    ("state:Uttar Pradesh", "BJP", date(2022, 3, 25), "high confidence"),
    ("state:Maharashtra", "BJP-led Mahayuti", date(2024, 12, 5), "high confidence"),
    ("state:Bihar", "JD(U)-led NDA", date(2024, 1, 28), "STALE RISK: election was due ~Nov 2025, after cutoff - verify"),
    (
        "state:West Bengal",
        "TMC",
        date(2021, 5, 5),
        "STALE RISK: election was due ~April-May 2026, likely already happened - verify",
    ),
    ("state:Madhya Pradesh", "BJP", date(2023, 12, 13), "high confidence"),
    ("state:Tamil Nadu", "DMK", date(2021, 5, 7), "STALE RISK: election was due ~April-May 2026 - verify"),
    ("state:Rajasthan", "BJP", date(2023, 12, 15), "high confidence"),
    ("state:Karnataka", "Congress", date(2023, 5, 20), "high confidence"),
    ("state:Gujarat", "BJP", date(2022, 12, 12), "high confidence"),
    ("state:Andhra Pradesh", "TDP-led NDA", date(2024, 6, 12), "high confidence"),
    ("state:Odisha", "BJP", date(2024, 6, 12), "high confidence"),
    ("state:Telangana", "Congress", date(2023, 12, 7), "high confidence"),
    ("state:Kerala", "LDF (CPI-M led)", date(2021, 5, 20), "STALE RISK: election was due ~April-May 2026 - verify"),
    ("state:Jharkhand", "JMM-led alliance", date(2024, 11, 28), "medium confidence"),
    ("state:Punjab", "AAP", date(2022, 3, 16), "high confidence"),
    ("state:Chhattisgarh", "BJP", date(2023, 12, 13), "high confidence"),
    ("state:Haryana", "BJP", date(2024, 10, 17), "medium confidence"),
    ("state:Assam", "BJP", date(2021, 5, 10), "STALE RISK: election was due ~April-May 2026 - verify"),
    (
        "state:Delhi",
        "BJP",
        date(2025, 2, 20),
        "medium confidence - ended ~10 years of AAP government in the Feb 2025 election",
    ),
]


def seed_jurisdictions(db: Session) -> int:
    """Upserts JURISDICTION_SEED, matched on (jurisdiction, effective_from).
    Safe to re-run - existing matching rows are left as-is (edit the table
    directly, or this file and re-run, if a value needs correcting).
    Returns the number of rows inserted.
    """
    existing = {
        (row.jurisdiction, row.effective_from)
        for row in db.query(JurisdictionRulingParty.jurisdiction, JurisdictionRulingParty.effective_from)
    }

    inserted = 0
    for jurisdiction, ruling_party, effective_from, _note in JURISDICTION_SEED:
        if (jurisdiction, effective_from) in existing:
            continue
        db.add(
            JurisdictionRulingParty(
                jurisdiction=jurisdiction,
                ruling_party=ruling_party,
                effective_from=effective_from,
                effective_to=None,
            )
        )
        inserted += 1

    db.commit()
    return inserted
