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
