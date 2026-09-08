"""Section 13 social listening: fetcher interface for the two sources
(YouTube, X). Deliberately not the same ABC as app/llm/base.py's
providers - those classify text that already exists; these fetch new
content from an external, real-money-adjacent API, a different enough
shape (and a different enough risk profile - see app/social/x_api.py)
that sharing an interface would blur two things worth keeping distinct.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.models import Entity
from app.models.enums import SocialSource


@dataclass
class FetchedMention:
    content_text: str
    author: str | None
    posted_at: datetime | None
    url: str
    # Views (YouTube) or retweet+like+reply+quote (X) - see each fetcher's
    # own module for exactly what feeds this. Used only for "most engaged
    # first" ordering/display (SocialMention.engagement_count's docstring),
    # never for cost accounting.
    engagement_count: int = 0


class SocialFetcher(ABC):
    #: Which SocialMention.source value this fetcher populates.
    source: SocialSource

    @abstractmethod
    def fetch(self, entity: Entity, max_results: int, lookback_days: int | None = None) -> list[FetchedMention]:
        """Returns exactly what the API returned for this call - the
        length of this list is the real billable read count for a metered
        source (app/social/x_api.py), even before any deduplication against
        what's already stored. Callers must not filter/truncate this list
        before using its length for cost accounting.

        `lookback_days` narrows the API's own search window (None means
        "the API's own default window", not "unlimited history" - X's
        recent-search endpoint only ever covers the last 7 days regardless
        of this value). The returned list is ordered most-engaged-first,
        per direct instruction - implementations achieve this either by
        asking the API to sort that way (YouTube's `order=viewCount`) or,
        where the API offers no such sort (X's recent-search), by fetching
        the API's own default order and re-sorting the full, un-truncated
        result locally before returning it.
        """
        raise NotImplementedError
