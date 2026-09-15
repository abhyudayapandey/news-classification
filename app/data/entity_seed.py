"""Seed data for the Entity table (Section 13.1).

**Parties**: reuses and extends app/processing/entity_triggers.py's
~25-item trigger list - but that list is a flat set of *trigger strings*,
not entity identities, and it silently conflates some real distinctions:
"cpi(m)"/"cpi (m)" and "communist party of india" sat in the same list even
though CPI and CPI(M) have been separate parties since a 1964 split. Here
they're correctly split into two Entity rows. Extended with parties that
were real, notable gaps in the original trigger list: JD(S), Shiromani
Akali Dal, Biju Janata Dal, AIMIM, Jammu & Kashmir National Conference,
and PDP. **Still a real, flagged gap**: northeastern and other smaller
regional parties (Mizo National Front, National People's Party, Sikkim
Krantikari Morcha, and others) remain essentially unrepresented - the
same "not exhaustive" caveat the trigger list always carried, now made
concrete rather than left implicit.

**Persons**: did not exist at all before this phase (the trigger net only
matched generic titles like "chief minister", never named individuals).
Seeded with national figures and state chief ministers, following the
same jurisdiction_seed.py precedent of a `confidence` note per entry and
explicit honesty about my training cutoff (January 2026) versus this
being built in September 2026 - eight months where real personnel changes
could have happened that I have no way to know about. West Bengal, Tamil
Nadu, and Kerala all changed ruling parties in the May 2026 elections (see
app/data/jurisdiction_seed.py); their new chief ministers were initially
**deliberately not seeded as named individuals**, since guessing a
specific person would have been exactly the kind of fabrication this
platform's own design principles (Section 2) warn against. **Update,
user-confirmed**: all three are now known and seeded below - Suvendu
Adhikari (BJP, West Bengal, sworn in 9 May 2026), Vijay (TVK, Tamil Nadu,
sworn in 10 May 2026 - the entity already existed as TVK's founder,
updated in place rather than duplicated), and V. D. Satheesan
(Congress-led UDF, Kerala, sworn in 18 May 2026). The former chief
ministers (Banerjee, Stalin, Vijayan) stay seeded too, as real, current,
relevant political figures now correctly noted as predecessors rather
than "successor unknown".

**Update, user-confirmed**: Bihar's Nitish Kumar (JD(U)) was removed as CM
on 15 April 2026 and replaced by Samrat Choudhary (BJP) - unlike the three
above, this wasn't a change of ruling coalition (NDA stayed in power the
whole time, see app/data/jurisdiction_seed.py), just of which party within
it holds the CM's office. Nitish Kumar is kept seeded as "party leader,
former Bihar CM", same pattern as Banerjee/Stalin/Vijayan above.

**Kerala's ~2-week gap, flagged explicitly per direct instruction**: the
election result (and so `jurisdiction_seed.py`'s `effective_from` for
Congress-led UDF) landed May 4, 2026, but Satheesan's swearing-in - and
so his actual start as an identifiable named entity - didn't happen until
May 18, a Congress internal leadership dispute delaying the announcement.
**Audited for downstream impact**: nothing in this codebase infers a
person's start date from `JurisdictionRulingParty.effective_from` -
`resolve_ruling_party()` (app/processing/jurisdiction.py) resolves the
ruling *party* only and never touches `Entity`/`ArticleEntity` at all, and
entity text-matching (app/processing/entities.py) has no date dimension
whatsoever - it just looks for literal name occurrences, so it can't
mismatch an article to the wrong person based on when they took office.
The real, structural gap this surfaces: `Entity` has no date-ranged
validity the way `JurisdictionRulingParty` does, so `entity_metadata`'s
"role" is always a single current snapshot, not historically accurate for
older mentions ("the Kerala CM" in an article from May 10 correctly meant
Vijayan, in caretaker capacity, not Satheesan - nothing here would get
that wrong today, but nothing would get it right from stored data alone
either, if that distinction is ever needed). Not fixed here - it's a
schema extension (effective_from/to on Entity or a new mapping table) with
no concrete need yet, not something to speculatively build.

**A deliberate precision/recall tradeoff, flagged rather than silently
accepted**: a few aliases below are genuinely ambiguous in isolation
(bare "Modi" collides with Nirav Modi, Lalit Modi; "SP" collides with
"Superintendent of Police"). Where a short form is unambiguous enough in
Indian political news to be worth the recall (bare "Modi" overwhelmingly
means the PM in this context), it's included; where the collision risk
seemed too high for too little benefit (bare "SP" for Samajwadi Party),
it's deliberately left out and only the fuller form is matched. This is a
judgment call, not a validated one - revisit if false-positive entity
tags on the wrong "Modi" or similar turn up in practice.
"""

from sqlalchemy.orm import Session

from app.models import Entity
from app.models.enums import EntityType

# (name, type, aliases, metadata)
# metadata.confidence mirrors jurisdiction_seed.py's own confidence-note
# convention - "high"/"medium" is my own assessment of how likely this
# specific fact is to still be accurate, not a validated measurement.
ENTITY_SEED: list[tuple[str, EntityType, list[str], dict]] = [
    # --- Parties: reused/split from entity_triggers.py's trigger list ---
    ("Bharatiya Janata Party", EntityType.PARTY, ["BJP"], {"scope": "national"}),
    ("Indian National Congress", EntityType.PARTY, ["Congress", "INC", "Congress Party"], {"scope": "national"}),
    ("Aam Aadmi Party", EntityType.PARTY, ["AAP"], {"scope": "national"}),
    ("Trinamool Congress", EntityType.PARTY, ["TMC", "All India Trinamool Congress"], {"scope": "state", "state": "West Bengal"}),
    ("Dravida Munnetra Kazhagam", EntityType.PARTY, ["DMK"], {"scope": "state", "state": "Tamil Nadu"}),
    ("All India Anna Dravida Munnetra Kazhagam", EntityType.PARTY, ["AIADMK"], {"scope": "state", "state": "Tamil Nadu"}),
    ("Tamilaga Vettri Kazhagam", EntityType.PARTY, ["TVK"], {"scope": "state", "state": "Tamil Nadu", "note": "new party, won May 2026 TN election"}),
    ("Shiv Sena", EntityType.PARTY, [], {"scope": "state", "state": "Maharashtra", "note": "split into UBT and Shinde factions post-2022 - not modeled as separate entities yet, a real simplification"}),
    ("Nationalist Congress Party", EntityType.PARTY, ["NCP"], {"scope": "state", "state": "Maharashtra", "note": "split into Sharad Pawar and Ajit Pawar factions post-2023 - not modeled as separate entities yet, a real simplification"}),
    ("Janata Dal (United)", EntityType.PARTY, ["JD(U)"], {"scope": "state", "state": "Bihar"}),
    ("Rashtriya Janata Dal", EntityType.PARTY, ["RJD"], {"scope": "state", "state": "Bihar"}),
    ("Samajwadi Party", EntityType.PARTY, [], {"scope": "state", "state": "Uttar Pradesh", "note": "bare 'SP' deliberately not an alias - collides with Superintendent of Police"}),
    ("Bahujan Samaj Party", EntityType.PARTY, ["BSP"], {"scope": "state", "state": "Uttar Pradesh"}),
    ("Communist Party of India (Marxist)", EntityType.PARTY, ["CPI(M)", "CPI (M)", "CPM"], {"scope": "national"}),
    ("Communist Party of India", EntityType.PARTY, ["CPI"], {"scope": "national", "note": "distinct from CPI(M) - split 1964, conflated in the old trigger-only list"}),
    ("YSR Congress Party", EntityType.PARTY, ["YSRCP"], {"scope": "state", "state": "Andhra Pradesh"}),
    ("Telugu Desam Party", EntityType.PARTY, ["TDP"], {"scope": "state", "state": "Andhra Pradesh"}),
    ("Bharat Rashtra Samithi", EntityType.PARTY, ["BRS", "TRS"], {"scope": "state", "state": "Telangana", "note": "renamed from TRS in 2022"}),
    ("Jharkhand Mukti Morcha", EntityType.PARTY, ["JMM"], {"scope": "state", "state": "Jharkhand"}),
    ("Lok Janshakti Party", EntityType.PARTY, ["LJP"], {"scope": "state", "state": "Bihar", "note": "split into factions after Ram Vilas Paswan's death - not modeled separately"}),
    # --- Parties: gaps in the original trigger list, added here ---
    ("Janata Dal (Secular)", EntityType.PARTY, ["JD(S)"], {"scope": "state", "state": "Karnataka", "note": "gap fix - absent from the old trigger list entirely"}),
    ("Shiromani Akali Dal", EntityType.PARTY, ["SAD", "Akali Dal"], {"scope": "state", "state": "Punjab", "note": "gap fix"}),
    ("Biju Janata Dal", EntityType.PARTY, ["BJD"], {"scope": "state", "state": "Odisha", "note": "gap fix - lost power June 2024 but remains the main opposition"}),
    ("All India Majlis-e-Ittehadul Muslimeen", EntityType.PARTY, ["AIMIM"], {"scope": "national", "note": "gap fix"}),
    ("Jammu & Kashmir National Conference", EntityType.PARTY, ["National Conference", "JKNC"], {"scope": "state", "state": "Jammu and Kashmir", "note": "gap fix"}),
    ("Jammu & Kashmir Peoples Democratic Party", EntityType.PARTY, ["PDP"], {"scope": "state", "state": "Jammu and Kashmir", "note": "gap fix"}),

    # --- Persons: national figures ---
    ("Narendra Modi", EntityType.PERSON, ["PM Modi", "Prime Minister Modi", "Modi"], {"party": "BJP", "role": "Prime Minister", "confidence": "high"}),
    ("Amit Shah", EntityType.PERSON, [], {"party": "BJP", "role": "Union Home Minister", "confidence": "high"}),
    ("Rahul Gandhi", EntityType.PERSON, [], {"party": "Indian National Congress", "role": "Leader of Opposition, Lok Sabha", "confidence": "high"}),
    ("Mallikarjun Kharge", EntityType.PERSON, [], {"party": "Indian National Congress", "role": "Party President", "confidence": "high"}),
    ("Sonia Gandhi", EntityType.PERSON, [], {"party": "Indian National Congress", "confidence": "high"}),
    ("Arvind Kejriwal", EntityType.PERSON, [], {"party": "Aam Aadmi Party", "role": "party leader, former Delhi CM", "confidence": "high"}),
    ("Asaduddin Owaisi", EntityType.PERSON, ["Owaisi"], {"party": "AIMIM", "confidence": "high"}),
    ("Sharad Pawar", EntityType.PERSON, [], {"party": "Nationalist Congress Party", "confidence": "high"}),
    ("Ajit Pawar", EntityType.PERSON, [], {"party": "Nationalist Congress Party", "role": "Deputy Chief Minister, Maharashtra", "confidence": "medium"}),
    ("Uddhav Thackeray", EntityType.PERSON, [], {"party": "Shiv Sena (UBT)", "confidence": "high"}),
    ("Eknath Shinde", EntityType.PERSON, [], {"party": "Shiv Sena", "role": "Deputy Chief Minister, Maharashtra", "confidence": "medium"}),
    ("Akhilesh Yadav", EntityType.PERSON, [], {"party": "Samajwadi Party", "confidence": "high"}),

    # --- Persons: state chief ministers (only where I have reasonable
    # confidence the office-holder hasn't changed since my training cutoff)
    ("Yogi Adityanath", EntityType.PERSON, [], {"party": "BJP", "role": "Chief Minister, Uttar Pradesh", "confidence": "high"}),
    ("Devendra Fadnavis", EntityType.PERSON, [], {"party": "BJP", "role": "Chief Minister, Maharashtra", "confidence": "medium"}),
    ("Nitish Kumar", EntityType.PERSON, [], {"party": "Janata Dal (United)", "role": "party leader, former Bihar CM", "confidence": "high", "note": "removed as CM on 15 April 2026 - NDA (which JD(U) still leads at the party level) stayed in power, but BJP's Samrat Choudhary took over as CM"}),
    ("Mohan Yadav", EntityType.PERSON, [], {"party": "BJP", "role": "Chief Minister, Madhya Pradesh", "confidence": "medium"}),
    ("Bhajanlal Sharma", EntityType.PERSON, [], {"party": "BJP", "role": "Chief Minister, Rajasthan", "confidence": "medium"}),
    ("Siddaramaiah", EntityType.PERSON, [], {"party": "Indian National Congress", "role": "Chief Minister, Karnataka", "confidence": "high"}),
    ("Chandrababu Naidu", EntityType.PERSON, [], {"party": "Telugu Desam Party", "role": "Chief Minister, Andhra Pradesh", "confidence": "high"}),
    ("Mohan Charan Majhi", EntityType.PERSON, [], {"party": "BJP", "role": "Chief Minister, Odisha", "confidence": "medium"}),
    ("Revanth Reddy", EntityType.PERSON, [], {"party": "Indian National Congress", "role": "Chief Minister, Telangana", "confidence": "high"}),
    ("Himanta Biswa Sarma", EntityType.PERSON, [], {"party": "BJP", "role": "Chief Minister, Assam", "confidence": "high"}),
    ("Rekha Gupta", EntityType.PERSON, [], {"party": "BJP", "role": "Chief Minister, Delhi", "confidence": "medium", "note": "took office Feb 2025 - before my training cutoff, but not independently re-verified"}),

    # --- Persons: major figures no longer (or never confirmed) in the
    # specific office their party now holds, post-cutoff - kept as real,
    # currently relevant figures without asserting a current title.
    ("Mamata Banerjee", EntityType.PERSON, [], {"party": "Trinamool Congress", "role": "party leader, former West Bengal CM", "confidence": "high", "note": "TMC lost the May 2026 WB election to BJP - succeeded by Suvendu Adhikari, sworn in 9 May 2026"}),
    ("M.K. Stalin", EntityType.PERSON, ["Stalin"], {"party": "Dravida Munnetra Kazhagam", "role": "party leader, former Tamil Nadu CM", "confidence": "high", "note": "DMK lost the May 2026 TN election to TVK - succeeded by Vijay, sworn in 10 May 2026", "alias_caution": "'Stalin' alone is ambiguous with the historical Soviet figure - included anyway since Indian political news context makes the intended referent clear, but flagged"}),
    ("Pinarayi Vijayan", EntityType.PERSON, [], {"party": "Communist Party of India (Marxist)", "role": "party leader, former Kerala CM", "confidence": "high", "note": "LDF lost the May 2026 Kerala election to Congress-led UDF - succeeded by V. D. Satheesan, sworn in 18 May 2026 (a ~2-week gap after the May 4 result, per a Congress leadership dispute; Vijayan is understood to have continued in a caretaker capacity in the interim, per standard convention - that specific detail is not independently confirmed)"}),
    ("Vijay", EntityType.PERSON, ["Thalapathy Vijay", "C. Joseph Vijay"], {"party": "Tamilaga Vettri Kazhagam", "role": "Chief Minister, Tamil Nadu", "confidence": "high", "note": "user-confirmed: sworn in 10 May 2026 - previously seeded only as TVK's founder, since which government post (if any) he'd take was beyond confident pre-cutoff knowledge at the time"}),
    ("Suvendu Adhikari", EntityType.PERSON, [], {"party": "Bharatiya Janata Party", "role": "Chief Minister, West Bengal", "confidence": "high", "note": "user-confirmed: sworn in 9 May 2026, succeeding Mamata Banerjee/TMC"}),
    ("V. D. Satheesan", EntityType.PERSON, ["Satheesan"], {"party": "Indian National Congress", "role": "Chief Minister, Kerala (Congress-led UDF coalition)", "confidence": "high", "note": "user-confirmed: sworn in 18 May 2026, succeeding Pinarayi Vijayan/LDF - see module docstring for the ~2-week post-election gap and why it doesn't affect any current downstream logic"}),
    ("Naveen Patnaik", EntityType.PERSON, [], {"party": "Biju Janata Dal", "role": "party leader, former Odisha CM", "confidence": "high", "note": "BJD lost the June 2024 Odisha election to BJP"}),
    ("Samrat Choudhary", EntityType.PERSON, [], {"party": "Bharatiya Janata Party", "role": "Chief Minister, Bihar", "confidence": "high", "note": "user-confirmed: made CM on 15 April 2026, replacing Nitish Kumar - the ruling NDA coalition itself didn't change, only which party leads it (JD(U) to BJP)"}),
]


def seed_entities(db: Session) -> tuple[int, int]:
    """Upserts ENTITY_SEED, matched on `name` (Entity.name is unique).
    Safe to re-run - an existing entity's aliases/metadata/type are synced
    to the seed rather than left stale, mirroring seed_jurisdictions'
    "safe to re-run" contract. Returns (inserted, updated).
    """
    existing = {entity.name: entity for entity in db.query(Entity)}

    inserted = 0
    updated = 0
    for name, entity_type, aliases, metadata in ENTITY_SEED:
        row = existing.get(name)
        if row is None:
            db.add(Entity(name=name, type=entity_type, aliases=aliases, entity_metadata=metadata))
            inserted += 1
        elif row.type != entity_type or row.aliases != aliases or row.entity_metadata != metadata:
            row.type = entity_type
            row.aliases = aliases
            row.entity_metadata = metadata
            updated += 1

    db.commit()
    return inserted, updated
