import enum


class ClassificationTag(str, enum.Enum):
    """Core framing taxonomy - Section 4.1 of the planning doc."""

    PRO_ESTABLISHMENT = "pro-establishment"
    ANTI_ESTABLISHMENT = "anti-establishment"
    APOLITICAL = "apolitical"


class ReviewDecision(str, enum.Enum):
    """Section 5: how an admin's review relates to the system tag."""

    AGREED_WITH_SYSTEM = "agreed_with_system"
    OVERRODE = "overrode"


class AdminRole(str, enum.Enum):
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class EntityType(str, enum.Enum):
    """Section 13.1: the only two entity kinds this platform tracks -
    named individuals and political parties. Ministries/generic titles
    (which app/processing/entity_triggers.py's safety net also matches)
    are deliberately NOT entities here - they're not a trackable subject
    a client could ask "show me every article about X" for."""

    PERSON = "person"
    PARTY = "party"


class EntityProminence(str, enum.Enum):
    """Section 13.1's prominence heuristic - see
    app/processing/entities.py for how this is computed."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    MENTIONED = "mentioned"


class SocialSource(str, enum.Enum):
    """Section 13's social listening capability - the two sources this
    platform fetches from, with deliberately different cost postures (see
    app/social/base.py): YouTube is free-tier and always fetched once an
    entity is tracked; X is metered per-post-read and gated per-entity on
    live ClientSubject.x_access (app/social/pipeline.py)."""

    X = "x"
    YOUTUBE = "youtube"


class SeatType(str, enum.Enum):
    """Which house a piece of content's guessed `constituency` refers to -
    Lok Sabha (MP) and Vidhan Sabha (MLA) seats are delimited independently
    of each other and of district boundaries in India, so a bare
    constituency name is ambiguous without this - the same name can even be
    both an MP and an MLA seat in the same state (Jodhpur is one real
    example). Set alongside `constituency` wherever app/processing/
    geography.py's text heuristic finds one named - either an explicit
    phrase ("Baramati Lok Sabha seat") or a bare mention resolved against
    app/data/constituency_seed.py's seeded name list; this is always
    content-derived, never anything manually assigned to an Entity - see
    that seed module's own docstring for what's actually seeded so far.
    """

    MP = "mp"
    MLA = "mla"


class SubjectSentiment(str, enum.Enum):
    """Section 13.2's subject-specific sentiment axis - deliberately named
    favorable/unfavorable/neutral rather than reusing pro/anti-establishment
    wording, since this measures sentiment toward one specific entity, not
    the article's framing relative to the government in power. The two
    axes are independent and must not be visually or terminologically
    conflated - see ArticleEntity's module docstring."""

    FAVORABLE = "favorable"
    UNFAVORABLE = "unfavorable"
    NEUTRAL = "neutral"
