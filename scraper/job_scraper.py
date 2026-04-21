#!/usr/bin/env python3
"""
Scrapes Watershed and Figma careers pages for Data Scientist roles.
Sends an email when new postings are detected.
"""
import json
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

TARGET_KEYWORDS = ["data scientist"]

COMPANIES = [
    {
        "name": "Watershed",
        "careers_url": "https://watershed.com/careers",
        "greenhouse_board": "watershedclimate",
        "lever_company": "watershed",
    },
    {
        "name": "Figma",
        "careers_url": "https://www.figma.com/careers/",
        "greenhouse_board": "figma",
        "lever_company": "figma",
    },
]

SEEN_JOBS_FILE = "data/seen_jobs.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobAlertBot/1.0)"}


def is_target_role(title: str) -> bool:
    return any(kw in title.lower() for kw in TARGET_KEYWORDS)


def fetch_greenhouse_jobs(board_token: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        jobs = []
        for job in resp.json().get("jobs", []):
            if is_target_role(job.get("title", "")):
                jobs.append({
                    "id": str(job["id"]),
                    "title": job["title"],
                    "location": job.get("location", {}).get("name", ""),
                    "url": job.get("absolute_url", ""),
                })
        return jobs
    except Exception as e:
        print(f"  Greenhouse API failed ({board_token}): {e}")
        return []


def fetch_lever_jobs(company: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        jobs = []
        for posting in resp.json():
            if is_target_role(posting.get("text", "")):
                jobs.append({
                    "id": posting["id"],
                    "title": posting["text"],
                    "location": posting.get("categories", {}).get("location", ""),
                    "url": posting.get("hostedUrl", ""),
                })
        return jobs
    except Exception as e:
        print(f"  Lever API failed ({company}): {e}")
        return []


def fetch_html_jobs(careers_url: str, company_name: str) -> list[dict]:
    """Last-resort HTML scrape — catches jobs not served via a known ATS API."""
    try:
        resp = requests.get(careers_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        seen_titles: set[str] = set()
        jobs = []
        for tag in soup.find_all(["a", "h1", "h2", "h3", "h4", "li"]):
            text = tag.get_text(strip=True)
            if not is_target_role(text) or text in seen_titles:
                continue
            seen_titles.add(text)
            href = tag.get("href", "") if tag.name == "a" else ""
            if href and not href.startswith("http"):
                href = careers_url.rstrip("/") + "/" + href.lstrip("/")
            slug = re.sub(r"[^a-z0-9]+", "_", text.lower())[:60]
            jobs.append({
                "id": f"{company_name.lower()}_{slug}",
                "title": text,
                "location": "",
                "url": href or careers_url,
            })
        return jobs
    except Exception as e:
        print(f"  HTML scrape failed ({careers_url}): {e}")
        return []


def scrape_company(company: dict) -> list[dict]:
    name = company["name"]

    if board := company.get("greenhouse_board"):
        jobs = fetch_greenhouse_jobs(board)
        if jobs:
            print(f"  {name}: {len(jobs)} match(es) via Greenhouse")
            return jobs

    if lever := company.get("lever_company"):
        jobs = fetch_lever_jobs(lever)
        if jobs:
            print(f"  {name}: {len(jobs)} match(es) via Lever")
            return jobs

    print(f"  {name}: falling back to HTML scrape")
    jobs = fetch_html_jobs(company["careers_url"], name)
    print(f"  {name}: {len(jobs)} match(es) via HTML")
    return jobs


def load_seen_jobs() -> dict:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE) as f:
            return json.load(f)
    return {}


def save_seen_jobs(seen: dict) -> None:
    os.makedirs(os.path.dirname(SEEN_JOBS_FILE), exist_ok=True)
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen, f, indent=2, sort_keys=True)


def send_email(new_jobs: list[dict]) -> None:
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    recipient = os.environ["EMAIL_RECIPIENT"]

    count = len(new_jobs)
    subject = f"[Job Alert] {count} new Data Scientist posting{'s' if count > 1 else ''}"

    rows = "".join(
        f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee">
            <strong>{job['title']}</strong><br>
            <span style="color:#555">{job['company']}</span>
            {' &mdash; ' + job['location'] if job['location'] else ''}
          </td>
          <td style="padding:8px;border-bottom:1px solid #eee">
            <a href="{job['url']}">Apply</a>
          </td>
        </tr>"""
        for job in new_jobs
    )

    html = f"""
    <html><body style="font-family:sans-serif;color:#222">
      <h2 style="color:#2563eb">New Data Scientist Openings</h2>
      <p>Found <strong>{count}</strong> new posting(s) as of
         {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.</p>
      <table style="border-collapse:collapse;width:100%;max-width:600px">
        <thead>
          <tr style="background:#f3f4f6">
            <th style="padding:8px;text-align:left">Role</th>
            <th style="padding:8px;text-align:left">Link</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"Email sent → {recipient}: {subject}")


def main() -> None:
    print(f"=== Job scraper run: {datetime.utcnow().isoformat()} UTC ===")
    seen = load_seen_jobs()
    all_new: list[dict] = []

    for company in COMPANIES:
        name = company["name"]
        print(f"\nScraping {name}…")
        current_jobs = scrape_company(company)

        company_seen = seen.get(name, {})
        new_jobs = []
        for job in current_jobs:
            if job["id"] not in company_seen:
                job["company"] = name
                new_jobs.append(job)
                company_seen[job["id"]] = {
                    "title": job["title"],
                    "url": job["url"],
                    "first_seen": datetime.utcnow().isoformat(),
                }

        seen[name] = company_seen

        if new_jobs:
            print(f"  → {len(new_jobs)} NEW: {[j['title'] for j in new_jobs]}")
            all_new.extend(new_jobs)
        else:
            print(f"  → No new postings")

    save_seen_jobs(seen)
    print(f"\nSaved seen_jobs.json ({sum(len(v) for v in seen.values())} total tracked)")

    if all_new:
        send_email(all_new)
    else:
        print("No new jobs — no email sent.")


if __name__ == "__main__":
    main()
