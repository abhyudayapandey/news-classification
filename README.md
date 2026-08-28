# News Framing Platform — POC (Phase 1: Foundation)

India-focused news aggregation POC that classifies articles by topic and by
pro-establishment / anti-establishment framing, with a human-in-the-loop
admin review layer. See `news-framing-platform-poc.md` (the planning doc)
for the full product design — this README covers what's actually built and
how to run it.

**Phases 1 and 2 are built**: project scaffolding, the full database schema,
RSS ingestion with wire-copy dedup (Phase 1), and embedding-based topic
clustering + pro/anti/apolitical classification with jurisdiction/ruling-
party resolution (Phase 2 — see §9). No admin UI, no website yet — those
are Phase 3. Everything here is built so that phase slots in without a
schema rewrite.

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
  main.py              FastAPI app (health, articles, ingestion, processing, clusters)
  config.py            Settings from .env (pydantic-settings)
  db.py                SQLAlchemy engine/session, declarative Base
  constants.py         Fixed technical constants (e.g. EMBEDDING_DIM)
  cli.py               Manual CLI - ingest, process, show-*, seed-jurisdictions, etc.
  models/              SQLAlchemy models — one file per Section 6 entity (+ Phase 2 fields)
  schemas/             Pydantic response models for the API
  routers/             FastAPI routers (health, articles, ingestion, processing, clusters)
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
Phase 2, everything except `reviews` and `admins` is populated:

| Table | Populated as of | Notes |
|---|---|---|
| `outlets` | Phase 1 | Synced from `config/outlets.yaml` on every ingestion run |
| `articles` | Phase 1 (+ Phase 2 fields) | `published_tag` stays NULL until Phase 3 review, except apolitical articles (Phase 2 sets it directly) |
| `story_clusters` | Phase 2 | Populated by `app/processing/clustering.py` |
| `system_tags` | Phase 2 | 1:1 with `articles`; written by `app/processing/pipeline.py` |
| `jurisdiction_ruling_parties` | Phase 2 (seeded) | Manually maintained lookup table — see §9.4 for what's seeded and what needs verification |
| `reviews` | No (table exists, empty) | One-to-many now so multi-admin reconciliation can be added later without a migration; Phase 3 only ever inserts one row per article |
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

**Status**: done — deployed at `news-classification-api-qp8a.onrender.com`,
`/ingest/run` returned `error: null` for all three outlets, and a repeat
call correctly no-op'd on already-seen articles (idempotent re-ingestion
confirmed against real feeds, not just local mocks). One real bug was
caught and fixed along the way: the feed fetcher accepted a
`timeout_seconds` parameter that was never actually applied, so a feed
that hung without erroring could have stalled `/ingest/run` indefinitely —
see the "Fix: actually enforce the feed fetch timeout" commit.

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

- Admin review queue, blinding, self-reference redaction (Phase 3)
- Super-admin analytics dashboard (Phase 3) — the `system_tags` and
  `reviews` schema is ready for it, nothing more
- End-user website (later)
- Any auth (Admin table has no password/session fields yet)
- OpenAI/Gemini *embedding* providers (only classification has paid
  providers so far — see §11)

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

**Seed data — please read before trusting it.** `app/data/jurisdiction_seed.py`
seeds Centre + the ~20 most populous states. Run it once:

```bash
python -m app.cli seed-jurisdictions
```

This data has a real, specific accuracy problem worth calling out rather
than glossing over: my knowledge of Indian politics has a training cutoff
of January 2026, and this was built in a session dated August 2026 — a
seven-month gap. Assembly elections were expected in that window for
**West Bengal, Kerala, Tamil Nadu, Assam, and Bihar** — those five rows are
flagged `STALE RISK` directly in the seed file and are likely already
wrong by the time you read this. Every other row reflects my best
knowledge as of the cutoff and is more likely still current (most state
governments run fixed 5-year terms with nothing due), but "more likely
current" is not "verified" — this table is explicitly designed to be
hand-maintained (per the planning doc's own warning about silent
mislabeling as governments change), and seeding it once doesn't change
that upkeep is on you going forward. Add a new row with its own
`effective_from` rather than editing an existing one when something
changes, so date-ranged lookups on older articles stay correct.

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

## 11. Known gaps carried over from the planning doc

Per Section 11 of the planning doc: 48-hour SLA escalation, multi-admin
tie-breaking, the secondary "tone" axis, and a published methodology
document are all explicitly out of scope for the whole POC, not just
Phase 1.
