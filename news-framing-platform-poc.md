# News Framing Platform — POC Planning Document

**Scope:** India-only proof of concept
**Status:** Pre-build planning
**Last updated:** August 28, 2026

---

## 1. Overview

A news aggregation platform that organizes articles at two levels:

1. **Topic clustering** — grouping articles about the same underlying story across outlets
2. **Framing classification** — tagging how each article frames the story, using a **pro-establishment / anti-establishment / apolitical** axis instead of a US-style left/right axis, which maps poorly onto Indian media dynamics

The platform has an end-user–facing website and an internal admin review system that keeps a human in the loop on every framing decision before it's published.

---

## 2. Design Principles

- **No source bias in review.** Admins tag articles blind to the outlet, so review isn't influenced by an outlet's reputation.
- **Establishment is contextual, not global.** "Establishment" shifts by jurisdiction (Centre vs. state) and by time (elections change who's in power), so every pro/anti tag carries a jurisdiction and a resolved ruling party — never a bare label.
- **The platform can itself become a bias actor.** Every design choice — which axis to use, how outlets are labeled, what counts as "apolitical" — is an editorial act. Mitigated via transparency (published methodology), a human review layer, and structural humility (soft defaults, re-evaluation) rather than one-shot automated tags.
- **Build for where this goes, not just the POC.** Backend as an API from day one (mobile clients later), `Reviews[]` as an array (multi-admin approval later), even though the POC only ever populates one of each.

---

## 3. User Roles

| Role | Access |
|---|---|
| **End user** | Views articles organized by topic → story cluster, each shown across three sections: **Pro-Establishment**, **Anti-Establishment**, **Primary Source** |
| **Admin** | Reviews a queue of articles (headline + body only, source hidden). Confirms or overrides the system-generated tag. Each admin has their own queue; no overlap in POC. |
| **Super Admin** | Everything an Admin can do, plus: full CRUD on admin accounts, and a view showing **system tag vs. admin decision** side by side for every article, for calibration/oversight |

---

## 4. Framing Taxonomy

### 4.1 Core tags
- `pro-establishment`
- `anti-establishment`
- `apolitical`

### 4.2 Jurisdiction metadata (required whenever pro/anti is applied)
- **Level:** `centre` or `state` (+ which state)
- **Ruling party:** resolved via a **date-ranged lookup table** (`jurisdiction → ruling party → effective date range`), not hardcoded — state governments change (e.g., Karnataka flipped from BJP to Congress in 2023), and this table must be updated as governments change to avoid silent mislabeling.
- **Date/year:** already inherent to the article's publish timestamp; no separate field needed.

### 4.3 Apolitical handling
"Apolitical" is a **soft default**, not a final state — a story can turn political after initial publication (e.g., an accident becomes political once negligence or a named official is implicated). Two safety nets, used together:

1. **Entity-trigger net:** presence of certain entities (MLA/MP names, ministry names, government tenders/contracts, named political parties) in an "apolitical"-classified article auto-flags it for admin review, overriding the classifier's first pass.
2. **Cluster re-evaluation:** if any new article in an existing story cluster gets classified as establishment-relevant, the **entire cluster** is re-flagged for review — not just the new article — since clustering (level 1) and tagging (level 2) are not fully independent stages.

### 4.4 Primary Source
Renamed from "Fact" — a government statement, official data release, or speech is a primary document, not neutral truth, and calling it "fact" risks baking pro-establishment framing into the platform itself.

- Where a clean primary source exists (official data, court order, PIB release, video of a speech/interview), it's linked directly.
- Where no such source exists for a story (common — most political controversies don't have one clean underlying document), the section shows an explicit **"No primary source available for this story"** state rather than forcing something in.

### 4.5 Deferred (not in POC scope, to be noted as future work)
- Secondary "tone" axis (measured/investigative vs. sensational/rhetorical criticism)
- Tie-breaking logic for multi-admin approval

---

## 5. Admin Review Workflow

- **Blinding:** Admins see headline + body text only.
  - Outlet name: hidden.
  - Bylines/reporter names: left visible (acceptable).
  - Self-references (e.g., "as this newspaper reported"): replaced with placeholder text (e.g., `[self-reference removed]`) rather than blank/blur, to avoid reading as a UI bug.
  - Distinctive outlet writing style / PTI-ANI wire copy: left as-is, intentionally — recognizing an outlet's own editorial voice (or lack thereof, in the case of unedited wire copy) is part of what the review is meant to surface.
- **Dedup before review:** Identical PTI/ANI wire copy run verbatim across multiple outlets should be deduplicated before hitting the review queue, so admins aren't repeatedly tagging the same text.
- **Queue order:** Oldest-first, to avoid staleness.
- **Staleness SLA:** 48 hours. (Escalation/auto-publish behavior when this is exceeded is **not built in the POC** — noted as a known gap; policy to be decided before this becomes a real risk.)
- **Assignment:** Each admin has their own queue (no overlap). Each admin's decision **is** the published tag for that article — no reconciliation step needed at POC scale.
- **Review record:** Decision is stored as `agreed_with_system` or `overrode`, tied to admin ID and timestamp — kept as a structured record (not just a final tag overwrite) so the history is preserved even in the single-admin model.

---

## 6. Data Model (conceptual)

```
Article
 ├── id
 ├── headline
 ├── body_text
 ├── outlet_id            (hidden from admin view, visible to super admin)
 ├── published_at
 ├── cluster_id            → Story Cluster
 ├── system_tag
 │     ├── classification   (pro / anti / apolitical)
 │     ├── jurisdiction     (centre / state:<name>)
 │     ├── ruling_party     (resolved via lookup table)
 │     └── confidence_score
 ├── reviews[]              ← array now, POC populates exactly one
 │     ├── admin_id
 │     ├── final_tag
 │     ├── decision         (agreed_with_system / overrode)
 │     └── timestamp
 └── published_tag          ← separate field; POC = copy of the single review;
                                future = e.g. majority vote of reviews[], without
                                touching anything downstream

Story Cluster
 ├── id
 ├── topic                  (politics, economy, sports, etc.)
 ├── articles[]             → Article
 ├── primary_source_url     (nullable — "no primary source available" state)
 └── needs_review           (flag, set true if any member article's
                                establishment-relevance changes post-publish)

Outlet
 ├── id
 ├── name
 ├── rss_feed_url

Jurisdiction Ruling-Party Lookup
 ├── jurisdiction            (centre or state name)
 ├── ruling_party
 ├── effective_from
 └── effective_to

Admin
 ├── id
 ├── name
 ├── role                    (admin / super_admin)
```

---

## 7. Pipeline Stages

1. **Ingest** — pull from RSS feeds, 8–10 Indian English-language outlets
2. **Dedup** — catch identical wire copy (PTI/ANI) across outlets before it reaches clustering/review
3. **Cluster** — embed articles, group same-story coverage across outlets within a time window (level 1: topic)
4. **Pre-filter** — is this article establishment-relevant at all? (LLM zero-shot classification) → apolitical articles skip straight to publish with an `apolitical` tag, subject to the entity-trigger net
5. **Classify** — for establishment-relevant articles: pro/anti + jurisdiction + ruling-party lookup (level 2: framing)
6. **Queue** — goes into the relevant admin's oldest-first review queue
7. **Review** — admin confirms or overrides the tag; blinding rules applied to displayed text
8. **Publish** — `published_tag` set from the review; article appears under its cluster in the relevant end-user section
9. **Re-evaluation trigger** — new article added to an existing cluster with establishment-relevant classification → flags the whole cluster's `needs_review`

---

## 8. Platform Architecture

- **Website-first**, but backend built as a standalone API — website is a client of the API, not a place where business logic lives.
- Auth, article-fetch, tag-display, and admin-review-submit all exposed as API endpoints from day one, even with only one client (the website) consuming them initially.
- This keeps the door open to iOS/Android clients later without backend re-architecture. Framework choices that allow logic-sharing across web and future mobile clients (e.g., React Native/Flutter) are worth considering when that time comes, but aren't a POC decision.
- **No real-time updates in POC** — standard page-load/refresh model. Sockets/polling deferred as unnecessary cost at this stage.

---

## 9. End-User View

For each story cluster, three sections:
- **Pro-Establishment** — articles tagged as such, with jurisdiction/ruling-party context shown
- **Anti-Establishment** — same
- **Primary Source** — direct link to official data/speech/document, or an explicit "not available" state

Apolitical articles appear under their topic without framing tags.

---

## 10. Admin & Super Admin Views

**Admin:**
- Queue of assigned articles, oldest-first
- Per article: headline + body (source hidden, self-references redacted)
- System-generated tag shown, with option to confirm or override

**Super Admin:**
- Everything above, plus:
  - Full CRUD on admin accounts
  - Per-article view showing **system tag vs. admin decision** side by side, for calibration and oversight

---

## 11. Known Gaps / Deferred to Post-POC

- Escalation or auto-publish behavior when the 48-hour SLA is exceeded
- Tie-breaking logic for when multi-admin approval is eventually introduced
- Secondary "tone" axis (sensational vs. measured criticism)
- Formal published methodology document for outlet/jurisdiction tagging (needed if this moves beyond POC, for transparency)
- Real-time update mechanism (sockets/polling), if usage patterns justify it later
- Mobile clients (iOS/Android) — architecture supports it, but not part of POC build

---

## 12. POC Build Scope Summary

- 8–10 free RSS feeds, English-language Indian outlets
- Topic clustering (embeddings + time window)
- Establishment pre-filter + pro/anti/apolitical classification + jurisdiction/ruling-party tagging
- Single-admin review workflow, oldest-first, 48-hour SLA (soft, unenforced in POC)
- Website only, API-first backend
- Three end-user sections per story: Pro-Establishment / Anti-Establishment / Primary Source
- Super admin oversight view

---

## 13. B2B Direction — Entity Tagging & Subject Framing (Post-Launch)

**Context:** Beyond the consumer site, a B2B use case emerged: PR and political-consultancy agencies want to track how a specific **subject** (a person or party) is covered across outlets over time — not just how a story is framed. This requires two new capabilities, plus a third that's explicitly parked.

### 13.1 Entity Tagging (near-term, natural extension)

The Phase 2 entity-trigger net (MLA/MP names, party names, ministries) already does informal entity detection — used today only as a binary trigger for the apolitical safety net. This phase promotes entity detection into a first-class, queryable data model.

**New data model:**

```
Entity
 ├── id
 ├── name
 ├── type                  (person / party)
 ├── aliases[]             (name variants, e.g. "PM Modi" / "Narendra Modi")
 └── metadata               (party affiliation if type=person, jurisdiction if relevant)

ArticleEntity  (many-to-many join)
 ├── article_id
 ├── entity_id
 └── prominence             (optional: is this entity central to the article, or an incidental mention?)
```

- Entity extraction runs as a new pipeline stage, likely reusing the same embedding/NER approach already in place for the trigger net, extended to store results rather than just act as a filter.
- `prominence` matters: a subject mentioned once in passing is a different signal than a subject the article is actually about. Worth deciding a simple heuristic (e.g., mention count, position in text, headline presence) rather than skipping this distinction.
- This enables the core B2B query: "show me every article about Subject X, across all outlets, over time period Y."

### 13.2 Subject-Specific Framing Axis (near-term, needs design judgment)

**The core issue:** the existing pro/anti-establishment axis measures framing *relative to the government in power* — not framing relative to a specific subject. An article can be anti-establishment while being complimentary toward a specific opposition figure who is the one criticizing the government. These are two different axes and both matter to a PR client.

**Proposed addition:**

```
ArticleEntity (extended)
 ├── article_id
 ├── entity_id
 ├── prominence
 └── subject_sentiment      (favorable / unfavorable / neutral — toward THIS entity specifically,
                               independent of the article's establishment tag)
```

- This is a second, independent classification pass — same pipeline shape as the existing classifier (system-generated, then admin-reviewed blind), but scored per-entity rather than per-article, since one article can mention multiple entities with different sentiment toward each.
- Naming deliberately avoids "pro/anti" for this axis, to keep it visually and conceptually distinct from the establishment tags — this is closer to conventional sentiment analysis, and should read as such, not be confused with the platform's core establishment framing.
- Review workflow question to resolve before building: does this get its own admin review queue, or get folded into the existing per-article review screen (reviewing both axes at once)? Leaning toward folding in, to avoid doubling review load — worth confirming once volume is known.

### 13.3 Social Media Listening (explicitly parked, not scoped)

Raised by a PR-agency contact as a desired feature. Deliberately **not** treated as a natural extension of the platform — flagged as a different product with different economics:

- Different data pipeline entirely (X/Meta APIs, not RSS) — meaningful API costs at any real volume, breaking the platform's $0-infrastructure approach.
- A mature, well-funded competitive category already (Brandwatch, Sprinklr, Talkwalker, Meltwater) — little differentiation available here versus incumbents.
- **Preferred direction if this comes up again:** position the platform's framing data as a complement to a client's *existing* social listening tool, rather than building a competing one. Revisit only if a paying client specifically funds it.

### 13.4 Other Monetization Directions Discussed (for reference)

- Data licensing to press-freedom/research institutions — smaller revenue, strong credibility value for funding narrative.
- Brand-safety signal for ad tech.
- Political-risk signal for market/investment intelligence (larger budgets, more sophisticated sales motion — not near-term).
- Election-cycle monitoring engagements for civil-society/election-monitoring bodies.
- Licensing to journalism schools for media-literacy education (credibility/goodwill, not primary revenue).
- API/data licensing to other media-tech products ("picks and shovels" model).
- Newsroom self-benchmarking (unusual sell — pitching the outlets being evaluated).

### 13.5 Legal Flag — Commercialization Raises the Stakes

The JSON-LD paywall-extraction tradeoff (Section 4, addendum below) was accepted as a POC-stage risk on the basis that extracted content is **never shown to end users**. Selling B2B insights derived from that same content is a materially different position — commercial benefit from paywall-bypassed content is harder to defend than free internal-only classification. **A real legal opinion is needed before committing to the B2B direction**, not deferred further once this becomes a paid product.

---

### 13.6 Client Portal (B2B-facing, separate from Admin)

**Structural decision:** the client portal is a **separate application surface** from the internal Admin/Super Admin dashboard — not a section within it. Admins are trusted internal reviewers; B2B clients are external paying customers. Same underlying data, different login system, different access surface, kept structurally distinct to avoid permission creep and to keep "admin" meaning one thing.

**Data model:**

```
Client
 ├── id, name, contract_start, active

ClientUser                (login accounts for the client's own team)
 ├── id, client_id, email, password_hash

ClientSubject             (many-to-many: a client can track multiple entities;
                              an entity, e.g. a party, can be tracked by multiple clients)
 ├── client_id, entity_id, added_at, backfilled (bool)
```

Client portal queries filter strictly through: `published articles ↔ ArticleEntity ↔ Entity ↔ ClientSubject ↔ Client`, scoped to the logged-in client's own subjects only. Tenant isolation enforced at the query layer, not just the UI.

**Onboarding flow:**
1. Client tells you who/what they want tracked (a person, a party, possibly several).
2. **Human check before going live:** a super admin confirms or creates the corresponding `Entity` (with correct aliases) rather than auto-creating one from whatever string the client typed — avoids ambiguous-name mismatches (e.g., common first names, regional figures sharing a name with someone more prominent).
3. Once the `Entity` exists and is linked via `ClientSubject`, a **one-time backfill scan** runs against already-ingested articles for that entity, so the client sees historical coverage, not just coverage from the moment they signed up.
4. Going forward, the entity is part of standard extraction — no special-casing needed once seeded.

**Review standard:** the client portal shows **`published_tag`-based data only** — same reviewed-only standard as the B2C site. No unreviewed/system-tag-only articles are surfaced, to keep both products credible and consistent rather than having B2B trade accuracy for speed.

**Operational note:** since B2B clients may care about turnaround more than B2C readers do, admins need visibility into which pending articles relate to a paying client's tracked subject, so review priority isn't dependent on a side conversation. Recommend a simple visual flag/badge in the admin queue showing linked client subject(s) on relevant articles — priority made legible in the tool itself, not held only in the founder's memory.

---

### Addendum to Section 4 — Paywall Content Handling (decided post-launch)

For outlets that paywall content, the platform extracts full text via the JSON-LD block served to search crawlers, for **internal classification purposes only**. This content is never surfaced to end users, who only ever see the RSS teaser plus a link to the outlet's own site. This is accepted as a deliberate POC-stage tradeoff — the alternative (paying for subscriptions to every ingested outlet) isn't viable for a self-funded POC — and is to be revisited before any public launch expansion, funding due diligence, or (per Section 13.5) B2B commercialization.
