"""Shared types and base class for company scrapers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Job:
    company: str
    job_id: str          # Stable per-company identifier for dedup (from URL).
    title: str
    location: str
    url: str
    posted_date: date | None = None   # Apple has this; Google doesn't.
    team: str | None = None

    @property
    def dedup_key(self) -> str:
        return f"{self.company}::{self.job_id}"


class BaseScraper(ABC):
    """Each company scraper returns a list of Job objects for recent postings."""

    company: str

    @abstractmethod
    async def fetch(self) -> list[Job]:
        """Scrape and return the jobs currently listed on the first page of results."""
        raise NotImplementedError
