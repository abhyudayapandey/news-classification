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
