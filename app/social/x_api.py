"""The official X API v2 (recent search), pay-per-use - explicitly NOT a
third-party reseller and NOT self-scraping, per direct instruction. This
is the platform's first genuinely metered-cost feature: every successful
call bills real money per post read (settings.x_cost_per_post_usd), and
that cost is what app/social/pipeline.py accumulates into
EntitySocialConfig.x_spend_usd and compares against each client's
ClientSubject.x_spend_ceiling_usd.

Never called unless an entity currently has at least one active client
with x_access=True (app/social/pipeline.py's _entity_has_active_x_access)
- there is no global "turn on X" switch anywhere in this codebase, by
design (see EntitySocialConfig's module docstring for why collapsing the
two layers into one would either waste money or leak access).
"""

from datetime import datetime, timezone

import requests

from app.config import settings
from app.models import Entity
from app.models.enums import SocialSource
from app.social.base import FetchedMention, SocialFetcher

_SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
_REQUEST_TIMEOUT_SECONDS = 15


class XFetcher(SocialFetcher):
    source = SocialSource.X

    def __init__(self, bearer_token: str | None = None):
        self.bearer_token = bearer_token or settings.x_api_bearer_token
        if not self.bearer_token:
            raise ValueError("X_API_BEARER_TOKEN is not set - required to use XFetcher.")

    def fetch(self, entity: Entity, max_results: int) -> list[FetchedMention]:
        # Same one-query-per-canonical-name tradeoff as YouTubeFetcher -
        # querying every alias would multiply real per-post-read cost, not
        # just quota, so it's an even sharper tradeoff here.
        # X's own API enforces a 10-100 bound on max_results - a caller
        # asking for fewer than 10 still gets (and is billed for) up to
        # 10, a real cost-relevant floor worth being honest about rather
        # than silently clamping and forgetting.
        api_max_results = max(10, min(max_results, 100))
        params = {
            "query": f'"{entity.name}" -is:retweet',
            "max_results": api_max_results,
            "tweet.fields": "created_at,author_id",
        }
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        response = requests.get(_SEARCH_URL, params=params, headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json().get("data", [])

        # Not re-truncated to the caller's original max_results: the
        # billable read count (this list's length) must reflect exactly
        # what X actually returned and charged for, per this module's
        # docstring - silently dropping items here would under-count real
        # spend, the one thing this feature exists to get right.
        mentions = []
        for post in data:
            post_id = post.get("id")
            if not post_id:
                continue
            posted_at = None
            if post.get("created_at"):
                posted_at = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00")).astimezone(
                    timezone.utc
                )
            mentions.append(
                FetchedMention(
                    content_text=post.get("text", ""),
                    author=post.get("author_id"),  # numeric id - resolving to a handle costs a second call/spend
                    posted_at=posted_at,
                    url=f"https://x.com/i/web/status/{post_id}",
                )
            )
        return mentions
