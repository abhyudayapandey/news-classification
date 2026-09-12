# News Framing Platform — POC

India-focused news aggregation POC that classifies articles by topic and by
pro-establishment / anti-establishment framing, with a human-in-the-loop
admin review layer. See `news-framing-platform-poc.md` (the planning doc)
for the full product design — this README covers what's actually built and
how to run it.

**Phases 1-7 are built**: project scaffolding and the full database schema
plus RSS ingestion with wire-copy dedup (Phase 1); embedding-based topic
clustering and pro/anti/apolitical classification with jurisdiction/ruling-
party resolution (Phase 2 — see §9); the login-gated admin/super-admin
review UI - queueing, blinding, confirm/override, account management, and
oversight views (Phase 3 — see §12); the public end-user site - three
framing columns, cross-outlet agreement/divergence, and date browsing
(Phase 4 — see §13); entity tagging + subject-specific sentiment -
the data-layer groundwork for a future B2B client portal, not the portal
itself (Phase 5 — see §14); social media listening (X + YouTube) with
per-client, per-entity cost controls on the metered X source - the
platform's first genuinely metered-cost feature (Phase 6 — see §15); and
the actual B2B client portal - super-admin client/subject/access
management plus a client-facing login and read-only social-listening
dashboard, scoped so each client sees only their own tracked entities and
their own contract (Phase 7 — see §16).

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

### Provider-swappable by design (built in Phase 1, populated in Phase 2)

Phase 1 built the seam - `app/llm/base.py`'s `EmbeddingProvider` and
`ClassificationProvider` interfaces, plus `EMBEDDING_PROVIDER`/
`LLM_PROVIDER` config - before either provider existed, specifically so
Phase 2 could implement providers without redesigning how calling code
reaches them. Phase 2 (§9) delivered on that: `app/llm/factory.py` now
returns a concrete provider per config, calling code never hardcodes one,
and OpenAI/Gemini are real, working implementations behind the same
interface as the local model - flipping `LLM_PROVIDER` is the entire
difference between free and billed. See §9.3 for the resource tradeoffs
behind which provider does what.

The `vector` Postgres extension enabled in Phase 1 is now in active use:
`articles.embedding` (pgvector, 384 dimensions) stores the local model's
output - see §9.1.

---

## 2. Project structure

```
app/
  main.py              FastAPI app - session middleware + all routers
  config.py            Settings from .env (pydantic-settings)
  db.py                SQLAlchemy engine/session, declarative Base
  constants.py         Fixed technical constants (e.g. EMBEDDING_DIM)
  text_utils.py        Shared boundary-matching regex (entity detection + redaction)
  cli.py               Manual CLI - ingest, process, assign-queue, create-admin, etc.
  models/              SQLAlchemy models — one file per Section 6 entity (+ Phase 2/3 fields)
  schemas/             Pydantic response models for the JSON APIs
  routers/             FastAPI routers - JSON APIs (health/articles/ingestion/processing/
                       clusters/admin-data/queue) plus admin_ui.py (the Phase 3 HTML UI)
  templates/           Jinja2 templates for the admin/super-admin UI (Phase 3)
  auth/                Phase 3: bcrypt hashing, session-based auth dependencies
  review/              Phase 3: blinding, queue assignment, scraping, review-listing queries
  ingestion/           Phase 1: RSS fetch, dedup, ingestion pipeline
    outlets_config.py  Loads config/outlets.yaml, upserts into `outlets`
    feed_fetcher.py    Fetches + parses one RSS feed into normalized entries
    dedup.py           Section 5 wire-copy dedup (content hashing)
    pipeline.py        Orchestrates one full ingestion run
    verify_feeds.py    Standalone feed health check (no DB)
  processing/          Phase 2: clustering + classification orchestration
    clustering.py      Incremental nearest-neighbor clustering (pgvector)
    topics.py          Topic label assignment (embedding similarity)
    entity_triggers.py Section 4.3 entity-trigger safety net (keyword/regex)
    jurisdiction.py    Jurisdiction guessing + ruling-party lookup
    pipeline.py         Orchestrates one full processing run
  llm/                 Embedding + classification providers
    base.py            Provider interfaces (EmbeddingProvider, ClassificationProvider)
    factory.py         Selects concrete provider from config
    local_embedding.py Local, free (fastembed/onnxruntime, no PyTorch)
    local_classification.py  Local, free (embedding-similarity zero-shot)
    openai_provider.py Paid, opt-in
    gemini_provider.py Paid, opt-in
    schema.py          Shared structured-output schema/prompt (OpenAI + Gemini)
    similarity.py       Cosine similarity / softmax helpers
  data/
    jurisdiction_seed.py  Section 4.2 lookup table seed data
alembic/                 Migrations (env.py wired to app's models/settings)
config/
  outlets.yaml           Config-driven outlet list (name + RSS URL)
```

## 3. Database schema (Section 6, implemented as-is)

All seven entities from the planning doc's Section 6 are modeled now. As of
Phase 3, all seven are populated:

| Table | Populated as of | Notes |
|---|---|---|
| `outlets` | Phase 1 | Synced from `config/outlets.yaml` on every ingestion run |
| `articles` | Phase 1 (+ Phase 2/3 fields) | `published_tag` set from a `Review`, for all three tags including apolitical (Phase 4 update — see §12.2); `assigned_admin_id`/`queued_at` added in Phase 3 |
| `story_clusters` | Phase 2 | Populated by `app/processing/clustering.py` |
| `system_tags` | Phase 2 | 1:1 with `articles`; written by `app/processing/pipeline.py` |
| `jurisdiction_ruling_parties` | Phase 2 (seeded) | Manually maintained lookup table — see §9.4 for what's seeded and what needs verification |
| `admins` | Phase 3 | `username`/`password_hash`/`is_active` added for login (§12.1) |
| `reviews` | Phase 3 | One-to-many so multi-admin reconciliation can be added later without a migration; only one row is ever created per article today |

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

## 5. Outlet feed URLs

`config/outlets.yaml` ships with The Hindu, The Indian Express, and NDTV.

**Verified live** (2026-08-28) via the Render deployment described in §6,
since this project's build environment has no outbound access to news
domains (confirmed as a 403 policy denial, not a feed or config issue).
`POST /ingest/run` against the deployed instance returned `error: null` for
all three outlets and ingested real articles into Neon — see §6.2 for how
to re-run this check yourself. If a URL goes stale later (outlets do
restructure feeds occasionally), you'll see it as a non-null `error` on
that outlet in the `/ingest/run` response; fix it directly in
`config/outlets.yaml`, nothing else needs to change.

You can also check feed health without touching the database:

```bash
python -m app.ingestion.verify_feeds
```

It fetches each configured feed and reports OK/FAIL/EMPTY plus the newest
headline for each — useful for a quick check from any machine with normal
internet access, without going through the deployed API.

The ingestion pipeline itself — fetch → parse → dedup → persist →
idempotent re-run — was also fully verified against two local mock RSS
feeds (one deliberately containing a duplicate "PTI wire copy" item) during
development, and separately confirmed idempotent against the real feeds
above: a second `/ingest/run` call correctly skipped already-ingested
articles rather than duplicating them.

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
up). The only Render free-tier limitation that matters here: the web
service spins down after 15 minutes idle and takes up to ~60s to wake on
the next request — fine for manual testing, not something to build a
real-time product on.

**Correction**: an earlier version of this doc claimed Render's Cron Jobs
were free-tier too. That was wrong and was never actually verified against
Render's pricing - Cron Jobs require a paid plan (billed per execution
minute, ~$1/month minimum per job). See §6.3 for how scheduled ingestion
is actually done here instead, at $0.

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
   - `OPENAI_API_KEY` / `GEMINI_API_KEY` — leave blank unless you're
     testing paid classification providers (§9.3).
   - `SECRET_KEY` — **required as of Phase 3, the app refuses to start
     without it** (signs the admin UI's session cookies). Generate one
     with `python -c "import secrets; print(secrets.token_hex(32))"` and
     paste the output in. Don't reuse a key you've shared anywhere else.
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

**Status**: done — deployed at `news-classification-api-qp8a.onrender.com`,
`/ingest/run` returned `error: null` for all three outlets, and a repeat
call correctly no-op'd on already-seen articles (idempotent re-ingestion
confirmed against real feeds, not just local mocks). One real bug was
caught and fixed along the way: the feed fetcher accepted a
`timeout_seconds` parameter that was never actually applied, so a feed
that hung without erroring could have stalled `/ingest/run` indefinitely —
see the "Fix: actually enforce the feed fetch timeout" commit.

### 6.3 Scheduled ingestion (GitHub Actions, not Render Cron Jobs)

None of `/ingest/run`, `/process/run`, or `/queue/assign` run on their own
— they're manual-trigger endpoints, by design, through Phases 1-3. Without
something calling them periodically, the app just sits still: no new
articles, no new classifications, no new queue items, no matter how much
time passes.

Render does offer Cron Jobs, but they are **not** part of the free tier
(billed per execution-minute, ~$1/month minimum per job) — using one here
would be this project's first paid dependency. Instead,
`.github/workflows/scheduled-pipeline.yml` runs the same three calls every
4 hours via a free GitHub Actions scheduled workflow:

1. `POST /ingest/run` once (covers all configured outlets).
2. `POST /process/run?limit=50`, looped until `remaining_unprocessed` hits
   0 — matches the same "call again if there's more" pattern documented on
   the endpoint itself, just automated.
3. `POST /queue/assign?limit=30`, looped until both `assigned` and
   `rescraped` hit 0 — same idea, covers both new assignment and the
   scrape-retry healing pass (see `app/review/assignment.py`).

Each step is capped at 20 loop iterations as a safety net against an
infinite loop if something's actually broken, and fails the workflow run
(visible in the repo's Actions tab) on any HTTP error response, rather
than silently doing nothing.

The target URL is a repository variable, `RENDER_APP_URL` (Settings →
Secrets and variables → Actions → Variables), defaulting to
`news-classification-api-qp8a.onrender.com` if unset — update the variable
rather than the workflow file if the deployed URL ever changes. You can
also trigger a run on demand from the Actions tab (`workflow_dispatch`)
instead of waiting for the schedule.

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

- End-user website (Phase 4)
- Full analytics *visualizations* (Phase 3's §12 built the underlying
  queries cleanly; charts on top of them are a later phase)
- Auto-escalation when the 48-hour review SLA is breached (Section 11,
  deferred) — just the visual "overdue" flag
- Multi-admin reconciliation / tie-breaking (Section 11, deferred) —
  `reviews[]` is modeled as one-to-many for this, but only one review is
  ever created per article today
- OpenAI/Gemini *embedding* providers (only classification has paid
  providers so far — see §11)
- Self-service password change for admins (a super admin resets a
  password via the edit form; there's no "change my own password" flow)

## 9. Phase 2: Clustering + Classification

Builds Section 7 pipeline stages 3-5 (embed, cluster, establishment
pre-filter, pro/anti/apolitical classification + jurisdiction/ruling-party)
and both Section 4.3 safety nets (entity-trigger override, cluster
re-evaluation). Still no admin UI, no website — this phase makes the
pipeline produce correct, queryable rows in the database; Phase 3 is what
puts a human and a UI in front of them.

### 9.1 Embeddings + clustering

- **Local embedding provider**: `app/llm/local_embedding.py`, via
  [fastembed](https://github.com/qdrant/fastembed) running
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-dim,
  ~50 languages including Hindi) through **onnxruntime, not PyTorch**.
  Originally `all-MiniLM-L6-v2` (English-only); swapped once local Hindi
  outlets were added to `config/outlets.yaml` and the English-only model
  was giving their content near-random classification. This is the one
  deliberate substitution from what was asked: `sentence-transformers`-the-
  library pulls in PyTorch, which alone needs several hundred MB of RAM
  even for a small model — tight to nonviable inside Render's free-tier
  512MB web service. fastembed runs the *exact same model weights* through
  a much lighter runtime (onnxruntime, no PyTorch at all) — same model,
  same output vectors, different execution engine. The multilingual
  model's memory footprint on this exact free tier is **not yet verified**
  (see that file's own docstring) — if it doesn't fit, fall back to
  `EMBEDDING_PROVIDER=openai` or `=gemini` rather than shrinking further.
  `LOCAL_EMBEDDING_MODEL` in `.env` still names the model in the usual
  Hugging Face format.
- **Storage**: `articles.embedding` (`pgvector`, fixed at 384 dimensions —
  see `app/constants.py`) plus `articles.embedding_model` recording which
  model produced it. Not indexed (no ivfflat/hnsw) — at POC scale, a full
  scan with pgvector's `<=>` cosine-distance operator is fast enough and
  needs no index tuning.
- **Clustering algorithm**: incremental nearest-neighbor, not HDBSCAN.
  Articles arrive continuously via ingestion, not as one static batch to
  cluster at once — "does this new article match an existing cluster?" is
  the actual shape of the problem, and re-running a batch algorithm like
  HDBSCAN from scratch on every ingestion run doesn't fit that. For each
  new article, `app/processing/clustering.py` finds the nearest other
  canonical article (`duplicate_of_id IS NULL`) published within
  `CLUSTERING_TIME_WINDOW_HOURS` (default 48h) and joins its cluster if
  cosine similarity clears `CLUSTERING_SIMILARITY_THRESHOLD` (default
  0.55), else starts a new cluster. **Both defaults are untuned
  starting points** — this build environment can't download the embedding
  model (see §10), so there was no way to run real articles through this
  and calibrate the threshold against actual clustering quality. Expect to
  adjust it after looking at real output.
- **Topic labeling**: `app/processing/topics.py` assigns each new cluster
  one of a fixed set of topic labels (Politics, Economy & Business, Sports,
  ...) via the same embedding-similarity zero-shot technique described
  below — compare the cluster's triggering article embedding to each
  topic's description embedding, take the closest. Edit `TOPIC_LABELS` to
  change the taxonomy; no other code changes needed.

### 9.2 Establishment pre-filter + entity-trigger net (Section 4.3)

Two independent layers, deliberately not merged into one:

1. **Pre-filter**: the classification provider's own political-vs-apolitical
   call (see §9.3) — this is the "is this article establishment-relevant at
   all?" question from Section 7 stage 4.
2. **Entity-trigger net** (`app/processing/entity_triggers.py`): a plain
   keyword/regex list — political titles (MLA, MP, Chief Minister, ...),
   `Ministry of ...` patterns, government tender/contract phrases, and
   ~25 national/state party names. When the pre-filter says "apolitical"
   but this net finds a hit anyway, the apolitical call is overridden and
   the article is routed through `classify_forcing_establishment_relevant()`
   instead (implemented on every provider — see `app/llm/base.py`), which
   must return pro/anti + jurisdiction, never apolitical. This is
   deliberately *not* an ML/NER model: Section 4.3 specifies this net as a
   safety net independent of the classifier's own judgment, so it should
   fail differently than the classifier does — a transparent, zero-cost,
   trivially-editable list does that better than a second model would.
   `Article.entity_trigger_override` records when this fired, so a future
   admin queue can prioritize exactly the cases Section 4.3 flags as
   needing a second look.

### 9.3 Pro/anti/apolitical classification — the honest resource writeup

You asked directly whether a local classifier is realistically deployable
on Render's free tier. Here's the straight answer:

**A separate local zero-shot/NLI model, stacked on top of the embedding
model, is not realistically viable inside Render's 512MB free container.**
That's two ML models competing for RAM that isn't there — even a "small"
NLI model would push total memory well past what's available alongside
FastAPI, SQLAlchemy, and the embedding model already resident.

Instead, `app/llm/local_classification.py` implements the local provider as
**embedding-similarity zero-shot classification**, reusing the exact
MiniLM model already loaded for clustering: compare the article's
embedding to a handful of reference-phrase embeddings ("this article
criticizes the government" vs. "this article praises the government",
etc.) and take the closer one, with a temperature-scaled softmax over the
similarities for `confidence_score`. This is a real, working technique —
not a fake placeholder — and it costs **zero additional RAM**, which is
what actually makes local classification Render-viable at all.

The tradeoff, stated plainly: this is fundamentally a topical/semantic-
similarity signal, not a reasoning one. It's reasonably suited to the
establishment-relevance split (political-vs-not is close to a topic
distinction) but meaningfully weaker at pro-vs-anti framing, which is a
subtler stance judgment than embeddings are naturally good at. Treat the
local provider as a free, always-available baseline for exercising the
pipeline correctly — not as a fair quality comparison against what OpenAI
or Gemini will produce. If you want real local-LLM-quality classification
without paying, that needs a model with actual reasoning capability run on
a machine with normal RAM (your own laptop, not this Render container) —
that's a real option, just not one this deployment target can host.

**OpenAI and Gemini providers** (`app/llm/openai_provider.py`,
`app/llm/gemini_provider.py`) are fully implemented — structured JSON
output via each SDK's native schema support (`chat.completions.parse` /
`GenerateContentConfig(response_schema=...)`), same prompt and output
shape for both so results are directly comparable. Neither is called
unless `LLM_PROVIDER=openai` or `gemini` **and** the matching API key is
set — with `LLM_PROVIDER=local` (the default), no code path can reach
either SDK, so there's no risk of an accidental charge. Every call once
enabled is billed by your account.

**Comparing providers**: `system_tags` stays strictly one row per article
(the planning doc's Section 6 specifies `system_tag` as singular, not an
array like `reviews[]`), so it can't hold multiple providers' opinions on
the same article side by side. For genuine comparison once you've funded
OpenAI/Gemini, use:

```bash
python -m app.cli compare-providers --providers local,openai,gemini --limit 10
```

This runs every named provider on the same sample of articles and prints
results side by side — it does **not** write to the database, so comparing
never affects what's actually classified.

Every classification produces `classification` + `jurisdiction` +
`confidence_score`; `ruling_party` is resolved separately and
deterministically (next section), never guessed by the classifier.

### 9.4 Jurisdiction → ruling party lookup (Section 4.2)

`app/processing/jurisdiction.py` splits this into two genuinely different
tasks:

- **Guessing which jurisdiction an article concerns** requires
  understanding the text - a real classification task. The local provider
  does this with a keyword match against Indian state names (`centre` if
  none found); OpenAI/Gemini determine it as part of their own structured
  output, which should be more accurate since it's contextual rather than
  keyword-based. One deliberate special case: "Delhi"/"New Delhi" alone is
  treated as a Centre reference (it's the national capital and appears
  constantly as a dateline), not a Delhi-state signal — only phrases like
  "Delhi government" or "Delhi Chief Minister" count as a state:Delhi
  match.
- **Resolving the ruling party for a known jurisdiction + date** is a pure
  lookup against `jurisdiction_ruling_parties`, exactly as Section 4.2
  specifies ("resolved via a date-ranged lookup table, not hardcoded").

**Seed data.** `app/data/jurisdiction_seed.py` seeds Centre + the ~20 most
populous states:

```bash
python -m app.cli seed-jurisdictions       # or POST /admin-data/seed-jurisdictions
```

My knowledge of Indian politics has a training cutoff of January 2026, and
this was originally built in a session dated August 2026 — a seven-month
gap that made five rows (West Bengal, Kerala, Tamil Nadu, Assam, Bihar)
outright guesses about elections I couldn't have known the outcome of.
**All five have since been corrected against user-verified, current
results**: West Bengal (BJP), Tamil Nadu (TVK — a new party, also added to
the entity-trigger net's party list since it postdates this model's
training data too), and Kerala (Congress-led UDF) all changed hands in the
May 4, 2026 elections; Assam (BJP) and Bihar (JD(U)-led NDA, confirmed
against the Nov 2025 result) did not. The old rows for the three states
that changed were closed out with a matching `effective_to` rather than
edited in place, per Section 4.2's date-ranged design — an article from
2023 still correctly resolves to the government that was actually in power
then. `seed_jurisdictions()` is idempotent and handles both inserting new
rows and closing out existing ones automatically; re-running it is safe.

Every other row reflects my best knowledge as of the cutoff and is more
likely still current (most state governments run fixed 5-year terms with
nothing due), but "more likely current" is not "verified" — this table is
explicitly designed to be hand-maintained (per the planning doc's own
warning about silent mislabeling as governments change), and correcting it
once doesn't change that upkeep is on you going forward. Add a new row
with its own `effective_from` (and close out the old one) rather than
editing a row in place when something changes next.

### 9.5 Cluster re-evaluation (Section 4.3)

Implemented in `app/processing/pipeline.py`: when a newly-processed article
**joins an existing cluster** (not one it just created) and its
classification is not apolitical, the whole cluster's `needs_review` is set
`True` — not just the new article — exactly as Section 4.3 specifies,
since clustering and tagging aren't fully independent stages. Verified with
a scripted test: a second, differently-framed article joining an existing
cluster correctly flags the cluster, while an article starting a brand new
cluster does not.

### 9.6 Running it

```bash
python -m app.cli seed-jurisdictions    # once, before first use
python -m app.cli verify-local-models   # confirms the embedding model downloads/loads (see §10)
python -m app.cli process               # cluster + classify all unprocessed articles
python -m app.cli show-clusters         # inspect results
```

Or via the API — this matters on Render's free tier specifically, which has
no shell access to run CLI commands: `POST /admin-data/seed-jurisdictions`,
`POST /process/run` (mirrors `/ingest/run`),
`GET /clusters?needs_review_only=true`, and `/articles` now includes
`cluster_id`, `entity_trigger_override`, and the nested `system_tag`.

## 10. What's verified vs. what needs checking on real infrastructure

Same situation as Phase 1's RSS feeds (§5), for the same reason: this build
environment's network is restricted to a small dev-infra allowlist and
cannot reach Hugging Face Hub (confirmed via direct test — a 403 from the
egress proxy) or the OpenAI/Gemini APIs with real credentials.

**Fully verified locally** (against a real Postgres 16 + pgvector instance,
using synthetic embeddings and mocked providers so the model download
isn't required to test the logic around it):

- The clustering algorithm's decision logic — same-story articles join a
  cluster, unrelated ones don't, articles outside the time window don't,
  via real pgvector cosine-distance queries
- The full pipeline's orchestration — embed → cluster → classify → entity-
  trigger override → jurisdiction/ruling-party resolution → SystemTag
  persistence → apolitical publish-skip → cluster re-evaluation — as one
  scripted scenario covering all of the above together
- Idempotency: a second `process` run touches zero already-processed
  articles
- Graceful failure: when a provider call fails (tested for real, by
  actually hitting the network-blocked Hugging Face download inside a live
  API request), the error is caught per-article and reported in the
  response rather than crashing the endpoint
- The entity-trigger net's keyword matching, including two real regex bugs
  caught and fixed during testing (see the "Fix:" prefixed commits) —
  short acronyms like "mp" false-matching inside ordinary words, and `\b`
  silently failing to match terms ending in punctuation like "CPI(M)"
- OpenAI/Gemini provider construction and structured-output schema
  building (both SDKs accept the shared Pydantic schema without error)

**Not verified — needs a real deploy or your own machine, same as §5**:

- The local embedding model actually downloading and producing real
  vectors (`python -m app.cli verify-local-models` is the check to run)
- Real clustering/classification *quality* on actual articles — the
  algorithm's logic is proven, but `CLUSTERING_SIMILARITY_THRESHOLD` and
  the local classifier's confidence calibration are untuned defaults, not
  validated against real embeddings
- Whether the local embedding model's RAM footprint actually fits Render's
  512MB in practice, alongside the rest of the app — the ~66MB onnxruntime
  install size supports the case that it should, but "should fit" isn't
  "confirmed to fit"
- Live OpenAI/Gemini API calls (no real keys, and this sandbox can't reach
  `api.openai.com` regardless — `generativelanguage.googleapis.com`
  happened to respond, likely because `*.googleapis.com` is allowlisted for
  unrelated cloud-tooling reasons, but no real key was available to test an
  authenticated call)

## 12. Phase 3: Admin & Super Admin Review UI

Builds Sections 3, 5, and 10: a login-gated review queue (Section 5), the
super-admin oversight views (Section 3), and the account management that
makes those roles real. Still server-rendered in this same FastAPI app —
no separate frontend framework, no build step — because this is an
internal tool for 2-3 known people, not the public site (Phase 4).

### 12.1 Stack choices and what they trade away

- **Jinja2 templates, not a JS framework.** `app/templates/*.html`,
  rendered via `fastapi.templating.Jinja2Templates`. No `npm`, no build
  pipeline, no separate deploy target — the whole UI ships as part of the
  same Render service Phases 1-2 already deploy to.
- **Session cookies, not JWTs or OAuth.** `Admin.username`/`password_hash`
  (bcrypt) plus Starlette's `SessionMiddleware` (a signed cookie holding
  `{"admin_id": ...}`) is the entire auth system. No server-side session
  store needed at this scale. `SECRET_KEY` (`.env`/Render env var) signs
  the cookie and has **no default on purpose** — a hardcoded or
  well-known signing key would let anyone forge a logged-in session, so
  the app refuses to start without one being set explicitly. Generate one
  with `python -c "import secrets; print(secrets.token_hex(32))"`.
- **What a public-facing app would need that this doesn't have**: CSRF
  tokens (mitigated instead by `SameSite=Lax` cookies, a reasonable
  POC-level protection, not a substitute for real tokens on something
  with untrusted users), rate-limiting on `/admin/login`, and self-service
  password reset via email. All reasonable to skip for 2-3 people you
  personally provisioned accounts for; revisit before this is anything
  more than that.

### 12.2 Queueing — Section 7's stage 6, which Phase 2 stopped short of

Phase 2 ended at classification (stage 5). Assigning a classified article
to a specific admin's queue is its own step, matching how ingestion and
processing each got their own trigger:

```bash
python -m app.cli assign-queue      # or POST /queue/assign
```

`app/review/assignment.py` assigns each pending (classified, not-yet-
assigned) article to whichever **active** admin currently has the fewest
unreviewed articles — load-balanced by recomputing queue depth from the
DB each call, rather than a stateless round-robin counter that could
drift out of sync across repeated small batches.

**Phase 4 update, departing from Section 4.3's original "apolitical skips
straight to publish":** live use surfaced apolitical mis-classifications
(a genuinely pro/anti article the classifier missed) sitting unreviewed
and already public, since nothing ever looked at them again once
auto-published. `app/processing/pipeline.py` no longer sets
`published_tag` for apolitical articles at all - they now enter the same
queue/assignment/review flow as pro/anti (`app/review/assignment.py`'s
`_pending_articles()` no longer excludes them), and `published_tag` for
*every* tag, apolitical included, is set only once an admin's `Review`
confirms or overrides it. The entity-trigger net and cluster
re-evaluation (§9.2, §9.5) are unchanged - they're now a pre-filter that
reduces how often a real political article reaches the queue mislabeled,
rather than the last line of defense before publish.

An admin's own queue (`/admin/queue`) is grouped into three categories -
Pro-Establishment, Anti-Establishment, Apolitical, by the article's
system tag - rendered as tabs rather than one flat oldest-first list.
Requested directly: a single long list of everything read as more
daunting than three shorter, categorized ones. The first version of this
stacked all three lists on the page instead, one below the other -
that still left an admin scrolling through everything, just split across
three lists instead of one, missing the actual point of categorizing
them. Tabs show one category at a time (defaulting to the first
non-empty one, so an admin never lands on a tab with nothing to review);
all three are still rendered server-side and just hidden/shown client-
side, so switching tabs is instant with no extra request. Order within
each tab is now newest `published_at`
first - a further departure from Section 5's original oldest-first
wording, requested directly: publishing the most recent articles first
keeps their context current and matches what an end user sees first on
the public site (also newest-first). This is purely display/review
order, not assignment order - `app/review/assignment.py`'s
`_pending_articles()` still assigns oldest-pending-first, so a backlog of
older unclassified articles isn't starved by a steady stream of newer
ones arriving first in line for an admin.

Each row also shows the same blinded excerpt (`app/public/formatting.
excerpt`, on the blinded body - see §12.3's blinding rules) an admin
would otherwise only see after opening the full review page, plus a
checkbox and a per-section "Publish selected" button
(`POST /queue/bulk-confirm`, in `app/routers/admin_ui.py`). Requested
directly: many articles are obvious from the headline and excerpt alone
(a cricket score, a weather report), and clicking into each one just to
confirm what's already correct added friction without adding a review.
Bulk-publish can only *agree* with the system tag already shown for that
row - there's no per-article tag picker in the bulk form - so an actual
override still goes through the single-article review page, same as
before. Silently skips any id that isn't this admin's to review (wrong
owner, already reviewed, a stale page after a double-submit) instead of
failing the whole batch.

The table also has **Jurisdiction** and **Ruling party** columns (formatted
the same way `review.html` already shows them - `format_jurisdiction`, and
`ruling_party or "unresolved"`). Requested directly: the same headline can
be pro-establishment for one party/jurisdiction and anti-establishment for
another, so an admin judging an "obvious" case straight from the queue
list - the entire point of the excerpt above - needs that context in the
table itself, not just after opening the full review page. Apolitical rows
show "-"/"unresolved" here too, same as their review page always has,
since jurisdiction/ruling_party genuinely don't apply to them (§4.2).

Two new `Article` fields support this: `assigned_admin_id` and
`queued_at`. `queued_at` — not `published_at` — is what the 48-hour SLA
(§12.3) is measured against: an article can sit unclassified for a while
after publication (ingestion/processing lag), and the SLA is about review
turnaround, not the news' own age. Queue *display* order is newest
`published_at` first (see above) — a Phase 4 departure from Section 5's
original oldest-first wording — but that's independent of the SLA clock,
which is unaffected by this change either way.

### 12.3 Blinding (Section 5)

`app/review/blinding.py` redacts two things to the same
`[self-reference removed]` placeholder:

1. **The outlet's own name**, wherever it appears in the headline/body —
   e.g. "The Hindu has learnt that..." would otherwise defeat the
   outlet-hidden rule even though `outlet_id` itself is never rendered,
   since the name is sitting right there in the text.
2. **Generic self-referential phrases** ("this newspaper", "this
   publication", "this website", ...) that identify the piece as
   self-reported without using the outlet's name directly.

Left untouched, per spec: bylines/reporter names, and PTI/ANI wire-copy
attribution (recognizing unedited wire copy — or its absence — is part of
what the review is meant to surface, not something to hide from it).

One judgment call worth flagging: outlet names are matched exactly as
configured (`config/outlets.yaml`) — "The Hindu", not a stripped "Hindu".
Stripping "The " would make bare "Hindu" a redaction target, which
collides with an unrelated, extremely common word (the religion) and
would over-redact real content. Verified directly: "Hindu devotees
gathered for the festival" stays untouched, while "The Hindu has learnt"
and "as this newspaper reported" both correctly redact. If you add an
outlet whose bare name is similarly ambiguous, don't "fix" this by adding
automatic prefix-stripping — it's a correctness trap, not a coverage gap.

The 48-hour SLA (`REVIEW_SLA_HOURS`, default 48) shows as a simple
overdue/hours-remaining badge in the queue and on the review page — no
auto-escalation on breach, exactly as Section 11 says to defer.

### 12.4 Full-text scraping for admin review

Raised directly during review, and worth taking as seriously as it was
raised: RSS feeds are notifications that content exists, not a
distribution channel — most outlets deliberately put only a headline and
a short teaser (sometimes nothing) in the feed, precisely so you have to
visit their site to read the rest. An admin asked to judge pro/anti
framing off a one-line teaser can't do that job, and this was surfacing
as articles whose review page appeared to be missing content entirely.

This has no clean free-and-zero-risk answer, so rather than silently pick
one, the tradeoffs were laid out directly: scrape (free, but most
outlets' ToS prohibit automated scraping, and it's fragile — the answer
we went with), pay for a licensed content API (the legitimate way to
actually redistribute full text, real cost), or redesign the end-user
product to never need full text at all (headline + snippet + link to the
source, the Google News pattern — free, no legal exposure, but a real
product-direction change deferred to whenever Phase 4 is actually
designed).

**What's built**, scoped deliberately narrow given the ToS risk:
`app/review/scraping.py` fetches an article's own page and extracts the
main text via [trafilatura](https://github.com/adbar/trafilatura) (a
purpose-built content-extraction library — not a hand-rolled "grab every
`<p>` tag" heuristic, which pulls in nav/ads/comments noise). Verified
directly: nav links, an ad banner, and a footer/comments block were all
correctly excluded from a realistic test page, while the actual article
paragraphs were kept intact.

- **Only for articles that will actually be reviewed.** `app/review/
  assignment.py` triggers a scrape exactly when an article is assigned to
  an admin's queue - since §12.2's Phase 4 update, that now includes
  apolitical articles too (they're reviewed the same as pro/anti), so
  this is really "never for a duplicate or an apolitical article that's
  already been reassigned to a still-pending state," not an apolitical-
  specific exemption anymore. Nothing is scraped in bulk "just in case."
- **Respects each site's robots.txt** and identifies itself honestly via
  User-Agent — no browser-spoofing to bypass a block. A site that
  disallows or blocks this is treated as "can't get this one," not
  something to route around. Verified: a path disallowed via robots.txt
  is correctly refused without even being fetched.
- **Never republished or end-user-facing.** The result
  (`Article.scraped_body_text`) exists only to give a human reviewer
  enough context to make an accurate call, privately. There is no
  end-user view in this POC yet, and this data has no path to one without
  a deliberate future decision to build that — see the option laid out
  above (snippet + link-out) for why "just show admins' scraped text to
  end users too" is not the assumed default for whenever that's built.
- **Graceful fallback, not a silent gap.** If a scrape fails (blocked,
  timed out, extraction found nothing), `scrape_error` records why, and
  the review/compare pages fall back to the RSS teaser with the failure
  reason shown — verified for the "teaser exists, scrape failed" case.
  The scraped text (when present) goes through the same blinding as the
  RSS teaser — verified a self-reference inside scraped text ("this
  newspaper") is correctly redacted.
- **Rejects extraction that looks like an author bio, not an article.**
  Some outlets embed a prominent "About the author" credibility block
  (name, years of experience, beat coverage — an SEO/E-E-A-T pattern)
  that can outrank the real article under `trafilatura`'s content-block
  selection, producing confident-looking but entirely wrong text. A
  heuristic (`looks_like_author_bio` in `app/review/scraping.py`) rejects
  extracted text shaped like a bio opening ("`<Name> is a/an
  <editor/correspondent/...>`" plus career-history phrasing) and records
  an honest `scrape_error` instead. `POST /queue/heal-bio-scrapes` /
  `python -m app.cli heal-bio-scrapes` is a one-time cleanup for articles
  scraped before this check existed.
- **"Neither exists" never reaches a regular admin's queue at all.** An
  article where the scrape failed *and* the RSS teaser is empty — genuinely
  nothing to show — is diverted to the super-admin-only Manual Review
  bucket (`/admin/manual-review`, `Article.needs_manual_link_review`)
  instead of sitting in a regular admin's blinded queue with nothing to
  read. That page shows the raw source URL (blinding is a regular-admin
  protection, not applicable when a human has to visit the link directly)
  so a super admin can read the real article externally and classify it
  from there. `POST /queue/divert-unreviewable` /
  `python -m app.cli divert-unreviewable` is a one-time cleanup for
  articles already stuck in a regular admin's queue from before this
  existed.
- **Bounded per call, same lesson as Phase 2's `/process/run`.** Each
  scrape is a real network fetch (up to a 15s timeout) that now runs
  inside `/queue/assign`, so a large batch would take a genuinely long
  time in one HTTP call. The default batch size was lowered (10, capped
  at 200) specifically because of this added per-article cost — call it
  repeatedly for a large backlog rather than raising the limit.

**Said plainly, once more, because it matters**: this is still not zero
legal risk. It's judged to be a substantially smaller footprint than a
general-purpose scraper — used only to inform a private human decision,
never stored for or shown to the public — but if this project ever moves
toward Phase 4's public site, "we already scrape for admin review" is not
a green light to reuse that content for the public-facing product without
a real, separate decision (and likely legal input) at that point.

### 12.5 Review decision -> Section 6's `Review` + `published_tag`

Confirming or overriding is one form: two radio options (pro/anti-
establishment), pre-selected to the system tag. Submitting the
pre-selected option records `decision=agreed_with_system`; picking the
other records `decision=overrode` — derived by comparing the choice to
`system_tag.classification`, not a separate manual field, so there's no
way for the two to disagree with each other. This creates the `Review`
row (`admin_id`, `final_tag`, `decision`, `timestamp`) and sets
`Article.published_tag` directly, exactly per Section 6.

### 12.6 Super admin: account CRUD, deactivate-don't-delete

`Admin` gained `username`, `password_hash`, `is_active`. Deactivating
(never hard-deleting, so `Review.admin_id` history stays intact) also
reassigns that admin's unreviewed queue to remaining active admins
(`reassign_admin_queue`) rather than leaving it orphaned.

Two safety guards, both verified: an admin can't deactivate their own
account, and the last active super admin can't be removed — **not just
via deactivation**. Testing surfaced a real gap here worth calling out
rather than glossing over: the initial guard only checked
`is_active`, which missed a second way to lose the last super admin —
demoting their *role* to `admin` while leaving them active. Both paths
are now blocked by the same check.

### 12.7 Bootstrapping the first super admin

Nothing can log in to create the first account, and an always-open
"create super admin" endpoint would be a real vulnerability if left
reachable. `POST /admin-data/bootstrap-super-admin` splits the
difference: it only works while the `admins` table is completely empty,
and returns 403 forever after the first account exists — solving
Render's no-shell problem (same reason `/admin-data/seed-jurisdictions`
exists) without leaving a permanent open door. Verified: works once,
403s on every attempt after. Locally, `python -m app.cli create-admin`
(password entered via `getpass`, never a CLI argument or shell history)
works for the first account and every one after.

### 12.8 Super admin: oversight + review-listing groundwork

- `GET /admin/articles/{id}/compare` — system tag vs. admin decision side
  by side, labeled, per Section 3.
- `GET /admin/reviews` — filterable by admin/decision/date range. You
  asked for this to be groundwork for a real analytics dashboard later,
  not charts now: `app/review/queries.py`'s `query_reviews()` and
  `decision_counts_by_admin()` are plain, reusable functions (eager-
  loading article+admin to avoid N+1 queries per row), not logic baked
  into the route handler — the dashboard phase can call the same
  functions instead of re-deriving this query layer. `Review.admin_id`,
  `.decision`, and `.timestamp` are now indexed for exactly this filtering
  pattern.

### 12.9 The Phase 1/2 debug endpoints are all still here

Per your instruction, nothing from `/health`, `/articles`,
`/ingest/run`, `/process/run`, `/clusters`, `/clusters/stats`, or
`/admin-data/seed-jurisdictions` was touched or gated behind login — they
remain open JSON endpoints, useful for internal testing independent of
the authenticated HTML admin UI, and for feeding the super-admin
dashboards later. `/queue/assign` (new this phase) follows the same
pattern.

### 12.10 Verified end-to-end

Full integration tests via FastAPI's `TestClient` (real HTTP requests,
real session cookies, against actual Postgres — no mocking of the routes
themselves): bootstrap → login → create admin → assign queue
(load-balanced) → queue page → blinding on the review page (outlet name
and self-reference both redacted, confirmed "Hindu devotees" stays
untouched) → submit both an agreement and an override → `published_tag` +
`Review` row correct in both cases → SLA overdue badge (backdating
`queued_at`, since the SLA clock starts at queueing, not publication) →
super-admin compare view → reviews listing + filters → 403 for a regular
admin on super-admin pages → wrong-password and deactivated-account login
rejected identically (no account-enumeration signal) → unauthenticated
access redirected to login → self-deactivation blocked → last-super-admin
guard verified for **both** deactivation and role-demotion, isolated from
the self-deactivation case with a second super-admin account →
deactivation's queue reassignment. Also verified against a local mock
article page: scraping correctly extracts real article text while
dropping nav/ad/footer noise, respects a robots.txt disallow without
fetching the page at all, and falls back to the RSS teaser (with the
failure reason shown) for both "teaser exists, scrape failed" and
"neither exists" cases - scraped text goes through the same blinding as
the RSS teaser either way. Not yet exercised: an actual browser session
(you logging in on Render) or scraping against the real configured
outlets specifically - the same "needs a real deploy" caveat as every
prior phase, and worth an early check given how outlet-specific scraping
tends to be.

### 12.11 Running it

```bash
# One-time setup
# .env / Render env vars need SECRET_KEY set - see §12.1
python -m app.cli create-admin --username you --name "Your Name" --role super_admin
# or, on Render (no shell): POST /admin-data/bootstrap-super-admin
#   {"username": "you", "name": "Your Name", "password": "..."}

# Regular use
python -m app.cli assign-queue     # or POST /queue/assign - after each `process` run
```

Then visit `/admin/login` in a browser (not `/docs` — this is real HTML,
not a JSON API to test through Swagger). Log in, review what's in your
queue, and — as super admin — visit `/admin/admins` to create accounts for
the other 1-2 people, and `/admin/reviews` to see everything reviewed so
far.

## 13. Phase 4: Public site

Builds Sections 8-9: the end-user-facing website. Server-rendered Jinja2 in
this same FastAPI app, same architecture as Phase 3's admin UI - no
separate frontend build - styled with Tailwind loaded via its CDN script
rather than a local build pipeline.

`app/public/queries.py` is a read model kept deliberately separate from
Phase 3's admin queries (`app/review/queries.py`), because the two have a
fundamentally different visibility rule. The one rule this module enforces:
**nothing is visible until `Article.published_tag` is set** - already the
codebase's own definition of "safe to show" (set directly for apolitical
articles, set by admin review for pro/anti). `SystemTag`, the raw
unreviewed model output, is never read here. Cards use `body_text` (the
RSS teaser) only - `scraped_body_text` is admin-review-only per
`app/review/scraping.py`'s own docstring, enforced here in the query layer
rather than left to convention.

**Layout**: three columns - Pro-Establishment, Anti-Establishment,
Apolitical - each a list of story clusters, newest first. Column identity
is typographic, not color-coded: no red/green, no saffron/green/blue - the
same reasoning Section 4.4 applies to calling a primary source "fact"
applies to how a tag is *presented*, not just what it's called. A cluster
with a `primary_source_url` shows a distinct badge; a cluster with none
shows an explicit "no primary source available" state on its `/compare`
page (Section 4.4).

**One cluster can have several published articles under the same tag**
(multiple outlets covering the same story and agreeing), and grouping is
by *(cluster, published_tag)*, not cluster alone - two outlets reviewing
the same story independently and blind can land on genuinely different
verdicts, and that's shown, not collapsed: a diverging story appears under
both Pro-Establishment and Anti-Establishment at once, each with a cross-
tag breakdown pill (`format_outlet_breakdown`, e.g. "3 pro · 2 anti").
Clicking a diverging card's pill goes to `/compare/{cluster_id}`, showing
every published article in the story grouped by tag side by side.

**Which article represents a cluster+tag on the home page, when more than
one outlet agrees**: the *earliest*-published one, not the most recent -
requested directly, since picking whichever article a query happened to
return first read as arbitrary to a reader with no way to know why that
outlet's headline was the one shown. The other agreeing outlets' headlines
aren't dropped: the same-sentiment card's breakdown pill (e.g. "3 pro") is
hoverable - a small popover lists the other outlets' headlines under
"Also reported by" - and clicking it goes to the same `/compare/{cluster_id}`
page the diverging case uses, which renders correctly either way (one
populated section for agreement, two or more for divergence; its heading
text adjusts - "reached the same verdict" vs. "framed this story"
differently - based on how many tag sections actually have anything in
them). A diverging card's own breakdown pill (the compare-link one) got
the same hover treatment, showing what the *other* tag(s) said, each
headline labeled with its tag ("Anti-Establishment: ...") since those
headlines don't all share the card's own tag the way the agreement case's
do.

**A real bug caught right after shipping the above, worth recording
plainly rather than glossing over**: a cluster's *sort position* in its
column used to be its own representative article's `published_at`. Once
the representative became the earliest article, that meant a story's
position was set by when it was *first* reported, not by how recently it
was actually covered - a story first reported long ago that just got a
brand-new follow-up from another outlet would sort as if it were stale,
and could be pushed out of `limit_per_column` entirely despite being
genuinely live, ongoing coverage. `ClusterCard.published_at` (the sort
key) is now the cluster+tag's *most recent* article's timestamp,
independent of `published_at_display` (the earliest article's own
timestamp, honestly describing the headline actually shown) - the two are
allowed to differ, deliberately.

**Date browsing**: `GET /?date=YYYY-MM-DD`, IST calendar-day boundaries
(the outlets and readership are India-focused; UTC boundaries would clip
or duplicate the last/first ~5.5 hours of every real IST day). Filters on
the article's own original `published_at`, not when review completed - a
deliberate tradeoff, since the 48-hour review SLA means "Today" can look
sparse for part of the day, accepted because it matches what a reader
actually means by "today's news." Rendered as a bounded 14-day `<select>`
(`app/public/formatting.recent_date_options`), not a native calendar
input - the latter rendered as a full-screen sheet on iOS Safari and let a
future date remain clickable in the picker UI even though the server
already rejected it; a `<select>` fixes both, since a future date is now
structurally never one of the options at all.

`/about` (`public_about.html`) ships as a scaffold only - nav and layout
done, one clearly marked placeholder left for methodology copy still to
be written directly, not drafted here.

## 14. Phase 5: Entity Tagging & Subject Sentiment (Section 13.1-13.2)

The data-layer groundwork for the future B2B client portal (Section
13.6) - **not the portal itself**, which stays a later, separate phase
with no client-facing tables or UI yet. What's here: two new tables, a
new pipeline stage, a new provider interface, and both folded into the
existing admin review screen rather than a second queue.

### 14.1 Entity + ArticleEntity data model

`Entity` (id, name, type `person`/`party`, `aliases[]`, `entity_metadata`
JSONB) and `ArticleEntity` (a real many-to-many join, composite
`(article_id, entity_id)` primary key - an article has at most one
prominence/sentiment record per entity, repeated mentions accumulate into
that one row rather than creating more). Promoted out of
`app/processing/entity_triggers.py`, which only ever detected *that* some
political entity was present (a binary trigger for the apolitical safety
net, Section 4.3) - never *which* one. That trigger net is completely
unchanged and still does its own job; this is a separate, queryable
record of specific entities.

### 14.2 Prominence heuristic (Section 13.1's "worth deciding a simple
heuristic")

Three signals, each cheap and explainable, combine into a 0-8 score:

- **+3** if the entity is named in the headline - the strongest single
  signal, since headlines are written to name the article's actual
  subject.
- **+1 per mention, capped at 3** - repeated mentions matter, but a 10th
  mention isn't 10x more meaningful than a 3rd.
- **+2** if the first mention falls in the first third of the combined
  (headline + body) text, **+1** in the middle third, **+0** in the last
  third - an entity introduced early is more likely the actual subject
  than one that shows up as a late aside.

Score >= 5 -> `primary`, >= 2 -> `secondary`, else `mentioned`. Like
`CLUSTERING_SIMILARITY_THRESHOLD` and the softmax temperature in
`app/llm/similarity.py`, these thresholds are a reasonable starting point,
not a validated one - there's no labeled data yet to tune them against.
Matching itself is the same word-boundary regex approach as
`entity_triggers.py` (`app/processing/entities.py`), not an NER model -
same tradeoff, stated plainly: false negatives (a form not in an entity's
aliases) and false positives from an ambiguous bare name (see §14.4).

### 14.3 Subject sentiment - a second, independent axis

`ArticleEntity.system_subject_sentiment` / `published_subject_sentiment`
(`favorable`/`unfavorable`/`neutral`) mirror `SystemTag.classification` /
`Article.published_tag`'s system-generated-then-admin-reviewed shape, but
deliberately never use "pro"/"anti" wording anywhere: this measures
sentiment toward **one specific entity**, independent of the article's
overall establishment framing. An anti-establishment article can be
favorable toward an opposition figure it quotes approvingly - conflating
the two axes' naming would misrepresent what each one measures (planning
doc Section 13.2). There is no `reviews[]`-style audit-trail table for
this axis - `subject_sentiment_decision`/`_reviewed_by_id`/`_reviewed_at`
are flat columns on `ArticleEntity` itself, since the review is folded
into the same single admin action that reviews the establishment tag
(§14.5) - a full multi-row history per entity wasn't asked for and would
be speculative ahead of the still-single-admin-per-article model.

Classification reuses the same provider-swappable pattern as
`ClassificationProvider` (`app/llm/base.py`'s new `EntitySentimentProvider`
+ `EmbeddingSimilarityEntitySentimentClassifier`/`OpenAIEntitySentimentProvider`/
`GeminiEntitySentimentProvider`), scored per-entity rather than per-article.
Provider selection reuses the existing `LLM_PROVIDER` setting rather than
a new knob - flipping it switches both axes together; there's no
supported way to run one axis local and the other paid today, a
reasonable POC-scale simplification, not an oversight.

**Cost, flagged plainly**: this runs one embedding/API call *per entity
found in the article*, not once per article. A plain-text article with no
political entities costs nothing extra; one mentioning several adds up
fast - free-but-not-instant for the local provider (CPU time, not RAM, is
the constraint), genuinely billed per entity for OpenAI/Gemini.

### 14.4 Seed data (`app/data/entity_seed.py`)

Reuses and extends `entity_triggers.py`'s ~25-item party trigger list -
correctly **splitting** two distinctions that list silently conflated
(CPI vs. CPI(M), separate parties since a 1964 split), and **adding** six
parties that were real gaps in it entirely (JD(S), Shiromani Akali Dal,
Biju Janata Dal, AIMIM, J&K National Conference, PDP). TVK (added to the
trigger net after the May 2026 Tamil Nadu election) is carried over.
**Still a flagged gap**: northeastern and other smaller regional parties
remain essentially unrepresented.

Person entities didn't exist before this phase at all (the trigger net
only ever matched generic titles like "chief minister", never named
individuals) - seeded with ~30 national figures and state chief
ministers, each carrying a `confidence` note in `entity_metadata`, same
honesty convention as `jurisdiction_seed.py`. **Three states' sitting
chief ministers are deliberately not seeded as named individuals**: West
Bengal, Tamil Nadu, and Kerala all changed ruling parties in the May 2026
elections (postdating my training cutoff) - the *party* is seeded with
confidence, the specific person that party installed as CM is not, since
guessing would be exactly the kind of fabrication the platform's own
design principles (Section 2) warn against. The former CMs (Banerjee,
Stalin, Vijayan) are still seeded as real, current, relevant figures -
just not asserted to hold that specific office today.

**A deliberate precision/recall tradeoff, flagged rather than silently
accepted**: bare "Modi" is included as an alias despite colliding in
principle with Nirav Modi/Lalit Modi, because in Indian political news it
overwhelmingly means the PM and excluding it would cost real recall on
the single most-tracked figure. Bare "SP" for Samajwadi Party is
deliberately *excluded* (collides with "Superintendent of Police") -
judgment calls, not validated ones; revisit if wrong-entity tags turn up
in practice.

### 14.5 Folded into the existing review screen, not a second queue

Per direct instruction. `review.html` (and `manual_review_detail.html`,
for consistency) render an "Entities mentioned" card inside the *same*
`<form>` as the establishment-tag radios - one submit
(`app/routers/admin_ui.py`'s `submit_review`) records both. Each entity
gets its own `entity_sentiment_<id>` radio group, pre-selected to the
system sentiment; submitting without changing it records
`agreed_with_system`, same semantics as the establishment tag.
`/admin/queue/bulk-confirm` (the checkbox "Publish selected" flow) does
the same for entity sentiment as it already does for the establishment
tag: an article confirmed without ever opening the full form agrees with
everything system-generated, entities included.

**Flagged directly, as asked, rather than silently absorbed**: for an
article mentioning many entities (a cabinet reshuffle naming a dozen-plus
ministers is the concrete case), this card gets long - a real tension
with this platform's own established anti-scrolling design bar (the
queue tabs rework earlier in this document exists for exactly that
reason). Mitigated partially by sorting the most-central entities first
(`_sorted_entity_mentions`) and by noting inline when a review has many
entities that the system's suggestion is already pre-selected for each,
but this is not a fix - a genuinely long form is still a genuinely long
form. Worth deciding, once real volume is visible: a prominence
threshold that only surfaces `primary`/`secondary` entities for review
(silently auto-confirming `mentioned`-level incidental ones), pagination,
or something else - not built now since it wasn't asked for and doing it
before seeing real multi-entity articles would be guessing.

### 14.6 Backfill - re-running extraction against history

Section 13.6's groundwork requirement: a future "a new entity was added,
sweep the archive for it" backfill must be straightforward, not only
wired into live ingestion. `app/processing/entities.py`'s
`extract_entities_for_article` is the single entry point both the live
pipeline (`app/processing/pipeline.py`, one article as it's classified)
and `backfill_entities` (many already-ingested articles) call - one code
path, two callers, so they can't drift apart.

`backfill_entities(rescan_all=False)` (the default) targets articles
never scanned at all (`Article.entities_extracted_at IS NULL`) - covers
every article ingested before this feature existed, in one pass.
`rescan_all=True` re-scans every classified article regardless of prior
scan state, for "a new entity was just seeded, check the whole archive."
Matching always re-runs (cheap, pure regex); a sentiment classification
(a real model/API call) is only spent on a genuinely new `(article,
entity)` pair - re-scoring one already scored would silently re-spend
money on a paid provider for no new information. Reachable via
`python -m app.cli backfill-entities [--rescan-all]` and
`POST /entities/backfill` (capped per call like `/process/run`, same
"call again while `remaining` > 0" pattern).

### 14.7 Verifying this phase

```bash
python -m app.cli seed-entities        # or POST /admin-data/seed-entities
python -m app.cli process              # now also extracts entities + sentiment
python -m app.cli show-entities        # list seeded entities + mention counts
python -m app.cli backfill-entities    # or POST /entities/backfill
```

`GET /entities` and `GET /entities/{id}/mentions` are unauthenticated
debug endpoints, same category as `/articles` and `/clusters` - not the
admin API, just a way to confirm extraction output over HTTP, including
on Render's free tier where there's no shell for the CLI equivalents.
`GET /entities/{id}/mentions` is also the concrete, already-working
answer to Section 13.1's core B2B query ("show me every article about
Subject X, over time") - well ahead of any client-facing surface for it.

Verified locally (mocked `EmbeddingProvider`/`ClassificationProvider`/
`EntitySentimentProvider`, same "no real network access" reasoning as
every other phase - see §10): the prominence heuristic's score thresholds
directly; a full `process_articles()` run extracting entities and scoring
sentiment correctly per entity in one article; the review screen showing
both entities with pre-selected sentiment and recording an override on
one entity alongside an agreement on another *in the same submit*;
bulk-confirm agreeing with system sentiment for an article never opened;
and backfill both finding a newly-seeded entity in an already-ingested
article and staying idempotent (no duplicate rows) on a second run.

## 15. Phase 6: Social Listening (Section 13.1, 13.6)

X (formerly Twitter) and YouTube mention tracking per `Entity`, with the
platform's first genuinely metered-cost feature: X's official pay-per-use
API bills real dollars per post read. YouTube's Data API is free-tier and
always fetched once an entity exists - no access gating needed for it at
all. Scope, per direct instruction: the data model, fetch logic, and cost
tracking, verifiable via CLI/API - no sentiment classification on social
content, no client-facing dashboard, and no automatic hard-cutoff on a
ceiling breach. All of those are explicitly later phases.

### 15.1 The core design question: shared fetch vs. per-client access

A subject like an entity's X mentions is public data - one fetch produces
the same posts regardless of which client asked for it. But whether a
*given client* should see (and be billed against) that data is a
per-contract decision. Collapsing these into one field forces a bad
choice: a single per-client "fetch X for this entity" flag would either
(a) fetch and pay for the same public posts once per client tracking that
entity - wasteful, multiplying real dollar cost by client count for
identical data - or (b) fetch once globally and let every client see it
regardless of their own contract - a straight access leak. Neither is
acceptable, so this phase keeps two separate tables:

- **`EntitySocialConfig`** (one row per `Entity`) is the shared, real-world
  truth: is X currently active for this entity, and what has actually been
  spent fetching it. This is where the one real API call per entity per
  fetch happens, and where its one real cost lands - independent of how
  many clients benefit from the resulting rows.
- **`ClientSubject`** (extended; composite `(client_id, entity_id)` key)
  carries `x_access` (does *this* client see X data for *this* entity) and
  `x_spend_ceiling_usd` (their own contracted monthly ceiling) - purely an
  access/reporting layer, contributing nothing to what gets fetched or
  what it costs.

The gating rule is a live query, not a cached flag: X is fetched for an
entity if and only if at least one *active* client currently has
`x_access=True` for it (`app/social/pipeline.py::_entity_has_active_x_access`).
`EntitySocialConfig.x_active` mirrors this for cheap display on the cost
screen (§15.4), but the actual fetch decision always re-queries
`ClientSubject`/`Client` at fetch time - trusting a cached boolean here
would risk fetching (and billing) for an entity whose last client already
revoked access, or skipping one that just gained it. `Client.active`
(deactivate, don't delete - same pattern as `Admin.is_active` from Phase
3) is part of that same live check, so an offboarded client's stale grant
can't keep costing money.

Ceiling comparisons are per `(client, entity)`, not a per-client total
split across every entity they track: each `ClientSubject.x_spend_ceiling_usd`
is compared directly against *that entity's* shared `EntitySocialConfig.x_spend_usd`
- a client tracking three entities with X access has three independent
ceiling checks, not one third of a combined budget. This matches how a
real contract would actually be written (a ceiling per subject, not an
opaque blended number) and avoids inventing a proportional-attribution
scheme that was never asked for.

`SocialMention` (entity_id, source, content_text, author, posted_at, url,
fetched_at, cost_usd) stores fetched content once regardless of which
clients can see it, deduplicated via `UNIQUE(entity_id, source, url)` -
visibility is a query-time join through `ClientSubject`, never duplicated
storage per client.

### 15.2 Billing accuracy vs. storage deduplication (deliberately not the same number)

X bills per post *read*, not per post *newly stored*. `app/social/x_api.py`
requests up to `max_results` (X enforces a real 10-100 bound server-side -
a request for fewer than 10 still returns, and bills, up to 10, a
cost-relevant floor worth stating rather than silently clamping around).
The cost accrued to `EntitySocialConfig.x_spend_usd` is
`x_cost_per_post_usd * len(mentions)` computed from the **raw** API
response, before deduplication - `app/social/pipeline.py::store_new_mentions`
then separately dedupes by URL for storage. A post already stored from an
earlier fetch is still billed again if a later recent-search call
re-returns it; the per-row `SocialMention.cost_usd` and the entity-level
running total will not always reconcile, and that's correct, not a bug -
X charges for the read, not for whether the platform already had a copy.
An earlier draft of `x_api.py` truncated the parsed list back down to the
caller's original `max_results` after already requesting the (floor-
adjusted) larger amount from the server - caught before it shipped, since
it would have silently under-counted real spend whenever the 10-post floor
exceeded what was asked for.

### 15.3 Monthly ceilings, lazily rolled over

`EntitySocialConfig.x_spend_usd` resets to zero whenever
`x_spend_period_start` no longer matches the first day of the current
calendar month, checked lazily on the next fetch that touches that entity
(`_roll_spend_period_if_needed`) - no scheduled job, consistent with
nothing in this codebase running on its own (ingest/process/assign-queue
are all the same shape). An entity nobody has fetched X for since last
month simply carries a stale `x_spend_usd` until its next fetch, which is
harmless since nothing reads that value as authoritative between fetches
except the cost screen, which is explicitly informational.

### 15.4 Super-admin cost visibility, deliberately gated and separate

`GET /admin/social-costs` (`social_costs.html`) is the only place real
spend and ceiling status are visible, and it's the one screen in this
whole project gated by `require_super_admin` for confidentiality reasons
rather than an escalation-of-privilege reason - Section 13's own framing
("could never be the one shared on a client call") calls for this to be
structurally impossible to put on screen during a client meeting, not
just a matter of admin discipline. It shows:

- **Entity spend (shared, current period)** - `EntitySocialConfig`'s real
  running total per entity, `x_active` status, how many clients currently
  have X access to it, and last-fetched time.
- **Per-client ceiling status** - every `ClientSubject` that currently has
  or ever had `x_access=True`, each entity's shared spend compared against
  that client's own ceiling, classified `OK` / `APPROACHING` (>=
  `SOCIAL_CEILING_WARN_RATIO`, default 80%, of ceiling) / `HIT` (spend >=
  ceiling) / `NO_CEILING` (access granted, no ceiling set) / `NO_ACCESS`.

Per direct instruction, a `HIT` or `APPROACHING` status is purely
informational for a super admin to act on (renegotiate, eat the overage,
or contact the client) - nothing here throttles fetching or access
automatically. Automatic cutoff on ceiling breach is an explicitly
out-of-scope future phase; a real contract might reasonably call for
eating an overage rather than silently breaking a promised service, and
that's a business decision this phase deliberately doesn't make for the
super admin.

`Client`/`ClientSubject` (Section 13.6) didn't exist before this phase -
Phase 5 explicitly deferred all of Section 13.6 to a later phase. They're
built now only as the minimum foundation this feature needs: a client to
grant/deny X access to, and a per-(client, entity) row to hold that grant
and its ceiling. `ClientUser` (client-facing logins) and any client-facing
UI are still not built - this stays a super-admin-only capability.

### 15.5 Verifying this phase (fake fetchers, no real API calls)

Same "no real network access in this sandbox" constraint and mocked-
provider convention as every prior phase (see §10). `SocialFetcher` is a
small provider-swappable interface (`app/social/base.py`), mirroring
`app/llm/base.py`'s classification providers but for fetching new external
content rather than classifying text already on hand. Verified with fake
`SocialFetcher` implementations standing in for `YouTubeFetcher`/`XFetcher`:

- X fetching is gated correctly - off with no client access, on once one
  client grants it, independently per entity, and off again once that
  access is revoked; YouTube keeps fetching regardless of X's state.
- `grant_x_access` rejects a non-positive ceiling (a ceiling with nothing
  to alert against isn't meaningful).
- The shared cost on `EntitySocialConfig` accrues once per fetch, not once
  per client with access to that entity.
- Re-fetching re-bills the shared cost without duplicating `SocialMention`
  storage (§15.2).
- Ceiling status against a **deliberately tiny fake ceiling**, as asked,
  before pointing this at a real X key: `OK` well under it, `HIT` once
  spend exceeds it, `APPROACHING` in the warn-ratio band between the two.
  A client merely tracking an entity with `x_access=False` never appears
  in the X cost report at all - it's not a zero/OK row, it's absent.
- Monthly period rollover resets a stale total to zero.
- Batch `fetch_social_mentions()` scans multiple entities, and a fetch
  exception on one source/entity is recorded per-entity without stopping
  the rest of the run or crashing.
- `/admin/social-costs` redirects when logged out and renders real data
  for a logged-in super admin.

Reachable via `python -m app.cli create-client --name ...`,
`show-clients`, `add-client-subject --client-id --entity-id [--x-ceiling]`,
`fetch-social [--limit]`, and `social-cost-report`; also
`POST /social/fetch` and `GET /social/mentions` (unauthenticated debug
endpoints, same category as `/articles`/`/entities`/`/clusters` - cost and
ceiling data is deliberately *not* exposed through these, only through the
gated admin screen).

**Flagged, not free-tier-friendly beyond the deliberate X dollar cost**:
YouTube's free tier is still a real 10,000-units/day quota, and a single
`search.list` call costs 100 units - roughly 100 entity-fetches/day across
the whole platform combined before hitting it, not literally unlimited.
A quota-exceeded response surfaces as an ordinary fetch error, caught and
recorded per-entity like any other failure, since there's nothing more
useful to do about it than wait for the daily reset. Both fetchers query
only an entity's canonical name, not its aliases, to avoid multiplying
quota cost (YouTube) or real per-post-read dollar cost (X) by alias count
- a deliberate coverage-vs-cost tradeoff, same shape as the alias-matching
tradeoffs already flagged in Phase 5 (§14.4), just for API cost instead of
match precision.

## 16. Phase 7: B2B Client Portal (Section 13.6)

The actual portal Section 13.6 describes and Phase 5/6 deliberately kept
deferring: a super admin can create a client, decide which entities they
track and whether that includes metered X access with a ceiling, and
issue them a login - and the client can log in and see exactly (and only)
what they're entitled to. Scope: the admin-side CRUD and the client-facing
login + read-only dashboard. Not built (still future phases, not asked
for here): self-service signup, quote/invoice generation, sentiment or
article-level content in the portal (this phase is social-listening data
only), and any password-reset flow (a super admin resets a client's
password the same way admin passwords are reset today - by setting a new
one, there's no forgot-password email flow anywhere in this project).

### 16.1 `ClientUser` - the login table Client's own docstring said didn't exist yet

Client (Phase 6) and ClientSubject (Phase 6) already existed; `ClientUser`
is new. One row per login, `client_id` FK to exactly one `Client` - a
client can have zero, one, or several logins (e.g. two people at the same
PR agency), and deactivating one login (`is_active=False`, same
deactivate-don't-delete posture as `Admin`/`Client`) never touches the
`Client` record or any other login on it. Password hashing reuses
`app/auth/security.py` (bcrypt) unchanged - it was already a generic
"verify a password against a stored hash" module, not something specific
to `Admin`.

### 16.2 Why client auth is a separate session key, not reused admin auth

`app/auth/client_session.py` mirrors `app/auth/session.py`'s shape
(`get_current_client_user` / `_optional`, a `ClientNotAuthenticated`
exception) but is a genuinely separate module, not a shared one with a
role check bolted on. Two reasons: a `ClientUser` and an `Admin` are
different account types with no shared identity (there's no "the same
login works for both" case to support), and an auth failure needs to
redirect to a different login page (`/client/login` vs `/admin/login`) -
`app/main.py` registers a separate exception handler per exception type
for exactly that. The session key itself (`client_user_id` vs
`admin_id`) is also different, and the client-side auth check clears only
its own key on a stale/deactivated session
(`request.session.pop("client_user_id", None)`) rather than the full
`request.session.clear()` the admin side uses - defensive against the
unlikely case of one browser somehow carrying both, at no real cost.

Both the login itself and every live session are checked against
`ClientUser.is_active` **and** `ClientUser.client.active` on every
request, not just at login time - deactivating a login kills an already-
open browser tab immediately (verified directly, not just future login
attempts), and deactivating the client itself locks out every login it
has, even ones that were perfectly valid a request ago. This is the same
"live check, not cached" discipline Phase 6 applied to the X-fetch-gating
decision, applied here to auth instead of billing.

### 16.3 Admin side: `/admin/clients` (super-admin gated, like `/admin/social-costs`)

Everything here was previously CLI-only (`create-client`,
`add-client-subject`, `python -m app.cli social-cost-report`) - same
underlying functions (`app.social.costs.grant_x_access` / `revoke_x_access`),
now also reachable as web forms:

- **`/admin/clients`** - list clients with entity/X-grant/login counts,
  deactivate/reactivate.
- **`/admin/clients/{id}`** - the main management page: add a tracked
  entity (with or without granting X access + a monthly ceiling in the
  same form submit), revoke X access or stop tracking an entity entirely,
  and create/deactivate/reactivate client logins - all in one page, same
  "one screen per client" shape as `/admin/admins` is for admin accounts.

`status_for` (X-ceiling OK/APPROACHING/HIT/NO_ACCESS/NO_CEILING
classification) was promoted from a private helper in `app/social/costs.py`
to a shared public function once this page needed the same classification
`list_client_cost_statuses` already computed - one function, two callers,
rather than a second copy of the same comparison logic.

### 16.4 Client side: `/client/*` (what the client actually sees)

- **`/client/login`** - separate branded header ("... Client Portal", not
  "News Review") from a `{% block header %}` added to `base.html` for
  exactly this purpose - existing admin pages don't override it, so their
  rendering is unchanged.
- **`/client/dashboard`** - every entity this client tracks, whether X is
  included for it, and - only where it is - their own current spend
  against their own contracted ceiling. Never another client's data, and
  never the cross-client aggregate `/admin/social-costs` shows - Section
  13's "could never be the one shared on a client call" instruction was
  about that internal screen specifically; a client seeing their *own*
  usage against their *own* contract is a narrower, ordinary thing for a
  paying customer's portal to show.
- **`/client/entities/{id}`** - recent YouTube mentions (always, for any
  tracked entity) and recent X mentions (**only** rendered into the page
  at all when `ClientSubject.x_access` is true for that entity - verified
  directly that the section is genuinely absent from the HTML, not merely
  empty, when access isn't granted). Requesting an entity the client
  doesn't track at all redirects to their dashboard rather than 404ing -
  a 404 would confirm the entity exists in the system at all, which isn't
  this client's business to know.

### 16.5 Verifying this phase

Same "no real network access, mocked/local test DB" approach as every
prior phase (see §10) - `fastapi.testclient.TestClient` driving the real
FastAPI app end-to-end through both the admin forms and the client login,
against the local Postgres test database, no browser needed. Verified:
admin-side CRUD is super-admin gated; a client granted X access on one
entity and tracking-only on another sees exactly that distinction
reflected on their dashboard and entity pages; the X section is absent
(not empty) from the page HTML when access isn't granted; an untracked
entity redirects rather than leaking its existence; deactivating a login
invalidates its live session immediately, not just future logins; and
deactivating the `Client` record itself locks out every login on it, not
just the one being tested. Full existing regression suite (all prior
phases) re-run with zero regressions.

**Not free-tier relevant, flagged for correctness anyway**: dashboard and
entity-page "current spend" default to `$0.0000` rather than crashing when
`EntitySocialConfig` doesn't exist yet for an entity with X access granted
but never fetched (`EntitySocialConfig` rows are created lazily on first
fetch, per Phase 6 - a freshly-granted subject legitimately has none yet).
Caught during manual walkthrough testing, not by the automated test file
initially - since fixed and the automated test now asserts the `$0.0000`
render explicitly rather than just checking for a 200 status.

## 17. Known gaps carried over from the planning doc

Per Section 11 of the planning doc: 48-hour SLA escalation, multi-admin
tie-breaking, the secondary "tone" axis, and a published methodology
document are all explicitly out of scope for the whole POC, not just
Phase 1.
