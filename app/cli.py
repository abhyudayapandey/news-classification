"""Manual command-line entry points.

Usage:
    python -m app.cli ingest              # Phase 1: fetch feeds, store new articles
    python -m app.cli show-articles       # Phase 1: list recently ingested articles
    python -m app.cli process             # Phase 2: cluster + classify unprocessed articles
    python -m app.cli show-clusters       # Phase 2: list story clusters
    python -m app.cli seed-jurisdictions  # Phase 2: upsert app/data/jurisdiction_seed.py
    python -m app.cli verify-local-models # Phase 2: confirm the embedding model downloads/loads
    python -m app.cli compare-providers   # Phase 2: run multiple providers on the same articles, side by side
    python -m app.cli assign-queue        # Phase 3: assign classified articles to admin queues
    python -m app.cli heal-bio-scrapes    # Phase 3: one-time cleanup for wrongly-accepted author-bio scrapes
    python -m app.cli divert-unreviewable # Phase 3: one-time cleanup, move textless articles to Manual Review
    python -m app.cli retry-failed-scrapes # Phase 3: re-attempt scraping for articles with a scrape_error
    python -m app.cli create-admin        # Phase 3: create an admin/super_admin account
    python -m app.cli seed-entities       # Phase 5: upsert app/data/entity_seed.py
    python -m app.cli backfill-entities   # Phase 5: (re-)run entity extraction against already-ingested articles
    python -m app.cli show-entities       # Phase 5: list seeded entities
"""

import argparse
import getpass
import logging
import sys

from app.db import SessionLocal
from app.ingestion.pipeline import run_ingestion
from app.models import Article, Outlet, StoryCluster


def cmd_ingest(_args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        results = run_ingestion(db)
    finally:
        db.close()

    print("\nIngestion run summary")
    print("-" * 60)
    had_error = False
    for r in results:
        if r.error:
            had_error = True
            print(f"{r.outlet_name:30s} ERROR: {r.error}")
            continue
        print(
            f"{r.outlet_name:30s} fetched={r.fetched:4d}  "
            f"new={r.inserted_new:4d}  duplicate={r.inserted_duplicate:4d}  "
            f"already_seen={r.skipped_existing:4d}"
        )
    print("-" * 60)
    return 1 if had_error else 0


def cmd_show_articles(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        articles = (
            db.query(Article)
            .join(Outlet)
            .order_by(Article.ingested_at.desc())
            .limit(args.limit)
            .all()
        )
        if not articles:
            print("No articles in the database yet. Run `python -m app.cli ingest` first.")
            return 0

        for a in articles:
            dup_marker = f" [duplicate of #{a.duplicate_of_id}]" if a.duplicate_of_id else ""
            print(f"#{a.id:<5d} [{a.outlet.name:20s}] {a.published_at:%Y-%m-%d %H:%M}  {a.headline}{dup_marker}")
    finally:
        db.close()
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    from app.processing.pipeline import process_articles

    db = SessionLocal()
    try:
        result = process_articles(db, limit=args.limit)
    finally:
        db.close()

    print("\nProcessing run summary")
    print("-" * 60)
    print(f"processed:                    {result.processed}")
    print(f"new clusters:                 {result.new_clusters}")
    print(f"joined existing clusters:     {result.joined_existing_clusters}")
    print(f"apolitical:                   {result.apolitical}")
    print(f"pro-establishment:            {result.pro_establishment}")
    print(f"anti-establishment:           {result.anti_establishment}")
    print(f"entity-trigger overrides:     {result.entity_trigger_overrides}")
    print(f"clusters flagged needs_review:{result.clusters_flagged_needs_review}")
    print(f"unresolved ruling party:      {result.unresolved_ruling_party}")
    print(f"entity mentions found:        {result.entity_mentions_found}")
    print(f"entity sentiments classified: {result.entity_sentiments_classified}")
    print(f"remaining unprocessed:        {result.remaining_unprocessed}")
    print("-" * 60)
    if result.errors:
        print(f"{len(result.errors)} article(s) failed:")
        for err in result.errors:
            print(f"  - {err}")
        return 1
    return 0


def cmd_show_clusters(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        clusters = db.query(StoryCluster).order_by(StoryCluster.created_at.desc()).limit(args.limit).all()
        if not clusters:
            print("No clusters yet. Run `python -m app.cli process` first.")
            return 0
        for c in clusters:
            review_marker = " [NEEDS REVIEW]" if c.needs_review else ""
            print(f"#{c.id:<5d} topic={c.topic or '(none)':22s} articles={len(c.articles):3d}{review_marker}")
            for a in c.articles:
                tag = a.system_tag.classification.value if a.system_tag else "?"
                print(f"       #{a.id:<5d} [{tag:20s}] {a.headline}")
    finally:
        db.close()
    return 0


def cmd_seed_jurisdictions(_args: argparse.Namespace) -> int:
    from app.data.jurisdiction_seed import seed_jurisdictions

    db = SessionLocal()
    try:
        inserted, updated = seed_jurisdictions(db)
    finally:
        db.close()
    print(f"Inserted {inserted} new row(s), updated (closed out) {updated} existing row(s).")
    print("Review app/data/jurisdiction_seed.py's module docstring for what's confirmed vs. still needs verification.")
    return 0


def cmd_verify_local_models(_args: argparse.Namespace) -> int:
    from app.llm.local_embedding import LocalEmbeddingProvider

    print("Downloading/loading local embedding model (first run only downloads)...")
    try:
        provider = LocalEmbeddingProvider()
        vectors = provider.embed(["This is a test sentence.", "Another test sentence."])
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}")
        return 1
    print(f"OK: model={provider.model_name}, produced {len(vectors)} vectors of dimension {len(vectors[0])}")
    return 0


def cmd_compare_providers(args: argparse.Namespace) -> int:
    """Runs each requested provider on the same sample of articles and
    prints results side by side - does NOT write to the database (SystemTag
    stays strictly 1:1 with Article; see app/models/system_tag.py). Use
    this once you've funded OPENAI_API_KEY/GEMINI_API_KEY to see how they
    compare against the free local provider on real articles.
    """
    from app.llm.factory import get_embedding_provider

    providers = {}
    for name in args.providers.split(","):
        name = name.strip()
        if name == "local":
            from app.llm.local_classification import EmbeddingSimilarityClassifier

            providers["local"] = EmbeddingSimilarityClassifier(embedding_provider=get_embedding_provider())
        elif name == "openai":
            from app.llm.openai_provider import OpenAIClassificationProvider

            providers["openai"] = OpenAIClassificationProvider()
        elif name == "gemini":
            from app.llm.gemini_provider import GeminiClassificationProvider

            providers["gemini"] = GeminiClassificationProvider()
        else:
            print(f"Unknown provider {name!r} - expected local, openai, or gemini")
            return 1

    db = SessionLocal()
    try:
        articles = (
            db.query(Article)
            .filter(Article.duplicate_of_id.is_(None))
            .order_by(Article.ingested_at.desc())
            .limit(args.limit)
            .all()
        )
        if not articles:
            print("No articles to compare. Run `python -m app.cli ingest` first.")
            return 0

        for a in articles:
            print(f"\n#{a.id} {a.headline}")
            for pname, provider in providers.items():
                try:
                    result = provider.classify(a.headline, a.body_text)
                    print(
                        f"  {pname:10s} -> {result.classification.value:20s} "
                        f"jurisdiction={result.jurisdiction or '-':20s} confidence={result.confidence_score:.2f}"
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"  {pname:10s} -> ERROR: {exc}")
    finally:
        db.close()
    return 0


def cmd_assign_queue(args: argparse.Namespace) -> int:
    from app.review.assignment import assign_pending_articles

    db = SessionLocal()
    try:
        result = assign_pending_articles(db, limit=args.limit)
    finally:
        db.close()
    print(f"Assigned {result.assigned} article(s) to admin queues.")
    print(f"Re-scraped {result.rescraped} already-assigned article(s) that had no prior scrape attempt.")
    return 0


def cmd_heal_bio_scrapes(args: argparse.Namespace) -> int:
    from app.review.assignment import heal_bio_scrapes

    db = SessionLocal()
    try:
        result = heal_bio_scrapes(db, limit=args.limit)
    finally:
        db.close()
    print(f"{result.matched} article(s) currently have a stored scrape that looks like an author bio.")
    print(f"Re-attempted {result.rescraped} of them this run.")
    if result.matched > result.rescraped:
        print("Run again to continue healing the rest.")
    return 0


def cmd_divert_unreviewable(_args: argparse.Namespace) -> int:
    from app.review.assignment import divert_unreviewable_articles

    db = SessionLocal()
    try:
        result = divert_unreviewable_articles(db)
    finally:
        db.close()
    print(f"Moved {result.diverted} article(s) with no usable text to the Manual Review bucket.")
    return 0


def cmd_retry_failed_scrapes(args: argparse.Namespace) -> int:
    from app.review.assignment import retry_failed_scrapes

    db = SessionLocal()
    try:
        result = retry_failed_scrapes(db, limit=args.limit)
    finally:
        db.close()
    print(f"{result.matched} unreviewed article(s) currently have a scrape_error on record.")
    print(f"Re-attempted {result.rescraped} of them this run.")
    print(f"{result.recovered} recovered usable text and left the Manual Review bucket.")
    if result.recovered:
        print("Run `assign-queue` to actually queue the recovered ones to an admin.")
    if result.matched > result.rescraped:
        print("Run again to continue retrying the rest.")
    return 0


def cmd_seed_entities(_args: argparse.Namespace) -> int:
    from app.data.entity_seed import seed_entities

    db = SessionLocal()
    try:
        inserted, updated = seed_entities(db)
    finally:
        db.close()
    print(f"Inserted {inserted} new entit(y/ies), updated {updated} existing one(s).")
    print("See app/data/entity_seed.py's module docstring for what's confidently seeded vs. flagged gaps.")
    return 0


def cmd_backfill_entities(args: argparse.Namespace) -> int:
    from app.processing.entities import backfill_entities

    db = SessionLocal()
    try:
        result = backfill_entities(db, limit=args.limit, rescan_all=args.rescan_all)
    finally:
        db.close()
    print(f"Scanned {result.scanned} article(s).")
    print(f"Ran {result.new_mentions_classified} new sentiment classification(s) (skipped for pairs already scored).")
    print(f"{result.remaining} article(s) still left to scan this mode.")
    if result.remaining:
        print("Run again (same flags) to continue.")
    return 0


def cmd_show_entities(args: argparse.Namespace) -> int:
    from app.models import Entity

    db = SessionLocal()
    try:
        entities = db.query(Entity).order_by(Entity.type, Entity.name).limit(args.limit).all()
        if not entities:
            print("No entities seeded yet. Run `python -m app.cli seed-entities` first.")
            return 0
        for e in entities:
            alias_str = f" (aka {', '.join(e.aliases)})" if e.aliases else ""
            mention_count = len(e.mentions)
            print(f"#{e.id:<4d} [{e.type.value:6s}] {e.name}{alias_str} - {mention_count} article mention(s)")
    finally:
        db.close()
    return 0


def cmd_create_admin(args: argparse.Namespace) -> int:
    from app.auth.security import hash_password
    from app.models import Admin
    from app.models.enums import AdminRole

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match.")
        return 1

    db = SessionLocal()
    try:
        if db.query(Admin).filter(Admin.username == args.username).one_or_none() is not None:
            print(f"Username {args.username!r} is already taken.")
            return 1
        try:
            password_hash = hash_password(password)
        except ValueError as exc:
            print(str(exc))
            return 1
        db.add(Admin(username=args.username, name=args.name, password_hash=password_hash, role=AdminRole(args.role)))
        db.commit()
    finally:
        db.close()
    print(f"Created {args.role} account {args.username!r}.")
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="News classification POC - manual CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ingest", help="Fetch all active outlet feeds and store new articles")

    show_parser = subparsers.add_parser("show-articles", help="List recently ingested articles")
    show_parser.add_argument("--limit", type=int, default=20)

    process_parser = subparsers.add_parser("process", help="Cluster + classify unprocessed articles")
    process_parser.add_argument(
        "--limit", type=int, default=None, help="Max articles to process this run (default: no limit)"
    )

    show_clusters_parser = subparsers.add_parser("show-clusters", help="List story clusters")
    show_clusters_parser.add_argument("--limit", type=int, default=20)

    subparsers.add_parser("seed-jurisdictions", help="Upsert the jurisdiction -> ruling party lookup table")

    subparsers.add_parser("verify-local-models", help="Confirm the local embedding model downloads and loads")

    compare_parser = subparsers.add_parser(
        "compare-providers", help="Run multiple classification providers on the same articles, side by side"
    )
    compare_parser.add_argument(
        "--providers", default="local", help="Comma-separated: local,openai,gemini (default: local)"
    )
    compare_parser.add_argument("--limit", type=int, default=10)

    assign_parser = subparsers.add_parser("assign-queue", help="Assign classified articles to admin queues")
    assign_parser.add_argument("--limit", type=int, default=None, help="Max articles to assign (default: no limit)")

    heal_bio_parser = subparsers.add_parser(
        "heal-bio-scrapes",
        help="One-time cleanup: re-attempt scrapes that were wrongly accepted as an author bio",
    )
    heal_bio_parser.add_argument(
        "--limit", type=int, default=None, help="Max articles to re-attempt (default: no limit)"
    )

    subparsers.add_parser(
        "divert-unreviewable",
        help="One-time cleanup: move already-stuck, textless articles to the Manual Review bucket",
    )

    retry_failed_parser = subparsers.add_parser(
        "retry-failed-scrapes",
        help="Re-attempt scraping for unreviewed articles with a scrape_error on record",
    )
    retry_failed_parser.add_argument(
        "--limit", type=int, default=None, help="Max articles to re-attempt (default: no limit)"
    )

    create_admin_parser = subparsers.add_parser("create-admin", help="Create an admin/super_admin account")
    create_admin_parser.add_argument("--username", required=True)
    create_admin_parser.add_argument("--name", required=True)
    create_admin_parser.add_argument("--role", choices=["admin", "super_admin"], default="admin")

    subparsers.add_parser("seed-entities", help="Upsert the Entity table from app/data/entity_seed.py")

    backfill_entities_parser = subparsers.add_parser(
        "backfill-entities", help="(Re-)run entity extraction against already-ingested, classified articles"
    )
    backfill_entities_parser.add_argument(
        "--limit", type=int, default=None, help="Max articles to scan this run (default: no limit)"
    )
    backfill_entities_parser.add_argument(
        "--rescan-all", action="store_true",
        help="Re-scan every classified article, not just ones never scanned before (use after adding a new entity)",
    )

    show_entities_parser = subparsers.add_parser("show-entities", help="List seeded entities and their mention counts")
    show_entities_parser.add_argument("--limit", type=int, default=100)

    args = parser.parse_args()

    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "show-articles":
        return cmd_show_articles(args)
    if args.command == "process":
        return cmd_process(args)
    if args.command == "show-clusters":
        return cmd_show_clusters(args)
    if args.command == "seed-jurisdictions":
        return cmd_seed_jurisdictions(args)
    if args.command == "verify-local-models":
        return cmd_verify_local_models(args)
    if args.command == "compare-providers":
        return cmd_compare_providers(args)
    if args.command == "assign-queue":
        return cmd_assign_queue(args)
    if args.command == "heal-bio-scrapes":
        return cmd_heal_bio_scrapes(args)
    if args.command == "divert-unreviewable":
        return cmd_divert_unreviewable(args)
    if args.command == "retry-failed-scrapes":
        return cmd_retry_failed_scrapes(args)
    if args.command == "create-admin":
        return cmd_create_admin(args)
    if args.command == "seed-entities":
        return cmd_seed_entities(args)
    if args.command == "backfill-entities":
        return cmd_backfill_entities(args)
    if args.command == "show-entities":
        return cmd_show_entities(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
