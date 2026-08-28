# News Framing Platform — POC (Phase 1: Foundation)

India-focused news aggregation POC that classifies articles by topic and by
pro-establishment / anti-establishment framing, with a human-in-the-loop
admin review layer. See `news-framing-platform-poc.md` (the planning doc)
for the full product design — this README covers what's actually built and
how to run it.

**This is Phase 1 only**: project scaffolding, the full database schema,
and RSS ingestion with basic wire-copy dedup. No clustering, no
classification, no admin UI, no website yet. Everything here is built so
those later phases slot in without a schema rewrite.

---

## 1. Cost architecture — why these choices

Everything below runs on free tiers. Nothing here requires a credit card.

### Database: Neon, not Supabase

Both Neon and Supabase offer a free Postgres tier with `pgvector`
pre-installable. I picked **Neon** for this project:

- **We don't use Supabase's other features.** Supabase's free tier is
  attractive largely because of bundled Auth, Storage, and Realtime — but
  this platform is built API-first with its own FastAPI backend and its own
  `Admin` table/roles (Section 3 of the planning doc), so we'd never touch
  Supabase Auth. Once you strip those out, Supabase's free tier is "just
  Postgres" with a catch: **the project auto-pauses after a week of
  inactivity** and needs a manual unpause from the dashboard. For a POC you
  run ingestion on sporadically, that's a real annoyance.
- **Neon branching fits the Alembic workflow well.** Neon lets you fork the
  database (schema + data) into a branch, which is a natural place to test
  a risky migration before applying it to the branch your app actually
  points at — useful across three phases of schema evolution.
- **Neon scales compute to zero automatically** between requests, which
  keeps free-tier usage low for something that runs in bursts (a manual
  ingestion run) rather than continuously.

Either would technically work here — if you already have a Supabase project
you'd rather standardize on, the only Neon-specific piece is the connection
string in `.env`; nothing in the code is Neon-specific.

### No paid dependency introduced

`requirements.txt` is entirely open-source, pip-installable packages
(FastAPI, SQLAlchemy, Alembic, feedparser, BeautifulSoup, PyYAML, psycopg).
RSS feeds are free and public. `.env.example` includes **placeholders** for
`OPENAI_API_KEY` / `GEMINI_API_KEY` — they are read into config but nothing
in Phase 1 calls either API. If Phase 2 needs something paid beyond what
you already have credit for, I'll flag it before adding it, with the free
alternative I considered and why it fell short.

### Provider-swappable by design, for Phase 2

Phase 2 (clustering + classification) needs embeddings and an LLM call.
Per your instruction, the seam for that is built now even though nothing
uses it yet:

- `app/llm/base.py` defines `EmbeddingProvider` and `ClassificationProvider`
  as abstract interfaces, plus factory functions that will read
  `settings.embedding_provider` / `settings.llm_provider`.
- `.env` / `app/config.py` already carry `EMBEDDING_PROVIDER`,
  `LLM_PROVIDER` (`local` / `openai` / `gemini`), plus model name and API
  key fields for all three.
- Phase 2 work is then: implement one class per provider per interface, and
  the factory picks the right one from config. Calling code (the classifier,
  the clustering job) never hardcodes a provider — you'll be able to run the
  free local model and either paid API side-by-side by flipping an env var.
- The `vector` Postgres extension is enabled now (see migration
  `1f76f92005cd_enable_pgvector_extension.py`) so Phase 2 can add an
  embedding column without a fresh extension migration. No embedding
  columns exist yet — that's Phase 2's job once clustering is actually being
  built.

---

## 2. Project structure

```
app/
  main.py              FastAPI app (health, articles, manual ingest trigger)
  config.py            Settings from .env (pydantic-settings)
  db.py                SQLAlchemy engine/session, declarative Base
  cli.py                Manual CLI: `python -m app.cli ingest|show-articles`
  models/               SQLAlchemy models — one file per Section 6 entity
  schemas/              Pydantic response models for the API
  routers/               FastAPI routers (health, articles, ingestion)
  ingestion/
    outlets_config.py   Loads config/outlets.yaml, upserts into `outlets`
    feed_fetcher.py      Fetches + parses one RSS feed into normalized entries
    dedup.py             Section 5 wire-copy dedup (content hashing)
    pipeline.py          Orchestrates one full ingestion run
    verify_feeds.py      Standalone feed health check (no DB) — see below
  llm/
    base.py              Phase 2 provider interfaces (not used yet)
alembic/                 Migrations (env.py wired to app's models/settings)
config/
  outlets.yaml           Config-driven outlet list (name + RSS URL)
```

## 3. Database schema (Section 6, implemented as-is)

All seven entities from the planning doc's Section 6 are modeled now, even
though Phase 1 only ever populates `Outlet` and `Article`:

| Table | Populated in Phase 1? | Notes |
|---|---|---|
| `outlets` | Yes | Synced from `config/outlets.yaml` on every ingestion run |
| `articles` | Yes | `cluster_id`, `published_tag` stay NULL until later phases |
| `system_tags` | No (table exists, empty) | 1:1 with `articles`; Phase 2's classifier writes here |
| `reviews` | No (table exists, empty) | One-to-many now so multi-admin reconciliation can be added later without a migration; Phase 3 only ever inserts one row per article |
| `story_clusters` | No (table exists, empty) | Phase 2's clustering job populates this |
| `jurisdiction_ruling_parties` | No (table exists, empty) | Manually maintained lookup table — see the planning doc's warning about keeping it current as governments change |
| `admins` | No (table exists, empty) | No auth fields yet; those land with the Phase 3 admin UI |

Two fields you specifically asked to keep intact:

- **`system_tags.confidence_score`** — a dedicated table (not inlined JSON
  on `Article`) so the Phase 3 super-admin analytics view (system tag vs.
  admin decision, calibration over time) is a plain join/aggregate against
  a typed column, not a JSON-path query.
- **`reviews`** — modeled as a genuine one-to-many table with `admin_id`,
  `final_tag`, `decision` (`agreed_with_system` / `overrode`), and
  `timestamp`, exactly as specced. This is what will let a future
  super-admin dashboard compute admin throughput, disagreement rate with
  the system tag, and per-admin calibration — none of that is possible if
  a review is just a column overwritten in place.

`Article.duplicate_of_id` is the one addition beyond Section 6's literal
field list — it's how the Section 5 wire-copy dedup is represented (see
below). It's additive, not a simplification of anything specced.

Migrations: `alembic/versions/`
1. `1f76f92005cd_enable_pgvector_extension.py` — `CREATE EXTENSION vector`
2. `4195c7a673a2_initial_schema.py` — all seven tables, generated via
   `alembic revision --autogenerate` from the models and verified by
   actually applying it to a local Postgres 16 + pgvector instance during
   development (this sandbox can't reach Neon directly — see §7).

## 4. RSS ingestion + dedup

`config/outlets.yaml` lists outlets as `name` + `rss_feed_url` + `is_active`.
Adding, disabling, or fixing a feed is a one-line YAML edit — no code or
migration needed. On every ingestion run, this file is upserted into the
`outlets` table (matched by name); removing an outlet from the YAML doesn't
delete its row or its articles, it just stops fetching it.

Pipeline per outlet (`app/ingestion/pipeline.py`):
1. Fetch + parse the feed (`feedparser`); HTML in the summary/content is
   stripped to plain text.
2. Skip entries whose `url` is already in the DB (idempotent re-runs — you
   can run ingestion as often as you like without duplicate rows).
3. For new entries, hash the normalized headline+body text
   (`app/ingestion/dedup.py`). If a canonical article with the same hash
   exists within a 72-hour window, the new row is inserted but linked via
   `duplicate_of_id` rather than treated as a new story — this is the
   first-pass version of Section 5's "identical PTI/ANI wire copy dedup."
   Every outlet's copy is still stored (useful later for analytics on how
   widely a wire story ran); Phase 2/3 code should filter
   `WHERE duplicate_of_id IS NULL` to get one row per story.

**Known limitation, by design for a first pass**: this only catches
byte-for-byte-ish identical copy after whitespace/case normalization. An
outlet that lightly edits wire copy (adds a paragraph, trims a line) won't
be caught. A fuzzy/near-duplicate pass is a reasonable Phase 2 add-on once
clustering embeddings exist anyway — no need to build two similarity
systems in parallel.

**Also worth flagging**: RSS feeds generally only carry a headline +
summary/teaser, not the full article body. `body_text` stores whatever the
feed provides. Full-body extraction would need a per-outlet scraper, which
is fragile and arguably against some outlets' terms — that's a real
decision to make before Phase 3's admin review (which needs full body
text), not something to quietly paper over now.

## 5. Outlet feed URLs — verify before relying on them

`config/outlets.yaml` ships with The Hindu, The Indian Express, and NDTV.

**I could not verify these live.** This build environment's outbound
network is restricted to an allowlist (package registries, GitHub,
Anthropic) that doesn't include news domains — every attempt to reach
`thehindu.com`, `indianexpress.com`, or `feedburner.com` (NDTV's feed host)
came back as a policy-level 403 from the network's egress proxy, not a
feed-side error. So these three URLs are the outlets' documented,
long-standing feed endpoints, not URLs I fetched and confirmed during this
session.

Run this yourself before your first real ingestion run, from a machine with
normal internet access:

```bash
python -m app.ingestion.verify_feeds
```

It fetches each configured feed (no DB writes) and reports OK/FAIL/EMPTY
plus the newest headline for each. If a URL is stale, fix it directly in
`config/outlets.yaml` — nothing else needs to change.

I *did* fully verify the ingestion pipeline itself — fetch → parse →
dedup → persist → idempotent re-run — against two local mock RSS feeds
(one deliberately containing a duplicate "PTI wire copy" item), and
confirmed the FastAPI endpoints and CLI both work end-to-end. That's a
proxy for the pipeline logic being correct; it doesn't substitute for you
confirming the three real feed URLs above are currently live.

This was confirmed to be a sandbox network policy restriction (a 403 from
the build environment's egress proxy on every attempt, including to
`render.com` itself), not a feed problem or a config mistake. §6 below
covers deploying to Render specifically to get real network access for
testing this.

## 6. Deploying to Render (to test ingestion with real network access)

The build environment this project was developed in cannot reach outside
domains other than a small dev-infra allowlist, so RSS feeds could never be
fetched live during development (§5). Render's free tier gives the app
itself a real internet connection to test against.

**Render over Railway**: Railway removed its unconditional free tier in
August 2024 — new accounts now get a one-time $5 trial credit (30 days),
after which continued use needs a paid Hobby plan. Render still has a
genuine, ongoing free tier: a free web service (512 MB RAM, 750 instance
hours/month shared across your account, no credit card required to sign
up), and cron jobs are natively supported on the free plan too if you later
want scheduled ingestion. The only Render free-tier limitation that
matters here: the web service spins down after 15 minutes idle and takes
up to ~60s to wake on the next request — fine for manual testing, not
something to build a real-time product on.

**Important caveat before you start**: this Claude Code session's sandbox
cannot reach `render.com` either (same policy block, confirmed by testing
it directly) — so once deployed, I can't hit the deployed URL, trigger
ingestion, or inspect results myself. You'll need to do the actual
triggering/checking (browser, curl, or the Render dashboard logs) and paste
results back here if you'd like help interpreting them. What deploying does
give us is an environment where the *app* has unrestricted outbound access,
which is the actual blocker — I just can't self-verify it from inside this
session.

### 6.1 One-time setup

1. Push this branch to GitHub (already done if you're reading this from the
   repo).
2. Sign up at [render.com](https://render.com) — no credit card needed for
   the free tier.
3. Dashboard → **New +** → **Blueprint** → connect this GitHub repo. Render
   will detect `render.yaml` at the repo root and propose the
   `news-classification-api` web service on the free plan.
4. Before the first deploy, set these environment variables in the Render
   dashboard (they're marked `sync: false` in `render.yaml`, meaning Render
   won't ask you to hardcode them in the file — you set them once, in the
   dashboard):
   - `DATABASE_URL` — your Neon connection string, pasted exactly as Neon
     gives it to you (§7.3 explains why you don't need to add `+psycopg`
     by hand). Pointing this at the **same** Neon database you use locally
     is fine and probably what you want — ingested articles land in one
     place either way. If you'd rather keep deployed-test data separate,
     create a Neon branch first and use its connection string here instead.
   - `OPENAI_API_KEY` / `GEMINI_API_KEY` — leave blank, unused in Phase 1.
5. Deploy. Render runs `pip install -r requirements.txt && alembic upgrade
   head` as the build step (see the comment in `render.yaml` for why
   migrations run here instead of a pre-deploy command — that feature
   needs a paid instance type), then starts the API with `uvicorn`.

### 6.2 Verify against real feeds

Once the deploy finishes, open `https://<your-service>.onrender.com/docs`
in a browser (the first hit after idle takes up to ~60s to wake up):

1. Try `GET /health` — confirms the deployed app can reach Neon.
2. Try `POST /ingest/run` — this is the real test: the deployed instance
   fetches all three configured feeds with unrestricted network access. The
   response is the same per-outlet summary the CLI prints
   (`fetched`/`inserted_new`/`inserted_duplicate`/`skipped_existing`/`error`)
   — an `error` field on any outlet means that specific feed URL is
   actually broken, not a network policy artifact.
3. Try `GET /articles?limit=20` — confirms real articles landed in Neon.

If you want me to help interpret the results, paste the `/ingest/run`
response (or a Render log excerpt) back into this conversation.

## 7. Setup

### 7.1 Create the free Postgres database (Neon)

1. Sign up at [neon.tech](https://neon.tech) (free tier).
2. Create a project. Note the connection string from the dashboard — it
   looks like `postgresql://<user>:<password>@<host>/<dbname>?sslmode=require`.
3. `pgvector` ships with Neon; you don't need to install anything, just run
   the migration in step 6.3 (it runs `CREATE EXTENSION IF NOT EXISTS vector`).

### 7.2 Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 7.3 Configure and migrate

```bash
cp .env.example .env
# Edit .env: paste your Neon connection string into DATABASE_URL, exactly as
# Neon's dashboard gives it to you (plain postgresql://...). app/config.py
# normalizes postgresql:// and postgres:// to the +psycopg driver
# automatically, so you don't need to edit the string by hand - this project
# standardized on psycopg3, and a bare postgresql:// URL would otherwise
# make SQLAlchemy default to psycopg2 (not installed), which fails loudly
# ("No module named 'psycopg2'") the first time anything touches the DB.

alembic upgrade head
```

### 7.4 Verify feed URLs, then ingest

```bash
python -m app.ingestion.verify_feeds   # confirm the 3 configured feeds are live
python -m app.cli ingest               # run ingestion once
python -m app.cli show-articles        # confirm articles landed in the DB
```

### 7.5 Run the API (optional, for Phase 1 verification)

```bash
uvicorn app.main:app --reload
```

- `GET /health` — DB connectivity check
- `GET /articles?limit=20&include_duplicates=false` — list ingested articles
- `POST /ingest/run` — trigger the same ingestion the CLI runs

This is **not** the admin review API — that's Phase 3, and it must blind
the outlet from admins per Section 5. `/articles` is an unauthenticated
debug endpoint for confirming Phase 1 works, nothing more.

## 8. What's deliberately not here yet

- Clustering (Phase 2)
- Establishment pre-filter / pro-anti-apolitical classification (Phase 2)
- Admin review queue, blinding, self-reference redaction (Phase 3)
- Super-admin analytics dashboard (Phase 3) — the `system_tags` and
  `reviews` schema is ready for it, nothing more
- End-user website (later)
- Any auth (Admin table has no password/session fields yet)

## 9. Known gaps carried over from the planning doc

Per Section 11 of the planning doc: 48-hour SLA escalation, multi-admin
tie-breaking, the secondary "tone" axis, and a published methodology
document are all explicitly out of scope for the whole POC, not just
Phase 1.
