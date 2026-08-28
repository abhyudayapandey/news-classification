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
