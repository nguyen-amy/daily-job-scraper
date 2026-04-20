# Daily Job Scraper

Automated GitHub Actions pipeline that scrapes Apple and Google career pages for Data Scientist / AI roles posted today and emails the links via Gmail SMTP.

## How it works

- Runs 4x per day (00:00, 06:00, 12:00, 18:00 UTC) via `.github/workflows/scrape.yml`.
- Uses Playwright (headless Chromium) because both career pages are SPAs with no public JSON API.
- Dedupes against a 7-day-rolling seen-jobs store (`.state/seen_jobs.json`). On GitHub Actions the store is persisted via `actions/cache`. Skips the email entirely when nothing new.

  Apple surfaces real posting dates on the site; Google doesn't. Both are handled by the same seen-store — a job is "new" if its stable per-company ID hasn't been seen in the last 7 days.

## Local setup

```bash
python3 -m venv djs
source djs/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# edit .env with your Gmail + app password
```

## Gmail app password

1. Enable 2FA on your Google account.
2. Generate an app password: https://myaccount.google.com/apppasswords
3. Use the 16-character password (spaces optional) as `GMAIL_APP_PASSWORD`.

## GitHub deployment

```bash
gh repo create daily_job_scraper --private --source=. --push
```

Then in the repo's **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
| --- | --- |
| `GMAIL_USER` | `you@gmail.com` |
| `GMAIL_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` |

Trigger a test run from the **Actions** tab → **Daily Job Scrape** → **Run workflow**.

## Gotchas

- **60-day inactivity rule**: GitHub automatically disables scheduled workflows if the repo has no commits for 60 days. Either push a small change periodically or add a keepalive action.
- **Site DOM changes**: If Apple or Google rework their markup, the scrapers will silently return 0 jobs. The Actions logs show the "parsed N jobs" line for each company — watch for sudden drops.
- **Cron drift**: GitHub cron jobs can be delayed by several minutes during high load. Don't schedule critical work to the exact minute.
