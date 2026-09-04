"""Shared text-matching helpers used across entity detection (Phase 2) and
blinding/redaction (Phase 3).
"""

import re


def boundary_pattern(term: str) -> re.Pattern:
    """Case-insensitive whole-term match. Plain \\b fails on terms ending in
    punctuation (e.g. r"\\bcpi\\(m\\)\\b" never matches "CPI(M)" - both ")"
    and whatever follows it are non-word characters, so there's no \\W-\\w
    transition for the trailing \\b to anchor on). Lookarounds that check
    "not preceded/followed by an alphanumeric" avoid that trap and work
    correctly at string boundaries too. See app/processing/entity_triggers.py
    for where this bug was first caught.
    """
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE)
