"""Scraper for Google Careers (Data Science / ML / AI).

Google does not expose posting dates anywhere in the rendered HTML or detail page,
so the scraper only returns the current first page of results sorted by date.
Deduplication is handled by the shared seen-jobs store in `src/seen_store.py`.
"""
from __future__ import annotations

import logging
import re

from playwright.async_api import async_playwright

from .base import BaseScraper, Job

log = logging.getLogger(__name__)

SEARCH_URL = (
    "https://www.google.com/about/careers/applications/jobs/results/"
    "?q=%22data+scientist%22+%22machine+learning%22+%22artificial+intelligence%22"
    "&sort_by=date"
)

# href is relative like: jobs/results/141494234703110854-software-engineer-...?q=...
_JOB_ID_RE = re.compile(r"jobs/results/(\d+)-")

KEYWORDS = re.compile(
    r"\b(data scientist|machine learning|\bml\b|\bai\b|artificial intelligence|"
    r"deep learning|data science|research scientist|applied scientist|generative ai|llm)\b",
    re.IGNORECASE,
)


class GoogleScraper(BaseScraper):
    company = "Google"

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
            log.info("Google: loading %s", SEARCH_URL)
            await page.goto(SEARCH_URL, wait_until="networkidle", timeout=60_000)

            try:
                await page.wait_for_selector("li.lLd3Je h3.QJPWVe", timeout=30_000)
            except Exception:
                log.warning("Google: job cards did not appear; returning 0")
                await browser.close()
                return []

            raw = await page.evaluate(
                """() => {
                    // Google uses Material Icons ligatures: <i class="google-material-icons">place</i>
                    // renders as an icon but its textContent is the literal word 'place'.
                    // Strip those before reading text.
                    const ICON_WORDS = new Set(['place','corporate_fare','bar_chart','share','link','email','public']);
                    const cleanText = (node) => {
                        const clone = node.cloneNode(true);
                        clone.querySelectorAll('i, .google-material-icons').forEach(n => n.remove());
                        return clone.textContent.trim();
                    };
                    return Array.from(document.querySelectorAll('li.lLd3Je')).map(li => {
                        const titleEl = li.querySelector('h3.QJPWVe');
                        const anchor = li.querySelector('a[aria-label^="Learn more about"]');
                        let location = '';
                        for (const el of li.querySelectorAll('span')) {
                            let t = cleanText(el);
                            // Drop standalone icon ligatures left over
                            ICON_WORDS.forEach(w => { if (t.startsWith(w)) t = t.slice(w.length).trim(); });
                            if (!t || t.length > 120) continue;
                            if (t.includes(',') || /remote/i.test(t)) {
                                if (!t.toLowerCase().includes('learn more')) {
                                    location = t;
                                    break;
                                }
                            }
                        }
                        return {
                            title: titleEl ? titleEl.textContent.trim() : null,
                            href: anchor ? anchor.getAttribute('href') : null,
                            location,
                        };
                    });
                }"""
            )
            await browser.close()

        jobs: list[Job] = []
        for r in raw:
            if not r.get("title") or not r.get("href"):
                continue
            title = r["title"]
            if not KEYWORDS.search(title):
                continue
            m = _JOB_ID_RE.search(r["href"])
            if not m:
                continue
            job_id = m.group(1)
            href = r["href"]
            if href.startswith("http"):
                url = href
            else:
                url = f"https://www.google.com/about/careers/applications/{href.lstrip('/')}"
            jobs.append(Job(
                company=self.company,
                job_id=job_id,
                title=title,
                location=r.get("location") or "",
                url=url,
                posted_date=None,
                team=None,
            ))

        log.info("Google: parsed %d jobs", len(jobs))
        return jobs
