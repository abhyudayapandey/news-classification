# News Framing Platform — What's Changed Since PR #14

**Purpose of this document:** a self-contained handoff summary of everything built in this
repository since PR #14 ("Show newest-published articles first in the admin queue"), for
briefing a separate Claude Code session/project that doesn't have this repo's git history.
For the full current architecture (not just the delta), see `news-framing-platform-poc.md`
in this repo — this document is the changelog; that one is the living reference.

**Covers:** PR #15 through PR #25 (current open PR), i.e. everything after PR #14.

---

## 1. One-paragraph context

This is an India-focused news aggregation platform. It clusters articles about the same
story across outlets and tags each one **pro-establishment / anti-establishment / apolitical**
(not a US-style left/right axis). A human admin reviews every system-generated tag before
publish. Beyond the public (B2C) site, it now also has: per-entity subject tracking with a
separate sentiment axis, X/YouTube social-media listening, and a B2B client portal for
PR/political-consultancy clients to track specific people/parties across news + social.

At PR #14, only the first two paragraphs above existed (article clustering/tagging + admin
review). Everything else below was built afterward.

---

## 2. Small fixes/polish immediately after PR #14 (PRs #15-#17)

- **PR #15** — Added Jurisdiction and Ruling-party columns directly to the admin queue table
  (previously only visible after opening an article's full review page), so an admin can judge
  an obvious case straight from the list.
- **PR #16** — Public home page: same-sentiment story cards (e.g. "3 pro", no divergence) got a
  hover popover listing the other outlets' headlines ("Also reported by"), clickable through to
  the existing `/compare/{cluster_id}` page. Also made the article representing a cluster+tag
  deterministic (earliest-published, not "whichever the query happened to return first").
- **PR #17** — Fixed a regression from #16: switching the displayed representative to the
  earliest article had also switched the *sort key* to that earliest timestamp, so a story with
  a brand-new follow-up from another outlet could get pushed off the home page as if stale.
  Sort key (most recent article in the cluster+tag) and display timestamp (earliest article,
  for an honest "this is the headline actually shown") are now deliberately different fields.
  Also extended the hover-popover treatment to diverging cards.

## 3. PR #18 — Phase 5: Entity tagging + subject-specific sentiment

New capability: track a **subject** (a person or party) across articles, independent of the
article's own establishment framing.

- New `Entity` model (name, type person/party, aliases, metadata) and `ArticleEntity` join
  table (entity_id, article_id, prominence).
- New **subject sentiment** axis: favorable/unfavorable/neutral toward a specific entity,
  independent of whether the article itself reads pro- or anti-establishment (an article can be
  anti-establishment while being complimentary toward the specific opposition figure quoted
  criticizing the government — two different axes).
- This is what makes "show me every article about Subject X over time" and later the entire
  B2B direction possible.

## 4. PR #19 — Phase 6: Social media listening (X + YouTube)

Previously scoped out entirely (flagged in the original planning doc as "a different product,
don't build it, position as complementary to existing tools instead"). Revisited once a real
paying B2B client made "coverage across news AND social" an actual ask.

- **Two-layer cost-control design**, because X billing is real per-read money and multiple
  clients can track the same public figure:
  - `EntitySocialConfig` (one row per Entity) — the *shared* side: is X fetching active for
    this entity, current-month spend, last-fetched timestamps. The actual paid fetch happens
    at most once per entity no matter how many clients track it.
  - `ClientSubject` extended with `x_access` (bool) + `x_spend_ceiling_usd` — the *per-client
    permission* side. A client's ceiling is compared against the entity's shared spend, not a
    per-client fractional slice, since the fetch itself is shared infrastructure.
  - The real gating check always re-derives live from `ClientSubject` at fetch time —
    `EntitySocialConfig.x_active` is a display-only cache, never the source of truth, so a
    stale cache can't cause an unauthorized or a missed fetch.
- **New `SocialMention` model** — one row per fetched X post or YouTube video, unique on
  (entity_id, source, url) so re-fetching a known post doesn't duplicate storage (though X
  still bills again for the re-read). Carries `sentiment`/`sentiment_confidence`,
  `engagement_count`, `cost_usd`, and content-derived `state`/`district`/`constituency`/
  `seat_type` geography — all computed once at storage time, never re-computed on re-fetch.
- **YouTube**: free tier, fetched for every tracked entity with no gating, 10,000-unit/day
  quota. Most-engaged-first ordering comes free from the API itself.
- **X**: gated by the two-layer design above; real dollar cost recorded per mention and rolled
  up per entity per calendar month.

## 5. PR #20 — Phase 7: B2B client portal

A structurally separate application surface (own login, own templates/router) from the
internal admin dashboard — same underlying data, different access surface.

- New `Client` (org) and `ClientUser` (login accounts) models.
- `ClientSubject` (client ↔ entity, many-to-many) with per-subject `news_access`/
  `youtube_access`/`x_access` visibility flags — all default `False`; a newly tracked subject
  shows nothing on a client's dashboard until a super admin explicitly turns each on
  (payment-gated, never implied just because tracking began).
- Tenant isolation enforced at the query layer: `published articles ↔ ArticleEntity ↔ Entity
  ↔ ClientSubject ↔ Client`, scoped to the logged-in client's own subjects only.
- Client dashboard (tracked subjects) + per-subject detail page with News/YouTube/X tabs.
- Same reviewed-only standard as the public site: only `published_tag`-based articles are ever
  shown, no unreviewed system-tag-only content, so B2B never trades accuracy for speed.

## 6. PR #21 — Fix: cache the local embedding provider

Render's free tier was re-loading the sentence-transformers embedding model on every call,
which pushed memory usage too high. Fixed by caching the provider instance instead of
constructing it repeatedly.

## 7. PR #22 — Fix: eager-load system_tag/outlet on the admin queue (N+1 fix)

The admin queue was issuing a separate query per row for `system_tag` and `outlet`. Fixed
with eager loading (`selectinload`) to collapse it to a constant number of queries regardless
of queue size.

## 8. PR #23 — Queue tabs, admin toggle-switch cleanup, social mention backfill

Three related pieces of feedback-driven work:

- **My Queue → Clients → client → subject** now has the same Pro/Anti/Apolitical sub-tabs the
  rest of the admin queue already had, so a client's pending articles are grouped by tag
  right where an admin is already working, not just visible after opening each article.
- **Admin toggle UI cleanup** — the clients list/detail pages previously showed a status badge
  + a separate enable/disable button per channel (News/YouTube/X), flagged directly as
  confusing (two separate pieces of UI to reconcile just to tell "is this on"). Replaced with a
  single flip-switch control per channel (one form + styled checkbox,
  `onchange="this.form.submit()"`). Toggling from the client *list* page now correctly returns
  to the list instead of always jumping to the detail page (a `next` hidden field, restricted
  to paths under `/admin/clients` to prevent an open-redirect). The ambiguous "$x / $y" spend
  column was relabeled to explicit "Spend $x" / "Ceiling $y" (or "Ceiling unset").
- **Social mention backfill** (`app/social/backfill.py`) — real production `SocialMention` rows
  fetched before `sentiment`/`engagement_count`/geography existed as columns were showing
  "0 views" / "-" sentiment on the client portal (not a display bug — genuinely never
  populated). New `backfill_social_mentions()` finds every row via `sentiment IS NULL` (a
  genuinely-scored row is never NULL even when NEUTRAL, so this can't false-positive), then
  re-scores sentiment, re-guesses geography where still unset, and re-fetches real YouTube
  view counts for YouTube rows still at 0. **X engagement is deliberately excluded** — a
  backfill re-read would bill again with no clean way to attribute that spend against a
  client's ceiling. Available as both a CLI command and an HTTP endpoint (Render has no shell).

## 9. PR #24 — Client portal News tab: Pro/Anti/Apolitical columns

The client portal's News tab used a single mixed 2-column grid with an inline tag badge per
card — inconsistent with the public site's own three-column Pro-Establishment/
Anti-Establishment/Apolitical layout, flagged directly ("why keep it like this?"). Replaced
with the same three-column layout, reusing the public site's own card/column macros for
visual and structural consistency between B2C and B2B.

## 10. PR #25 (open, current) — YouTube: description + genuine historical fetch

Two related YouTube improvements, prompted by direct questions about social-listening
capability limits:

- **Content analysis was title-only before this** — the video description (free in the same
  API response, previously discarded) is now combined into `content_text` as a second line,
  giving sentiment/geography scoring real additional signal.
- **Genuine historical fetch** — YouTube's `search.list` has no API-tier restriction on
  `publishedBefore`/`publishedAfter` (unlike X, see below), so a new `fetch_youtube_historical()`
  entry point (separate from the regular ongoing multi-entity scan) can pull an arbitrary past
  date range for one entity, free of extra cost.
- Confirmed and documented as a **hard limit, not a code gap**: X's `/2/tweets/search/recent`
  is capped to the last 7 days by the endpoint itself regardless of any parameter passed —
  genuine historical tweet/engagement fetch needs X's paid Pro or Enterprise tier, a real
  billing-tier decision, not something achievable via this codebase.
- Also confirmed: real YouTube video *content* (what's said, not just title/description) would
  require the YouTube Captions API, which needs OAuth ownership of the target video — blocks
  pulling transcripts for arbitrary third-party political videos entirely, independent of cost.

## 11. Also this session: `news-framing-platform-poc.md` brought current

The architecture/planning reference doc had not been touched since PR #18 (Phase 5) and still
described social listening as "explicitly parked" and the client portal as a future plan.
Updated with new Section 14 (social listening as-built), Section 15 (client portal as-built),
and Section 16 (open items below) so it no longer contradicts what's actually running.

---

## 12. Open items — not yet resolved, flagged rather than silently dropped

- **X historical-archive access tier** — a real cost/contract decision (Enterprise pricing is
  unpublished; third-party estimates run ~$42k-$50k+/month), needs a funded client need
  behind it before pursuing. Documentation: `docs.x.com/enterprise-api/getting-started/pricing`.
- **YouTube caption/transcript analysis** — blocked by the Captions API's OAuth-ownership
  requirement for third-party videos, independent of engineering cost.
- **A formal X/YouTube cost-calculation table or formula** (translating a contracted spend
  ceiling into expected read/post volume, or modeling Enterprise-tier X cost against expected
  demand) — discussed, explicitly **not yet built**.
- **Legal review of B2B commercialization** — the JSON-LD paywall-extraction tradeoff (accepted
  as POC-stage risk when content was never shown to end users) carries more risk now that it's
  tied to a paying product; not confirmed as reviewed.
