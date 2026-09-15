"""Seed data for the jurisdiction -> ruling party lookup table (Section 4.2).

Last updated 2026-09-15, incorporating the May 4, 2026 assembly election
results (West Bengal, Tamil Nadu, Kerala, Assam), confirmation of the
Nov 2025 Bihar result, and the 15 April 2026 Bihar NDA leadership change
(Nitish Kumar replaced as CM by Samrat Choudhary, JD(U)-led NDA becoming
BJP-led NDA) - all user-verified against current sources, since my own
training cutoff (January 2026) predates all of these.

Per Section 4.2's date-ranged design, a government change gets a NEW row
with its own effective_from, and the PRIOR row is closed out with a
matching effective_to (one day before) rather than edited in place - this
keeps date-ranged lookups on older articles correct (an article from 2023
should still resolve to the government that was actually in power then).

This table is still explicitly hand-maintained (see
app/models/jurisdiction.py) - re-verify anything here against current
sources before a real classification decision leans on it, and add new
rows the same way the next time any of these changes.

Coverage: Centre + the ~20 most populous states, not exhaustive. Smaller
states/UTs aren't seeded - add rows for them the same way if you need them.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models import JurisdictionRulingParty

# (jurisdiction, ruling_party, effective_from, effective_to, confidence_note)
# effective_to=None means "still in effect". A closed-out historical row
# keeps its original effective_from - only effective_to changes.
JURISDICTION_SEED: list[tuple[str, str, date, date | None, str]] = [
    ("centre", "BJP-led NDA", date(2024, 6, 9), None, "high confidence"),
    ("state:Uttar Pradesh", "BJP", date(2022, 3, 25), None, "high confidence"),
    ("state:Maharashtra", "BJP-led Mahayuti", date(2024, 12, 5), None, "high confidence"),
    (
        "state:Bihar",
        "JD(U)-led NDA",
        date(2024, 1, 28),
        date(2026, 4, 14),
        "closed out - NDA retained power in the Nov 2025 election (202/243 seats) with "
        "Nitish Kumar continuing as CM, but he was then removed as CM on 15 April 2026, "
        "with BJP taking over leadership of the same ruling NDA coalition",
    ),
    (
        "state:Bihar",
        "BJP-led NDA",
        date(2026, 4, 15),
        None,
        "high confidence - Samrat Choudhary made CM on 15 April 2026, replacing Nitish "
        "Kumar; same NDA coalition stays in power, only its leading party changes "
        "from JD(U) to BJP",
    ),
    # West Bengal: TMC's 15-year run ended in the May 2026 election.
    (
        "state:West Bengal",
        "TMC",
        date(2021, 5, 5),
        date(2026, 5, 3),
        "closed out - lost the May 2026 election to BJP",
    ),
    (
        "state:West Bengal",
        "BJP",
        date(2026, 5, 4),
        None,
        "high confidence - won the May 2026 election (206 seats), ending 15 years of TMC rule",
    ),
    ("state:Madhya Pradesh", "BJP", date(2023, 12, 13), None, "high confidence"),
    # Tamil Nadu: TVK (Tamilaga Vettri Kazhagam) is a new party, founded too
    # recently to be in my training data - see the entity-trigger net note
    # in app/processing/entity_triggers.py, which now includes it.
    (
        "state:Tamil Nadu",
        "DMK",
        date(2021, 5, 7),
        date(2026, 5, 3),
        "closed out - lost the May 2026 election to TVK",
    ),
    (
        "state:Tamil Nadu",
        "TVK",
        date(2026, 5, 4),
        None,
        "high confidence - new party won the May 2026 election (108 seats), "
        "ending decades of DMK/AIADMK dominance",
    ),
    ("state:Rajasthan", "BJP", date(2023, 12, 15), None, "high confidence"),
    ("state:Karnataka", "Congress", date(2023, 5, 20), None, "high confidence"),
    ("state:Gujarat", "BJP", date(2022, 12, 12), None, "high confidence"),
    ("state:Andhra Pradesh", "TDP-led NDA", date(2024, 6, 12), None, "high confidence"),
    ("state:Odisha", "BJP", date(2024, 6, 12), None, "high confidence"),
    ("state:Telangana", "Congress", date(2023, 12, 7), None, "high confidence"),
    (
        "state:Kerala",
        "LDF (CPI-M led)",
        date(2021, 5, 20),
        date(2026, 5, 3),
        "closed out - lost the May 2026 election to Congress-led UDF",
    ),
    (
        "state:Kerala",
        "Congress-led UDF",
        date(2026, 5, 4),
        None,
        "high confidence - won the May 2026 election, ending LDF's term",
    ),
    ("state:Jharkhand", "JMM-led alliance", date(2024, 11, 28), None, "medium confidence"),
    ("state:Punjab", "AAP", date(2022, 3, 16), None, "high confidence"),
    ("state:Chhattisgarh", "BJP", date(2023, 12, 13), None, "high confidence"),
    ("state:Haryana", "BJP", date(2024, 10, 17), None, "medium confidence"),
    (
        "state:Assam",
        "BJP",
        date(2021, 5, 10),
        None,
        "confirmed: BJP retained power in the May 2026 election - ruling party unchanged, no new row needed",
    ),
    (
        "state:Delhi",
        "BJP",
        date(2025, 2, 20),
        None,
        "medium confidence - ended ~10 years of AAP government in the Feb 2025 election",
    ),
]


def seed_jurisdictions(db: Session) -> tuple[int, int]:
    """Upserts JURISDICTION_SEED, matched on (jurisdiction, ruling_party,
    effective_from). Safe to re-run. Returns (inserted, updated):

    - A new (jurisdiction, ruling_party, effective_from) triple is inserted.
    - An existing one has its effective_to synced to the seed - this is how
      a previously "still in effect" row gets closed out once a government
      changes, without ever touching its effective_from (preserving the
      historical record other rows' date-ranged lookups depend on).
    """
    existing = {(row.jurisdiction, row.ruling_party, row.effective_from): row for row in db.query(JurisdictionRulingParty)}

    inserted = 0
    updated = 0
    for jurisdiction, ruling_party, effective_from, effective_to, _note in JURISDICTION_SEED:
        key = (jurisdiction, ruling_party, effective_from)
        row = existing.get(key)
        if row is None:
            db.add(
                JurisdictionRulingParty(
                    jurisdiction=jurisdiction,
                    ruling_party=ruling_party,
                    effective_from=effective_from,
                    effective_to=effective_to,
                )
            )
            inserted += 1
        elif row.effective_to != effective_to:
            row.effective_to = effective_to
            updated += 1

    db.commit()
    return inserted, updated
