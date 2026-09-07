# News Framing Platform — POC

India-focused news aggregation POC that classifies articles by topic and by
pro-establishment / anti-establishment framing, with a human-in-the-loop
admin review layer. See `news-framing-platform-poc.md` (the planning doc)
for the full product design — this README covers what's actually built and
how to run it.

**Phases 1-3 are built**: project scaffolding and the full database schema
plus RSS ingestion with wire-copy dedup (Phase 1); embedding-based topic
clustering and pro/anti/apolitical classification with jurisdiction/ruling-
party resolution (Phase 2 — see §9); and the login-gated admin/super-admin
review UI - queueing, blinding, confirm/override, account management, and
oversight views (Phase 3 — see §12). No public end-user website yet —
that's Phase 4.

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
  `sentence-transformers/all-MiniLM-L6-v2` (384-dim) through **onnxruntime,
  not PyTorch**. This is the one deliberate substitution from what was
  asked: `sentence-transformers`-the-library pulls in PyTorch, which alone
  needs several hundred MB of RAM even for a small model — tight to
  nonviable inside Render's free-tier 512MB web service. fastembed runs the
  *exact same model weights* through a much lighter runtime (onnxruntime is
  ~66MB installed, no PyTorch at all) — same model, same output vectors,
  different execution engine. `LOCAL_EMBEDDING_MODEL` in `.env` still names
  the model in the usual Hugging Face format.
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

## 13. Known gaps carried over from the planning doc

Per Section 11 of the planning doc: 48-hour SLA escalation, multi-admin
tie-breaking, the secondary "tone" axis, and a published methodology
document are all explicitly out of scope for the whole POC, not just
Phase 1.
