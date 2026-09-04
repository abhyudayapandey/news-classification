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
    python -m app.cli create-admin        # Phase 3: create an admin/super_admin account
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
        assigned = assign_pending_articles(db, limit=args.limit)
    finally:
        db.close()
    print(f"Assigned {assigned} article(s) to admin queues.")
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

    create_admin_parser = subparsers.add_parser("create-admin", help="Create an admin/super_admin account")
    create_admin_parser.add_argument("--username", required=True)
    create_admin_parser.add_argument("--name", required=True)
    create_admin_parser.add_argument("--role", choices=["admin", "super_admin"], default="admin")

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
    if args.command == "create-admin":
        return cmd_create_admin(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
