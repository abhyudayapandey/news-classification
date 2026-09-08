"""YouTube Data API v3 - free tier, always fetched once an entity is
tracked, no cost gating (Section 13's own framing). Not entirely free of
constraints, worth flagging: the free tier is a 10,000-unit/day quota, and
a search.list call costs 100 units - roughly 100 searches/day across every
tracked entity combined before hitting it, not literally unlimited. A
quota-exceeded response surfaces as a normal HTTP error here, caught and
recorded per-entity by app/social/pipeline.py like any other fetch
failure - not specially handled, since there's nothing more useful to do
about it than wait for the daily reset.
"""

from datetime import datetime, timezone

import requests

from app.config import settings
from app.models import Entity
from app.models.enums import SocialSource
from app.social.base import FetchedMention, SocialFetcher

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_REQUEST_TIMEOUT_SECONDS = 15


class YouTubeFetcher(SocialFetcher):
    source = SocialSource.YOUTUBE

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.youtube_api_key
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY is not set - required to use YouTubeFetcher.")

    def fetch(self, entity: Entity, max_results: int) -> list[FetchedMention]:
        # Query on the canonical name only, not every alias - querying N
        # aliases would mean N searches (and N x the quota cost) for one
        # entity. A deliberate coverage-vs-cost tradeoff, same shape as
        # app/data/entity_seed.py's bare-surname alias calls, just for API
        # quota instead of match precision.
        params = {
            "key": self.api_key,
            "q": entity.name,
            "part": "snippet",
            "type": "video",
            "order": "date",
            "maxResults": max_results,
        }
        response = requests.get(_SEARCH_URL, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        items = response.json().get("items", [])

        mentions = []
        for item in items:
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            if not video_id:
                continue
            published_at = None
            if snippet.get("publishedAt"):
                published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")).astimezone(
                    timezone.utc
                )
            mentions.append(
                FetchedMention(
                    content_text=snippet.get("title", ""),
                    author=snippet.get("channelTitle"),
                    posted_at=published_at,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                )
            )
        return mentions
