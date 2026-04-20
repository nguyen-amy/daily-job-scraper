"""Scraper for Apple Careers (Machine Learning & AI + Data Science teams)."""
from __future__ import annotations

import logging
import re
from datetime import date

from dateutil import parser as dateparser
from playwright.async_api import async_playwright

from .base import BaseScraper, Job

log = logging.getLogger(__name__)

# Apple team slugs: Machine Learning & AI + Data Science & Analytics, sorted newest.
SEARCH_URL = (
    "https://jobs.apple.com/en-us/search"
    "?team=machine-learning-and-ai-SFTWR-MCHLN"
    "+data-science-and-analytics-SFTWR-DSGNAN"
    "&sort=newest"
)

# Role number extracted from the href, e.g. /en-us/details/200657848-0157/...
_ROLE_ID_RE = re.compile(r"/details/([^/]+)/")

# Defense-in-depth title/team filter in case Apple changes the team URL params.
KEYWORDS = re.compile(
    r"\b(data scientist|machine learning|\bml\b|\bai\b|artificial intelligence|"
    r"deep learning|data science|research scientist|applied scientist|generative ai|llm)\b",
    re.IGNORECASE,
)


class AppleScraper(BaseScraper):
    company = "Apple"

    async def fetch(self) -> list[Job]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/127.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            log.info("Apple: loading %s", SEARCH_URL)
            await page.goto(SEARCH_URL, wait_until="networkidle", timeout=60_000)

            try:
                await page.wait_for_selector("div.job-title-link h3 a", timeout=30_000)
            except Exception:
                log.warning("Apple: job anchors did not appear; returning 0")
                await browser.close()
                return []

            # Run extraction in the page context for speed.
            raw = await page.evaluate(
                """() => Array.from(document.querySelectorAll('div.job-title-link')).map(div => {
                    const a = div.querySelector('h3 a');
                    const team = div.querySelector('span.team-name');
                    const posted = div.querySelector('span.job-posted-date');
                    // Location is in a sibling column on the same row.
                    const row = div.closest('div.job-title');
                    const loc = row ? row.querySelector('div.job-title-location span:not(.a11y)') : null;
                    return {
                        href: a ? a.getAttribute('href') : null,
                        title: a ? a.textContent.trim() : null,
                        team: team ? team.textContent.trim() : null,
                        posted: posted ? posted.textContent.trim() : null,
                        location: loc ? loc.textContent.trim() : '',
                    };
                })"""
            )
            await browser.close()

        jobs: list[Job] = []
        for r in raw:
            if not r.get("href") or not r.get("title"):
                continue
            title = r["title"]
            team = r.get("team")
            if not KEYWORDS.search(title) and not (team and KEYWORDS.search(team)):
                continue
            m = _ROLE_ID_RE.search(r["href"])
            if not m:
                continue
            role_id = m.group(1)
            url = f"https://jobs.apple.com{r['href']}" if r["href"].startswith("/") else r["href"]
            jobs.append(Job(
                company=self.company,
                job_id=role_id,
                title=title,
                location=r.get("location") or "",
                url=url,
                posted_date=_parse_posted(r.get("posted") or ""),
                team=team,
            ))

        log.info("Apple: parsed %d jobs", len(jobs))
        return jobs


def _parse_posted(text: str) -> date | None:
    """Parse Apple's posted-date string (e.g. 'Posted: Apr 15, 2026' or 'Apr 15, 2026')."""
    if not text:
        return None
    cleaned = text.replace("Posted:", "").strip()
    try:
        return dateparser.parse(cleaned).date()
    except (ValueError, TypeError):
        return None
