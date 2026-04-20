"""Smoke tests \u2014 verify modules import and pure functions work."""
from datetime import date
from pathlib import Path

from src.scrapers.apple import _parse_posted as apple_parse
from src.scrapers.base import Job
from src.seen_store import SeenStore


def test_apple_parse_posted_with_prefix():
    assert apple_parse("Posted: Apr 15, 2026") == date(2026, 4, 15)


def test_apple_parse_posted_plain():
    assert apple_parse("Apr 15, 2026") == date(2026, 4, 15)


def test_apple_parse_posted_bad():
    assert apple_parse("") is None
    assert apple_parse("nonsense") is None


def test_seen_store_filters_duplicates(tmp_path: Path):
    store = SeenStore(path=tmp_path / "seen.json")
    jobs = [
        Job(company="Apple", job_id="A1", title="ML Engineer", location="Cupertino", url="https://apple.com/a1"),
        Job(company="Google", job_id="G1", title="Data Scientist", location="MTV", url="https://google.com/g1"),
    ]
    first = store.filter_new(jobs)
    assert len(first) == 2
    # Second pass with the same jobs yields nothing.
    second = store.filter_new(jobs)
    assert second == []
    # Adding a new job surfaces only it.
    jobs.append(Job(company="Apple", job_id="A2", title="Research Scientist", location="Austin", url="https://apple.com/a2"))
    third = store.filter_new(jobs)
    assert len(third) == 1 and third[0].job_id == "A2"


def test_seen_store_persists(tmp_path: Path):
    path = tmp_path / "seen.json"
    s1 = SeenStore(path=path)
    s1.filter_new([Job(company="Apple", job_id="X", title="t", location="", url="u")])
    s1.save()

    s2 = SeenStore(path=path)
    again = s2.filter_new([Job(company="Apple", job_id="X", title="t", location="", url="u")])
    assert again == []
