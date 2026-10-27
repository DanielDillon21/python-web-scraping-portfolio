# Login + Infinite Scroll Scraper (Playwright)

Scrapes the kinds of sites that break simple scrapers: content loaded by JavaScript as you scroll,
and data that only appears after logging in.

**Result:** 100 of 100 quotes captured from the infinite-scroll feed, logged in through a
CSRF-protected form, and merged with members-only links. Every record matched (0 missing).

## What it does
1. **Infinite scroll.** Drives a real Chromium browser, scrolling and waiting for each new batch
   from the site's background API until the feed stops growing.
2. **Login.** Fills the login form (the site's hidden CSRF token is handled automatically by the
   browser), confirms success, and keeps the session for the rest of the run.
3. **Members-only data.** Walks the paginated listing while logged in and collects the Goodreads
   and author links that anonymous visitors never see.
4. **Merge and clean.** Joins both sources into one table, normalizes text, counts tags and removes duplicates.
5. **Export.** Writes a CSV plus an Excel workbook with three sheets: Quotes, By Author and Top Tags.

## Run
```bash
python quotes_scraper.py          # headless
python quotes_scraper.py --show   # watch the browser work (good for a screen recording)
```
Credentials come from `SCRAPER_USER` and `SCRAPER_PASS` environment variables, so nothing secret
lives in the code. The sandbox site accepts any value.
