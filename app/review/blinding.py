"""Section 5 blinding rules for the admin review view.

Two things get redacted, both to the same placeholder:
1. The outlet's own name, wherever it appears in the headline/body - e.g.
   "The Hindu has learnt that..." would otherwise defeat the outlet-hidden
   rule even though outlet_id itself is never shown, since the name is
   right there in the text.
2. Generic self-referential phrases ("this newspaper", "this publication",
   ...) that don't literally use the outlet's name but still identify the
   piece as self-reported.

What's deliberately NOT redacted, per Section 5: bylines/reporter names,
and PTI/ANI wire-copy attribution or an outlet's distinctive writing style
- recognizing unedited wire copy (or its absence) is part of what the
review is meant to surface.

One outlet-specific judgment call worth flagging: outlet names are matched
exactly as configured (config/outlets.yaml), e.g. "The Hindu" - not a
stripped "Hindu" variant. Stripping "The " would make "Hindu" alone a match
target, which collides with an unrelated, common word (the religion) and
would over-redact real content. If you add outlets whose bare name is
ambiguous like that, don't add automatic prefix-stripping here - it's a
correctness trap, not a coverage gap.
"""

from app.text_utils import boundary_pattern

REDACTION_PLACEHOLDER = "[self-reference removed]"

_GENERIC_SELF_REFERENCE_PHRASES = [
    "this newspaper",
    "this publication",
    "this daily",
    "this website",
    "this news portal",
    "this portal",
    "this channel",
    "this news channel",
    "this news agency",
]


def redact_self_references(text: str, outlet_name: str) -> str:
    result = boundary_pattern(outlet_name).sub(REDACTION_PLACEHOLDER, text)
    for phrase in _GENERIC_SELF_REFERENCE_PHRASES:
        result = boundary_pattern(phrase).sub(REDACTION_PLACEHOLDER, result)
    return result


def blind_headline_and_body(headline: str, body_text: str, outlet_name: str) -> tuple[str, str]:
    return (
        redact_self_references(headline, outlet_name),
        redact_self_references(body_text, outlet_name),
    )
