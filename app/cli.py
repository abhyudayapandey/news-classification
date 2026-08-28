"""Manual command-line entry points for Phase 1.

Usage:
    python -m app.cli ingest          # run ingestion once, print a summary
    python -m app.cli show-articles   # list recently ingested articles
"""

import argparse
import logging
import sys

from app.db import SessionLocal
from app.ingestion.pipeline import run_ingestion
from app.models import Article, Outlet


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


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="News classification POC - manual CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("ingest", help="Fetch all active outlet feeds and store new articles")

    show_parser = subparsers.add_parser("show-articles", help="List recently ingested articles")
    show_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()

    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "show-articles":
        return cmd_show_articles(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
