"""Persistent 'jobs already seen' store, shared across scrapers.

State is a small JSON file mapping `dedup_key` -> ISO timestamp of first sighting.
Entries older than `TTL_DAYS` are pruned on each load so the file can't grow forever.

In GitHub Actions the state file is restored/saved via `actions/cache`; locally it
lives at `.state/seen_jobs.json` (gitignored) so back-to-back runs dedupe too.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .scrapers.base import Job

log = logging.getLogger(__name__)

TTL_DAYS = 30
DEFAULT_PATH = Path(".state/seen_jobs.json")


class SeenStore:
    def __init__(self, path: Path | None = None):
        self.path = path or Path(os.environ.get("SEEN_STORE_PATH", DEFAULT_PATH))
        self._seen: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            log.info("SeenStore: no existing state at %s", self.path)
            return
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            log.warning("SeenStore: failed to read %s (%s); starting fresh", self.path, e)
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)
        for key, iso in raw.items():
            try:
                if datetime.fromisoformat(iso) >= cutoff:
                    self._seen[key] = iso
            except ValueError:
                continue
        log.info("SeenStore: loaded %d entries (pruned to last %dd)", len(self._seen), TTL_DAYS)

    def filter_new(self, jobs: list[Job]) -> list[Job]:
        """Return jobs not previously recorded. Newly-seen jobs are added to state."""
        now_iso = datetime.now(timezone.utc).isoformat()
        new: list[Job] = []
        for j in jobs:
            if j.dedup_key in self._seen:
                continue
            self._seen[j.dedup_key] = now_iso
            new.append(j)
        return new

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._seen, indent=2, sort_keys=True))
        log.info("SeenStore: wrote %d entries to %s", len(self._seen), self.path)
