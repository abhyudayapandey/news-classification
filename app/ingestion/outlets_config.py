"""Loads config/outlets.yaml and syncs it into the outlets table.

Keeping the outlet list in a YAML file (rather than hardcoded in Python or
only in the DB) means adding/disabling/fixing a feed is a one-line config
edit, no migration or deploy needed.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models import Outlet

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "outlets.yaml"


@dataclass
class OutletConfigEntry:
    name: str
    rss_feed_url: str
    is_active: bool = True


def load_outlets_config(path: Path = DEFAULT_CONFIG_PATH) -> list[OutletConfigEntry]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []

    return [
        OutletConfigEntry(
            name=entry["name"],
            rss_feed_url=entry["rss_feed_url"],
            is_active=entry.get("is_active", True),
        )
        for entry in raw
    ]


def sync_outlets(db: Session, path: Path = DEFAULT_CONFIG_PATH) -> list[Outlet]:
    """Upserts config/outlets.yaml into the outlets table, matched by name.

    Safe to call on every ingestion run - existing outlets get their
    rss_feed_url/is_active refreshed from config; new entries are inserted.
    Outlets removed from the YAML are left alone (not deleted) so historical
    articles keep a valid outlet_id.
    """
    entries = load_outlets_config(path)
    existing = {o.name: o for o in db.query(Outlet).all()}

    synced: list[Outlet] = []
    for entry in entries:
        outlet = existing.get(entry.name)
        if outlet is None:
            outlet = Outlet(name=entry.name, rss_feed_url=entry.rss_feed_url, is_active=entry.is_active)
            db.add(outlet)
        else:
            outlet.rss_feed_url = entry.rss_feed_url
            outlet.is_active = entry.is_active
        synced.append(outlet)

    db.commit()
    for outlet in synced:
        db.refresh(outlet)
    return synced
