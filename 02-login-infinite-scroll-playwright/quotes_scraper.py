"""
Browser-automation scraper built with Playwright.

Handles the three things that break simple requests/BeautifulSoup scrapers:
  1. Infinite scroll  - content only loads as the page is scrolled
                        (quotes.toscrape.com/scroll, fed by a background API)
  2. Login + session  - fills a form with a hidden CSRF token, keeps the
                        session cookie, and scrapes members-only fields
                        (Goodreads links that only appear when logged in)
  3. Merging sources  - joins both datasets into one clean table

quotes.toscrape.com is a public sandbox built for scraping practice and
accepts any username/password.

Run:
    python quotes_scraper.py            # headless
    python quotes_scraper.py --show     # watch the browser work
Outputs:
    output/quotes.csv
    output/quotes.xlsx
"""

import argparse
import os
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

BASE_URL = "https://quotes.toscrape.com"
OUTPUT_DIR = Path(__file__).parent / "output"

# Sandbox credentials; a real job would read these from environment variables.
USERNAME = os.environ.get("SCRAPER_USER", "demo")
PASSWORD = os.environ.get("SCRAPER_PASS", "demo")


def scrape_infinite_scroll(page):
    """Scroll until no new quotes load, then extract everything on the page."""
    page.goto(f"{BASE_URL}/scroll")
    page.wait_for_selector("div.quote")

    previous = 0
    while True:
        count = page.locator("div.quote").count()
        if count == previous:
            break
        previous = count
        page.mouse.wheel(0, 20000)
        try:
            # Wait for the next batch from the background API to render.
            page.wait_for_function(
                "n => document.querySelectorAll('div.quote').length > n", arg=count, timeout=5000
            )
        except Exception:
            pass  # nothing new arrived: we've hit the end of the feed
    print(f"[scroll] loaded {previous} quotes")

    return page.eval_on_selector_all(
        "div.quote",
        """els => els.map(el => ({
            text: el.querySelector('.text').innerText,
            author: el.querySelector('.author').innerText,
            tags: [...el.querySelectorAll('.tag')].map(t => t.innerText).join(', '),
        }))""",
    )


def login(page):
    page.goto(f"{BASE_URL}/login")
    page.fill("#username", USERNAME)
    page.fill("#password", PASSWORD)
    page.click("input[type=submit]")
    page.wait_for_selector("a[href='/logout']")
    print("[login] authenticated")


def scrape_members_fields(page):
    """Walk the paginated listing while logged in and collect members-only links."""
    rows = []
    page.goto(BASE_URL)
    while True:
        rows += page.eval_on_selector_all(
            "div.quote",
            """els => els.map(el => {
                const links = [...el.querySelectorAll('a')];
                const goodreads = links.find(a => a.href.includes('goodreads.com'));
                const about = links.find(a => a.getAttribute('href').startsWith('/author/'));
                return {
                    text: el.querySelector('.text').innerText,
                    goodreads_url: goodreads ? goodreads.href : null,
                    author_url: about ? about.href : null,
                };
            })""",
        )
        next_link = page.locator("li.next a")
        if next_link.count() == 0:
            break
        next_link.click()
        page.wait_for_load_state("domcontentloaded")
    print(f"[members] collected links for {len(rows)} quotes")
    return rows


def clean(df):
    df["text"] = df["text"].str.strip().str.strip("“”\"")
    df["author"] = df["author"].str.strip()
    df["tag_count"] = df["tags"].apply(lambda t: len(t.split(", ")) if t else 0)
    return df.drop_duplicates(subset=["text", "author"]).reset_index(drop=True)


def export(df):
    OUTPUT_DIR.mkdir(exist_ok=True)
    df.to_csv(OUTPUT_DIR / "quotes.csv", index=False, encoding="utf-8-sig")

    by_author = (
        df.groupby("author")
        .agg(quotes=("text", "count"), author_url=("author_url", "first"))
        .sort_values("quotes", ascending=False)
        .reset_index()
    )
    tags = (
        df["tags"].str.split(", ").explode().loc[lambda s: s != ""]
        .value_counts().rename_axis("tag").reset_index(name="quotes")
    )

    with pd.ExcelWriter(OUTPUT_DIR / "quotes.xlsx", engine="openpyxl") as writer:
        for name, table in {"Quotes": df, "By Author": by_author, "Top Tags": tags}.items():
            table.to_excel(writer, sheet_name=name, index=False)
            ws = writer.sheets[name]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(width + 2, 70)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true", help="run with a visible browser")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show)
        context = browser.new_context()
        page = context.new_page()

        scrolled = pd.DataFrame(scrape_infinite_scroll(page))
        login(page)
        members = pd.DataFrame(scrape_members_fields(page))

        browser.close()

    # The two sources format quote text identically, so join on it.
    df = scrolled.merge(members, on="text", how="left")
    df = clean(df)
    export(df)

    missing = df["goodreads_url"].isna().sum()
    print(f"Wrote {len(df)} quotes from {df['author'].nunique()} authors to {OUTPUT_DIR} "
          f"({missing} without a members-only link)")


if __name__ == "__main__":
    main()
