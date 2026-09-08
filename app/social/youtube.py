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

from datetime import datetime, timedelta, timezone

import requests

from app.config import settings
from app.models import Entity
from app.models.enums import SocialSource
from app.social.base import FetchedMention, SocialFetcher

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_REQUEST_TIMEOUT_SECONDS = 15


class YouTubeFetcher(SocialFetcher):
    source = SocialSource.YOUTUBE

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.youtube_api_key
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY is not set - required to use YouTubeFetcher.")

    def fetch(self, entity: Entity, max_results: int, lookback_days: int | None = None) -> list[FetchedMention]:
        # Query on the canonical name only, not every alias - querying N
        # aliases would mean N searches (and N x the quota cost) for one
        # entity. A deliberate coverage-vs-cost tradeoff, same shape as
        # app/data/entity_seed.py's bare-surname alias calls, just for API
        # quota instead of match precision.
        # order=viewCount, not date: most-engaged-first is satisfied
        # directly by the search API itself for YouTube (unlike X, which
        # has no equivalent sort - see XFetcher.fetch), so no local
        # re-sorting is needed here.
        params = {
            "key": self.api_key,
            "q": entity.name,
            "part": "snippet",
            "type": "video",
            "order": "viewCount",
            "maxResults": max_results,
        }
        if lookback_days is not None:
            since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
            params["publishedAfter"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        response = requests.get(_SEARCH_URL, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        items = response.json().get("items", [])

        video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
        view_counts = self._fetch_view_counts(video_ids)

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
                    engagement_count=view_counts.get(video_id, 0),
                )
            )
        return mentions

    def _fetch_view_counts(self, video_ids: list[str]) -> dict[str, int]:
        """search.list (above) never returns statistics - a second,
        separate videos.list call (also within the free daily quota, at a
        much cheaper 1 unit each vs. search.list's 100) is required to get
        each video's view count for engagement ordering/display. A failure
        here degrades to "engagement unknown" (0) rather than failing the
        whole fetch - the mentions themselves are still valid without it.
        """
        if not video_ids:
            return {}
        try:
            response = requests.get(
                _VIDEOS_URL,
                params={"key": self.api_key, "id": ",".join(video_ids), "part": "statistics"},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
        except requests.RequestException:
            return {}
        return {item["id"]: int(item.get("statistics", {}).get("viewCount", 0)) for item in items if item.get("id")}
